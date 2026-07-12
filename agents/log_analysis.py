# agents/log_analysis.py
from __future__ import annotations

import logging

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from config import settings
from pipeline.state import IncidentState
from tools.log_parser import parse_logs

logger = logging.getLogger(__name__)

# Maximum error lines to include in the LLM prompt
MAX_ERROR_LINES_FOR_LLM = 50

# Maximum stack traces to include in the LLM prompt
MAX_STACK_TRACES_FOR_LLM = 10

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",
    temperature=0.1,
    google_api_key=settings.gemini_api_key,
)

async def _reason_over_logs(
    error_patterns: list[str],
    stack_traces: list[str],
    error_frequency: dict | None,
    affected_services: list[str] | None,
) -> dict:
    """Use Gemini to reason over extracted log signals.

    Receives only structured signals from the log parser — never raw logs.
    The parser has already reduced 50,000 lines to the relevant signals.

    Args:
        error_patterns: Deduplicated error lines from the log parser.
        stack_traces: Stack trace lines extracted from the log file.
        error_frequency: Error counts before and after the window start.
        affected_services: Services identified by the Triage Agent.

    Returns:
        Dict with anomalies, log_summary, and reasoning.
    """
    # Format error frequency for the prompt
    frequency_text = "Not available"
    if error_frequency:
        frequency_text = (
            f"Before incident window: {error_frequency['before_window']} errors\n"
            f"After incident window: {error_frequency['after_window']} errors\n"
            f"Spike ratio: {error_frequency['spike_ratio']}x increase"
        )

    # Format error patterns for the prompt
    patterns_text = "\n".join(
        f"{i + 1}. {pattern}"
        for i, pattern in enumerate(error_patterns[:MAX_ERROR_LINES_FOR_LLM])
    )

    # Format stack traces for the prompt
    traces_text = "\n---\n".join(
        stack_traces[:MAX_STACK_TRACES_FOR_LLM]
    ) or "No stack traces found"

    services_text = ", ".join(affected_services) if affected_services else "Unknown"

    prompt = f"""You are an SRE analyst performing log analysis for a production incident.

Affected services: {services_text}

Error frequency analysis:
{frequency_text}

Unique error patterns detected:
{patterns_text}

Stack traces:
{traces_text}

Based on the above extracted signals, respond with ONLY a JSON object.
No explanation, no markdown, no code fences — just the raw JSON.

{{
    "anomalies": [
        "<description of anomaly 1>",
        "<description of anomaly 2>"
    ],
    "log_summary": "<2-3 sentence plain English summary of what the logs show>",
    "likely_component": "<the specific class, service, or component most likely failing>",
    "reasoning": "<your reasoning about what these patterns indicate>"
}}"""

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
            "anomalies": parsed.get("anomalies", []),
            "log_summary": parsed.get("log_summary", ""),
            "likely_component": parsed.get("likely_component", "unknown"),
            "reasoning": parsed.get("reasoning", ""),
        }

    except Exception as e:
        logger.error(f"Log analysis LLM reasoning failed: {e}")
        return {
            "anomalies": [],
            "log_summary": "LLM reasoning failed — see raw error patterns for manual analysis",
            "likely_component": "unknown",
            "reasoning": "",
        }
    
async def analyze_logs_node(state: IncidentState) -> dict:
    """LangGraph node — parse logs and reason over extracted signals.

    Runs in parallel with the Deploy Correlation Agent after Triage.
    Uses deterministic log parser first, then LLM for reasoning.

    Args:
        state: Current incident state from LangGraph.

    Returns:
        Partial state update with log_findings.
    """
    incident_id = state["incident_id"]
    logger.info(f"Log analysis agent starting for incident {incident_id}")

    try:
        raw_logs = state["raw_logs"]
        investigation_window = state.get("investigation_window")

        if not raw_logs:
            logger.warning(f"No logs available for incident {incident_id}")
            return {
                "log_findings": None,
                "errors": state.get("errors", []) + [
                    "log_analysis: no raw logs available"
                ],
            }

        # Step 1 — deterministic: parse logs and extract signals
        window_start = (
            investigation_window["start"]
            if investigation_window
            else None
        )

        parser_result = parse_logs(
            raw_logs=raw_logs,
            window_start=window_start,
        )

        logger.info(
            f"Log parser complete for {incident_id} — "
            f"{parser_result['total_lines']} total lines, "
            f"{len(parser_result['error_lines'])} error lines"
        )

        # Step 2 — LLM: reason over extracted signals
        llm_result = await _reason_over_logs(
            error_patterns=parser_result["error_patterns"],
            stack_traces=parser_result["stack_traces"],
            error_frequency=parser_result["error_frequency"],
            affected_services=state.get("affected_services"),
        )

        # Combine deterministic and LLM results into log_findings
        log_findings = {
            "total_lines": parser_result["total_lines"],
            "error_count": len(parser_result["error_lines"]),
            "first_error_timestamp": parser_result["first_error_timestamp"],
            "error_frequency": parser_result["error_frequency"],
            "error_patterns": parser_result["error_patterns"],
            "stack_traces": parser_result["stack_traces"],
            "anomalies": llm_result["anomalies"],
            "log_summary": llm_result["log_summary"],
            "likely_component": llm_result["likely_component"],
            "reasoning": llm_result["reasoning"],
        }

        logger.info(
            f"Log analysis complete for {incident_id} — "
            f"first error: {parser_result['first_error_timestamp']}, "
            f"anomalies: {len(llm_result['anomalies'])}"
        )

        return {"log_findings": log_findings}

    except Exception as e:
        logger.error(
            f"Log analysis agent failed for incident {incident_id}: {e}"
        )
        return {
            "log_findings": None,
            "errors": state.get("errors", []) + [f"log_analysis: {str(e)}"],
        }    