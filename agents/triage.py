# agents/triage.py
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from config import settings
from pipeline.state import IncidentState

logger = logging.getLogger(__name__)

# How many minutes before reported_at to start investigating
LOOKBACK_MINUTES = settings.default_lookback_minutes

# Valid severity levels in descending order
SEVERITY_LEVELS = ["critical", "high", "medium", "low"]

# Valid incident types
INCIDENT_TYPES = ["deployment", "config", "dependency", "unknown"]

# Gemini model — low temperature for analytical consistency
llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.1,
    google_api_key=settings.gemini_api_key,
)

def calculate_investigation_window(
    reported_at: str,
    lookback_minutes: int = LOOKBACK_MINUTES,
) -> dict[str, str]:
    """Calculate the time window to investigate before the incident was reported.

    This is deterministic — no LLM needed. The window is always
    lookback_minutes before reported_at up to reported_at.

    Args:
        reported_at: ISO format string of when the incident was reported.
        lookback_minutes: How many minutes before report time to investigate.

    Returns:
        Dict with 'start' and 'end' as ISO format UTC strings.

    Raises:
        ValueError: If reported_at cannot be parsed as a datetime.
    """
    try:
        reported_time = datetime.fromisoformat(
            reported_at.replace("Z", "+00:00")
        )
    except ValueError as e:
        raise ValueError(
            f"Cannot parse reported_at as datetime: {reported_at}"
        ) from e

    if reported_time.tzinfo is None:
        reported_time = reported_time.replace(tzinfo=timezone.utc)

    window_start = reported_time - timedelta(minutes=lookback_minutes)
    window_end = reported_time

    return {
        "start": window_start.isoformat(),
        "end": window_end.isoformat(),
    }

async def _classify_incident(
    description: str,
    raw_logs: str,
) -> dict[str, str | list[str]]:
    """Use Gemini to classify incident severity, type, and affected services.

    Sends only the description and a small log sample — never the full log.
    The deterministic log parser handles full log analysis in the next agent.

    Args:
        description: Plain English incident description from the SRE.
        raw_logs: Raw log content — only first 200 lines are sent to LLM.

    Returns:
        Dict with severity, incident_type, and affected_services.
    """
    # Take only the first 200 lines to keep the prompt small
    log_sample = "\n".join(raw_logs.splitlines()[:200])

    prompt = f"""You are an SRE analyst performing incident triage.

Analyze the following incident and respond with ONLY a JSON object.
No explanation, no markdown, no code fences — just the raw JSON.

Incident description:
{description}

Log sample (first 200 lines):
{log_sample}

Respond with exactly this JSON structure:
{{
    "severity": "<one of: critical, high, medium, low>",
    "incident_type": "<one of: deployment, config, dependency, unknown>",
    "affected_services": ["<service name>", "<service name>"]
}}

Severity guidelines:
- critical: Complete outage, data loss, or security breach
- high: Major feature broken, significant user impact
- medium: Partial degradation, some users affected
- low: Minor issue, minimal user impact

Incident type guidelines:
- deployment: Likely caused by a recent code or config deployment
- config: Configuration change without a deployment
- dependency: External service or database failure
- unknown: Cannot determine from available information"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw_content = response.content.strip()

        # Strip markdown fences if Gemini adds them despite instructions
        if raw_content.startswith("```"):
            raw_content = raw_content.split("```")[1]
            if raw_content.startswith("json"):
                raw_content = raw_content[4:]

        import json
        parsed = json.loads(raw_content)

        # Validate and sanitize LLM output
        severity = parsed.get("severity", "unknown")
        if severity not in SEVERITY_LEVELS:
            severity = "unknown"

        incident_type = parsed.get("incident_type", "unknown")
        if incident_type not in INCIDENT_TYPES:
            incident_type = "unknown"

        affected_services = parsed.get("affected_services", [])
        if not isinstance(affected_services, list):
            affected_services = []

        return {
            "severity": severity,
            "incident_type": incident_type,
            "affected_services": affected_services,
        }

    except Exception as e:
        logger.error(f"LLM classification failed: {e}")
        return {
            "severity": "unknown",
            "incident_type": "unknown",
            "affected_services": [],
        }
    
async def triage_node(state: IncidentState) -> dict:
    """LangGraph node — classify incident and calculate investigation window.

    Runs first in the pipeline. Sets severity, incident_type,
    affected_services, and investigation_window for downstream agents.

    Args:
        state: Current incident state from LangGraph.

    Returns:
        Partial state update with triage findings.
    """
    incident_id = state["incident_id"]
    logger.info(f"Triage agent starting for incident {incident_id}")

    try:
        # Step 1 — deterministic: calculate investigation window
        investigation_window = calculate_investigation_window(
            reported_at=state["reported_at"],
        )

        # Step 2 — LLM: classify severity, type, affected services
        classification = await _classify_incident(
            description=state["description"],
            raw_logs=state["raw_logs"],
        )

        logger.info(
            f"Triage complete for {incident_id} — "
            f"severity: {classification['severity']}, "
            f"type: {classification['incident_type']}"
        )

        return {
            "severity": classification["severity"],
            "incident_type": classification["incident_type"],
            "affected_services": classification["affected_services"],
            "investigation_window": investigation_window,
        }

    except Exception as e:
        logger.error(f"Triage agent failed for incident {incident_id}: {e}")
        return {
            "severity": "unknown",
            "incident_type": "unknown",
            "affected_services": [],
            "investigation_window": calculate_investigation_window(
                reported_at=state["reported_at"],
            ),
            "errors": state.get("errors", []) + [f"triage: {str(e)}"],
        }
