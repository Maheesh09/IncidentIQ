# agents/synthesis.py
from __future__ import annotations

import logging

from database import AsyncSession
from pipeline.calibration import fetch_calibration_context
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from config import settings
from pipeline.state import IncidentState

logger = logging.getLogger(__name__)

# Maximum hypotheses the Synthesis Agent will produce
MAX_HYPOTHESES = 3

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",
    temperature=0.1,
    google_api_key=settings.gemini_api_key,
)

async def _synthesize_findings(
    log_findings: dict | None,
    deploy_findings: dict | None,
    severity: str | None,
    incident_type: str | None,
    description: str,
    errors: list[str],
    callibration_context: str = "",
) -> list[dict]:
    """Use Gemini to synthesize findings into ranked hypotheses.

    Receives structured outputs from Log Analysis and Deploy Correlation.
    Builds causal hypotheses with confidence scores and evidence mapping.

    Args:
        log_findings: Structured output from the Log Analysis Agent.
        deploy_findings: Structured output from the Deploy Correlation Agent.
        severity: Incident severity from the Triage Agent.
        incident_type: Incident type from the Triage Agent.
        description: Original incident description from the SRE.
        errors: Any errors accumulated from previous agents.

    Returns:
        List of hypothesis dicts ranked by confidence score.
    """
    # Format log findings for the prompt
    log_context = "Log analysis was not available for this incident."
    if log_findings:
        log_context = f"""
Log summary: {log_findings.get("log_summary", "N/A")}
Likely failing component: {log_findings.get("likely_component", "unknown")}
First error timestamp: {log_findings.get("first_error_timestamp", "unknown")}
Anomalies detected:
{chr(10).join(f"  - {a}" for a in log_findings.get("anomalies", []))}
Error patterns (sample):
{chr(10).join(f"  - {p}" for p in log_findings.get("error_patterns", [])[:10])}
"""

    # Format deploy findings for the prompt
    deploy_context = "Deploy correlation was not available for this incident."
    if deploy_findings:
        commits_summary = ""
        for commit in deploy_findings.get("commits", [])[:5]:
            commits_summary += (
                f"\n  - [{commit['short_sha']}] {commit['message']} "
                f"by {commit['author']} at {commit['committed_at']}"
                f" ({commit.get('time_to_first_error_seconds', 'unknown')}s before first error)"
                f"\n    Risk signals: {', '.join(commit.get('risk_signals', [])) or 'none'}"
            )

        deploy_context = f"""
Deploy verdict: {deploy_findings.get("verdict", "N/A")}
Correlation confidence: {deploy_findings.get("correlation_confidence", 0.0)}
Most likely commit: {deploy_findings.get("most_likely_commit_sha", "none identified")}
Deploy reasoning: {deploy_findings.get("reasoning", "N/A")}
Commits in window:{commits_summary}
"""

    # Note any agent failures
    errors_context = ""
    if errors:
        errors_context = f"""
Note: The following agents encountered errors during analysis:
{chr(10).join(f"  - {e}" for e in errors)}
Factor this into your confidence scores.
"""

    prompt = f"""You are a senior SRE performing root cause analysis for a production incident.

{calibration_context}

Incident description: {description}
Severity: {severity or "unknown"}
Incident type: {incident_type or "unknown"}

Log analysis findings:
{log_context}

Deploy correlation findings:
{deploy_context}
{errors_context}

Based on all available evidence, generate up to {MAX_HYPOTHESES} ranked root cause hypotheses.
Respond with ONLY a JSON object.
No explanation, no markdown, no code fences — just the raw JSON.

{{
    "hypotheses": [
        {{
            "rank": 1,
            "confidence": <float 0.0-1.0>,
            "root_cause": "<specific, actionable root cause statement>",
            "evidence": [
                "<specific evidence item 1>",
                "<specific evidence item 2>"
            ],
            "reasoning": "<why this evidence points to this root cause>"
        }}
    ]
}}

Guidelines:
- Rank 1 must have the highest confidence score
- Evidence must reference specific facts from the findings above
- Root cause must be specific enough for an SRE to act on immediately
- If data is missing due to agent errors, lower confidence scores accordingly
- Never invent evidence — only reference what is present in the findings"""

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
        hypotheses = parsed.get("hypotheses", [])

        # Validate and sanitize each hypothesis
        validated = []
        for h in hypotheses[:MAX_HYPOTHESES]:
            confidence = float(h.get("confidence", 0.0))
            confidence = max(0.0, min(1.0, confidence))
            validated.append({
                "rank": int(h.get("rank", len(validated) + 1)),
                "confidence": round(confidence, 2),
                "root_cause": str(h.get("root_cause", "")),
                "evidence": list(h.get("evidence", [])),
                "reasoning": str(h.get("reasoning", "")),
            })

        # Sort by confidence descending and re-rank
        validated.sort(key=lambda x: x["confidence"], reverse=True)
        for i, h in enumerate(validated):
            h["rank"] = i + 1

        return validated

    except Exception as e:
        logger.error(f"Synthesis LLM reasoning failed: {e}")
        return [{
            "rank": 1,
            "confidence": 0.0,
            "root_cause": "Synthesis failed — manual analysis required",
            "evidence": [],
            "reasoning": f"LLM reasoning error: {str(e)}",
        }]

async def synthesize_node(state: IncidentState) -> dict:
    """LangGraph node — synthesize all findings into ranked hypotheses.

    Runs after both Log Analysis and Deploy Correlation finish (fan-in).
    Combines structured findings from both agents into causal hypotheses.
    Injects past SRE feedback as calibration context.

    Args:
        state: Current incident state from LangGraph.

    Returns:
        Partial state update with hypotheses.
    """
    incident_id = state["incident_id"]
    logger.info(f"Synthesis agent starting for incident {incident_id}")

    try:
        log_findings = state.get("log_findings")
        deploy_findings = state.get("deploy_findings")
        errors = state.get("errors", [])

        if not log_findings and not deploy_findings:
            logger.warning(
                f"No findings available for synthesis on incident {incident_id}"
            )

        # Fetch calibration context from past feedback
        calibration_context = ""
        async with AsyncSessionLocal() as db:
            calibration_context = await fetch_calibration_context(
                db=db,
                incident_type=state.get("incident_type"),
                severity=state.get("severity"),
            )

        hypotheses = await _synthesize_findings(
            log_findings=log_findings,
            deploy_findings=deploy_findings,
            severity=state.get("severity"),
            incident_type=state.get("incident_type"),
            description=state["description"],
            errors=errors,
            calibration_context=calibration_context,
        )

        logger.info(
            f"Synthesis complete for {incident_id} — "
            f"{len(hypotheses)} hypotheses generated, "
            f"top confidence: {hypotheses[0]['confidence'] if hypotheses else 0.0}"
        )

        return {"hypotheses": hypotheses}

    except Exception as e:
        logger.error(
            f"Synthesis agent failed for incident {incident_id}: {e}"
        )
        return {
            "hypotheses": [{
                "rank": 1,
                "confidence": 0.0,
                "root_cause": "Synthesis agent failed — manual analysis required",
                "evidence": [],
                "reasoning": str(e),
            }],
            "errors": state.get("errors", []) + [f"synthesis: {str(e)}"],
        }        