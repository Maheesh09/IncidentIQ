# utils/pagerduty.py
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from utils.secret_manager import retrieve_secret

logger = logging.getLogger(__name__)

PAGERDUTY_EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"
PAGERDUTY_TIMEOUT_SECONDS = 10


def _map_severity(root_causes: list[dict]) -> str:
    """Derive a PagerDuty severity from the top hypothesis confidence.

    PagerDuty accepts: critical, error, warning, info.
    We map from the top hypothesis confidence score so high-confidence
    findings page loudly and low-confidence ones don't.

    Args:
        root_causes: Ranked hypothesis list from the Report Agent.

    Returns:
        A PagerDuty severity string.
    """
    if not root_causes:
        return "error"

    confidence = float(root_causes[0].get("confidence", 0))

    if confidence >= 0.80:
        return "critical"
    elif confidence >= 0.50:
        return "error"
    elif confidence >= 0.30:
        return "warning"
    return "info"


def _build_payload(
    routing_key: str,
    incident_id: str,
    report: dict,
    config_metadata: dict | None,
) -> dict:
    """Build a PagerDuty Events API v2 payload from an RCA report.

    Uses event_action=trigger. The dedup_key is the incident ID so
    repeated delivery attempts don't create duplicate PagerDuty incidents.

    Args:
        routing_key: Events API v2 integration key.
        incident_id: IncidentIQ incident ID — used as dedup_key.
        report: raw_report dict from the Report Agent.
        config_metadata: Optional config — service_name is used in the
                         alert summary if present.

    Returns:
        A dict ready to POST to the PagerDuty Events API v2.
    """
    root_causes = report.get("root_causes") or []
    summary = report.get("summary", "Incident analysis complete")
    immediate_fix = report.get("immediate_fix", "")
    prevention_note = report.get("prevention_note", "")
    duration = report.get("analysis_duration_seconds")

    severity = _map_severity(root_causes)

    # Build a tight alert title — what PagerDuty shows in the alert list
    service_name = (config_metadata or {}).get("service_name", "")
    if service_name:
        alert_summary = f"[IncidentIQ] {service_name} — {incident_id}"
    else:
        alert_summary = f"[IncidentIQ] RCA complete — {incident_id}"

    # custom_details is what appears in the PagerDuty alert body.
    # Keep it flat and human-readable — nested dicts render poorly.
    custom_details: dict = {
        "incident_id": incident_id,
        "analysis_summary": summary,
    }

    if root_causes:
        top = root_causes[0]
        confidence_pct = int(float(top.get("confidence", 0)) * 100)
        custom_details["root_cause"] = top.get("root_cause", "")
        custom_details["confidence"] = f"{confidence_pct}%"

        # Second hypothesis for context
        if len(root_causes) > 1:
            second = root_causes[1]
            second_pct = int(float(second.get("confidence", 0)) * 100)
            custom_details["alternative_hypothesis"] = (
                f"{second.get('root_cause', '')} ({second_pct}%)"
            )

    if immediate_fix:
        custom_details["immediate_fix"] = immediate_fix

    if prevention_note:
        custom_details["prevention_note"] = prevention_note

    if duration:
        custom_details["analysis_duration_seconds"] = duration

    return {
        "routing_key": routing_key,
        "event_action": "trigger",
        "dedup_key": f"incidentiq-{incident_id}",
        "payload": {
            "summary": alert_summary,
            "severity": severity,
            "source": "IncidentIQ",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "custom_details": custom_details,
        },
    }


async def send_pagerduty_notification(
    secret_name: str,
    incident_id: str,
    report: dict,
    config_metadata: dict | None = None,
) -> bool:
    """Trigger a PagerDuty alert with the RCA report summary.

    Retrieves the routing key from Secret Manager, builds an Events API
    v2 payload, and POSTs to PagerDuty. Always returns rather than
    raising — delivery failure must not affect the incident record.

    Args:
        secret_name: Secret Manager reference for the PagerDuty routing key.
        incident_id: The incident identifier — used as the dedup_key.
        report: raw_report dict from the Report Agent.
        config_metadata: Optional config. service_name is used in the
                         alert title if present.

    Returns:
        True if the alert was accepted, False on any failure.
    """
    try:
        credentials = await retrieve_secret(secret_name)
        routing_key = credentials.get("routing_key")

        if not routing_key:
            logger.error(
                f"PagerDuty secret {secret_name!r} has no routing_key"
            )
            return False

        payload = _build_payload(
            routing_key=routing_key,
            incident_id=incident_id,
            report=report,
            config_metadata=config_metadata,
        )

        async with httpx.AsyncClient(timeout=PAGERDUTY_TIMEOUT_SECONDS) as client:
            response = await client.post(
                PAGERDUTY_EVENTS_URL,
                json=payload,
            )

        # PagerDuty returns 202 Accepted on success with
        # {"status": "success", "message": "Event processed", "dedup_key": "..."}
        if response.status_code == 202:
            logger.info(
                f"PagerDuty alert triggered for incident {incident_id} "
                f"(dedup_key: incidentiq-{incident_id})"
            )
            return True

        # 429 = rate limited, 400 = bad payload, 500 = PagerDuty error
        elif response.status_code in (400, 429, 500):
            logger.error(
                f"PagerDuty delivery failed for {incident_id}: "
                f"HTTP {response.status_code} — {response.text!r}"
            )
            return False
        
        logger.error(
            f"PagerDuty delivery failed for {incident_id}: "
            f"HTTP {response.status_code} — {response.text!r}"
        )
        return False

    except Exception as e:
        logger.error(
            f"PagerDuty notification error for incident {incident_id}: {e}"
        )
        return False