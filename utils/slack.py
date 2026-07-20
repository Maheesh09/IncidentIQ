# utils/slack.py
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from utils.secret_manager import retrieve_secret

logger = logging.getLogger(__name__)

# Slack webhook delivery timeout — fail fast rather than blocking the runner.
SLACK_TIMEOUT_SECONDS = 10


def _build_blocks(incident_id: str, report: dict) -> list[dict]:
    """Build a Slack Block Kit payload from an RCA report.

    Formats the most actionable parts of the report — summary, top
    hypothesis, immediate fix, prevention note. The full report is
    always available via the API; the Slack message is a signal,
    not a replacement.

    Args:
        incident_id: The incident identifier, e.g. INC-20260718-A3F9C12B.
        report: The raw_report dict from the Report Agent.

    Returns:
        A list of Block Kit block dicts ready to POST to Slack.
    """
    summary = report.get("summary", "No summary available.")
    root_causes = report.get("root_causes") or []
    immediate_fix = report.get("immediate_fix", "")
    prevention_note = report.get("prevention_note", "")
    duration = report.get("analysis_duration_seconds")
    timeline = report.get("timeline") or []

    blocks: list[dict] = []

    # ── Header ─────────────────────────────────────────────────────────────
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"🔍 RCA Complete — {incident_id}",
            "emoji": True,
        },
    })

    # ── Summary ────────────────────────────────────────────────────────────
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*Summary*\n{summary}",
        },
    })

    blocks.append({"type": "divider"})

    # ── Top hypothesis ──────────────────────────────────────────────────────
    if root_causes:
        top = root_causes[0]
        confidence_pct = int(float(top.get("confidence", 0)) * 100)
        root_cause_text = top.get("root_cause", "")

        # Confidence bar — 10 blocks, each block = 10%
        filled = confidence_pct // 10
        bar = "█" * filled + "░" * (10 - filled)

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Most Likely Root Cause* ({confidence_pct}% confidence)\n"
                    f"`{bar}` {confidence_pct}%\n"
                    f"{root_cause_text}"
                ),
            },
        })

        # Second hypothesis if present — lower weight
        if len(root_causes) > 1:
            second = root_causes[1]
            second_pct = int(float(second.get("confidence", 0)) * 100)
            blocks.append({
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": (
                        f"*Alternative ({second_pct}%):* "
                        f"{second.get('root_cause', '')}"
                    ),
                }],
            })

        blocks.append({"type": "divider"})

    # ── Timeline (first 4 events) ────────────────────────────────────────
    if timeline:
        visible = timeline[:4]
        remaining = len(timeline) - len(visible)
        timeline_text = "\n".join(f"• {event}" for event in visible)
        if remaining > 0:
            timeline_text += f"\n_...and {remaining} more events_"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Timeline*\n{timeline_text}",
            },
        })
        blocks.append({"type": "divider"})

    # ── Immediate fix ───────────────────────────────────────────────────────
    if immediate_fix:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Immediate Fix*\n{immediate_fix}",
            },
        })

    # ── Prevention note ─────────────────────────────────────────────────────
    if prevention_note:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Prevention*\n{prevention_note}",
            },
        })

    # ── Footer context ───────────────────────────────────────────────────────
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    footer_parts = [f"IncidentIQ  •  {generated_at}"]
    if duration:
        footer_parts.append(f"Analysed in {duration}s")

    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": "  |  ".join(footer_parts),
        }],
    })

    return blocks


async def send_slack_notification(
    secret_name: str,
    incident_id: str,
    report: dict,
    config_metadata: dict | None = None,
) -> bool:
    """Send an RCA report summary to a configured Slack channel.

    Retrieves the webhook URL from Secret Manager, formats a Block Kit
    message, and POSTs to Slack. Always returns rather than raising —
    a Slack delivery failure must not mark the incident as failed.

    Args:
        secret_name: Secret Manager reference for the Slack webhook URL.
        incident_id: The incident identifier for the message header.
        report: raw_report dict from the Report Agent.
        config_metadata: Optional config — currently unused, reserved for
                         future channel override support.

    Returns:
        True if delivered successfully, False on any failure.
    """
    try:
        credentials = await retrieve_secret(secret_name)
        webhook_url = credentials.get("webhook_url")
        if not webhook_url:
            logger.error(
                f"Slack secret {secret_name!r} has no webhook_url key"
            )
            return False

        blocks = _build_blocks(incident_id, report)
        payload = {"blocks": blocks}

        async with httpx.AsyncClient(timeout=SLACK_TIMEOUT_SECONDS) as client:
            response = await client.post(webhook_url, json=payload)

        # Slack returns 200 with body "ok" on success, or a plain text
        # error message on failure. It does not use HTTP error codes for
        # application-level errors.
        if response.status_code == 200 and response.text == "ok":
            logger.info(
                f"Slack notification sent for incident {incident_id}"
            )
            return True

        logger.error(
            f"Slack delivery failed for {incident_id}: "
            f"HTTP {response.status_code} — {response.text!r}"
        )
        return False

    except Exception as e:
        logger.error(
            f"Slack notification error for incident {incident_id}: {e}"
        )
        return False