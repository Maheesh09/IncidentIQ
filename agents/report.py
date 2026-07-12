# agents/report.py
from __future__ import annotations

import logging
from datetime import datetime, timezone

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from config import settings
from pipeline.state import IncidentState

logger = logging.getLogger(__name__)

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",
    temperature=0.1,
    google_api_key=settings.gemini_api_key,
)

async def _format_report(
    hypotheses: list[dict],
    description: str,
    severity: str | None,
    log_findings: dict | None,
    deploy_findings: dict | None,
    incident_id: str,
) -> dict:
    """Use Gemini to format synthesis findings into a human-readable RCA report.

    Takes structured hypotheses and produces a clean report an SRE
    can read and act on immediately during or after an incident.

    Args:
        hypotheses: Ranked hypotheses from the Synthesis Agent.
        description: Original incident description from the SRE.
        severity: Incident severity from the Triage Agent.
        log_findings: Structured output from the Log Analysis Agent.
        deploy_findings: Structured output from the Deploy Correlation Agent.
        incident_id: The incident ID for report attribution.

    Returns:
        Dict containing the formatted RCA report fields.
    """
    # Format hypotheses for the prompt
    hypotheses_text = ""
    for h in hypotheses:
        evidence_text = "\n    ".join(h.get("evidence", []))
        hypotheses_text += f"""
Hypothesis {h['rank']} (confidence: {h['confidence']}):
  Root cause: {h['root_cause']}
  Evidence:
    {evidence_text}
  Reasoning: {h['reasoning']}
"""

    # Build timeline context from available findings
    timeline_events = []

    if deploy_findings and deploy_findings.get("commits"):
        for commit in deploy_findings["commits"][:3]:
            timeline_events.append(
                f"{commit['committed_at']} — Deploy [{commit['short_sha']}] "
                f"by {commit['author']}: {commit['message']}"
            )

    if log_findings and log_findings.get("first_error_timestamp"):
        timeline_events.append(
            f"{log_findings['first_error_timestamp']} — "
            f"First error detected in logs"
        )

    timeline_text = (
        "\n".join(timeline_events)
        if timeline_events
        else "Timeline could not be reconstructed from available data"
    )

    prompt = f"""You are a senior SRE writing a post-incident root cause analysis report.

Incident ID: {incident_id}
Severity: {severity or "unknown"}
Description: {description}

Reconstructed timeline:
{timeline_text}

Root cause hypotheses:
{hypotheses_text}

Write a clear, actionable RCA report. Respond with ONLY a JSON object.
No explanation, no markdown, no code fences — just the raw JSON.

{{
    "summary": "<one paragraph plain English summary of what happened and why>",
    "timeline": [
        "<timestamp> — <event description>",
        "<timestamp> — <event description>"
    ],
    "immediate_fix": "<specific action to resolve the incident right now>",
    "prevention_note": "<one specific change to prevent this class of incident>",
    "root_causes": [
        {{
            "rank": 1,
            "confidence": <float>,
            "root_cause": "<root cause statement>",
            "evidence": ["<evidence 1>", "<evidence 2>"],
            "reasoning": "<reasoning>"
        }}
    ]
}}

Guidelines:
- Summary must be readable by a non-technical manager
- Timeline must be in chronological order with real timestamps where available
- Immediate fix must be specific — not "investigate further" or "check the logs"
- Prevention note must be a concrete engineering action
- Root causes must match the hypotheses provided above exactly"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw_content = response.content.strip()

        # Strip markdown fences if present
        if raw_content.startswith("```"):
            raw_content = raw_content.split("```")[1]
            if raw_content.startswith("json"):
                raw_content = raw_content[4:]

        import json
        parsed = json.loads(raw_content)

        return {
            "summary": parsed.get("summary", ""),
            "timeline": parsed.get("timeline", []),
            "immediate_fix": parsed.get("immediate_fix"),
            "prevention_note": parsed.get("prevention_note"),
            "root_causes": parsed.get("root_causes", hypotheses),
        }

    except Exception as e:
        logger.error(f"Report formatting LLM call failed: {e}")
        return {
            "summary": (
                f"Automated RCA completed for incident {incident_id}. "
                f"Manual review of hypotheses below is required."
            ),
            "timeline": timeline_events,
            "immediate_fix": None,
            "prevention_note": None,
            "root_causes": hypotheses,
        }
    

async def generate_report_node(state: IncidentState) -> dict:
    """LangGraph node — format synthesis findings into the final RCA report.

    Runs last in the pipeline after the Synthesis Agent completes.
    Produces the human-readable report the SRE reads and acts on.

    Args:
        state: Current incident state from LangGraph.

    Returns:
        Partial state update with final_report.
    """
    incident_id = state["incident_id"]
    logger.info(f"Report agent starting for incident {incident_id}")

    try:
        hypotheses = state.get("hypotheses", [])

        if not hypotheses:
            logger.warning(
                f"No hypotheses available for report on incident {incident_id}"
            )

        # Format the report via LLM
        report = await _format_report(
            hypotheses=hypotheses,
            description=state["description"],
            severity=state.get("severity"),
            log_findings=state.get("log_findings"),
            deploy_findings=state.get("deploy_findings"),
            incident_id=incident_id,
        )

        # Calculate analysis duration
        analysis_duration_seconds = None
        started_at = state.get("started_at") if "started_at" in state else None
        if started_at:
            try:
                started = datetime.fromisoformat(
                    str(started_at).replace("Z", "+00:00")
                )
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                analysis_duration_seconds = int(
                    (datetime.now(timezone.utc) - started).total_seconds()
                )
            except ValueError:
                logger.warning(
                    f"Could not parse started_at for duration calculation: "
                    f"{started_at}"
                )

        # Build the complete final report
        final_report = {
            "incident_id": incident_id,
            "summary": report["summary"],
            "timeline": report["timeline"],
            "root_causes": report["root_causes"],
            "immediate_fix": report["immediate_fix"],
            "prevention_note": report["prevention_note"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analysis_duration_seconds": analysis_duration_seconds,
            "errors_during_analysis": state.get("errors", []),
        }

        logger.info(
            f"Report generation complete for {incident_id} — "
            f"duration: {analysis_duration_seconds}s, "
            f"hypotheses: {len(hypotheses)}"
        )

        return {"final_report": final_report}

    except Exception as e:
        logger.error(
            f"Report agent failed for incident {incident_id}: {e}"
        )
        return {
            "final_report": {
                "incident_id": incident_id,
                "summary": "Report generation failed — review hypotheses manually",
                "timeline": [],
                "root_causes": state.get("hypotheses", []),
                "immediate_fix": None,
                "prevention_note": None,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "analysis_duration_seconds": None,
                "errors_during_analysis": state.get("errors", []) + [
                    f"report: {str(e)}"
                ],
            },
            "errors": state.get("errors", []) + [f"report: {str(e)}"],
        }    