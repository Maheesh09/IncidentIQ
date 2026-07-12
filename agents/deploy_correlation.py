# agents/deploy_correlation.py
from __future__ import annotations

import logging

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from config import settings
from pipeline.state import IncidentState
from tools.github_client import (
    fetch_commits_in_window,
    calculate_time_to_first_error,
    GitHubClientError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)

logger = logging.getLogger(__name__)

# Maximum commits to send to the LLM for reasoning
MAX_COMMITS_FOR_LLM = 10

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0.1,
    google_api_key=settings.gemini_api_key,
)

async def _reason_over_deploys(
    commits: list[dict],
    log_findings: dict | None,
) -> dict:
    """Use Gemini to reason over commits and correlate with log findings.

    Receives structured commit data and log findings — never raw logs.
    Reasons about whether any commit plausibly caused the observed errors.

    Args:
        commits: List of CommitInfo dicts from the GitHub client.
        log_findings: Structured findings from the Log Analysis Agent.

    Returns:
        Dict with correlation_confidence, verdict, and reasoning.
    """
    if not commits:
        return {
            "most_likely_commit_sha": None,
            "correlation_confidence": 0.0,
            "verdict": "No deployments found in the investigation window",
            "reasoning": "No commits were detected in the investigation window",
        }

    # Format commits for the prompt
    commits_text = ""
    for i, commit in enumerate(commits[:MAX_COMMITS_FOR_LLM]):
        risk_signals = (
            "\n      ".join(commit.get("risk_signals", []))
            or "None detected"
        )
        commits_text += f"""
Commit {i + 1}:
  SHA: {commit['short_sha']}
  Author: {commit['author']}
  Message: {commit['message']}
  Committed at: {commit['committed_at']}
  Changed files: {", ".join(commit.get("changed_files", []))}
  Additions: {commit.get("additions", 0)}, Deletions: {commit.get("deletions", 0)}
  Risk signals: {risk_signals}
  Time to first error: {commit.get("time_to_first_error_seconds", "unknown")} seconds
"""

    # Format log findings for context
    log_context = "No log findings available"
    if log_findings:
        log_context = f"""
Log summary: {log_findings.get("log_summary", "N/A")}
Likely failing component: {log_findings.get("likely_component", "unknown")}
Anomalies: {", ".join(log_findings.get("anomalies", []))}
First error timestamp: {log_findings.get("first_error_timestamp", "unknown")}
"""

    prompt = f"""You are an SRE analyst correlating deployments with a production incident.

Log analysis findings:
{log_context}

Deployments in the investigation window:
{commits_text}

Analyze whether any of these deployments likely caused the incident.
Respond with ONLY a JSON object.
No explanation, no markdown, no code fences — just the raw JSON.

{{
    "most_likely_commit_sha": "<short SHA of most suspicious commit, or null>",
    "correlation_confidence": <float between 0.0 and 1.0>,
    "verdict": "<one sentence conclusion about whether a deploy caused this>",
    "reasoning": "<detailed explanation of why this commit is or is not suspicious>"
}}

Confidence guidelines:
- 0.9-1.0: Very strong correlation — timing, file changes, and errors all align
- 0.7-0.9: Strong correlation — timing and at least one risk signal align
- 0.5-0.7: Moderate correlation — timing aligns but file changes seem unrelated
- 0.3-0.5: Weak correlation — a deployment exists but connection is unclear
- 0.0-0.3: No meaningful correlation found"""

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

        # Validate confidence is a valid float between 0 and 1
        confidence = float(parsed.get("correlation_confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))

        return {
            "most_likely_commit_sha": parsed.get("most_likely_commit_sha"),
            "correlation_confidence": round(confidence, 2),
            "verdict": parsed.get("verdict", ""),
            "reasoning": parsed.get("reasoning", ""),
        }

    except Exception as e:
        logger.error(f"Deploy correlation LLM reasoning failed: {e}")
        return {
            "most_likely_commit_sha": None,
            "correlation_confidence": 0.0,
            "verdict": "LLM reasoning failed — manual correlation required",
            "reasoning": "",
        }

async def correlate_deploys_node(state: IncidentState) -> dict:
    """LangGraph node — fetch deployments and correlate with incident.

    Runs in parallel with the Log Analysis Agent after Triage.
    Uses GitHub client to fetch commits, then LLM for causal reasoning.

    Args:
        state: Current incident state from LangGraph.

    Returns:
        Partial state update with deploy_findings.
    """
    incident_id = state["incident_id"]
    logger.info(f"Deploy correlation agent starting for incident {incident_id}")

    try:
        investigation_window = state.get("investigation_window")

        if not investigation_window:
            logger.warning(
                f"No investigation window for incident {incident_id}"
            )
            return {
                "deploy_findings": None,
                "errors": state.get("errors", []) + [
                    "deploy_correlation: no investigation window available"
                ],
            }

        # Step 1 — deterministic: fetch commits from GitHub
        try:
            commits = await fetch_commits_in_window(
                github_repo_url=state["github_repo_url"],
                window_start=investigation_window["start"],
                window_end=investigation_window["end"],
            )
        except GitHubNotFoundError:
            logger.error(
                f"Repository not found for incident {incident_id}: "
                f"{state['github_repo_url']}"
            )
            return {
                "deploy_findings": None,
                "errors": state.get("errors", []) + [
                    f"deploy_correlation: repository not found — "
                    f"{state['github_repo_url']}"
                ],
            }
        except GitHubRateLimitError:
            logger.warning(
                f"GitHub rate limit hit for incident {incident_id}"
            )
            return {
                "deploy_findings": None,
                "errors": state.get("errors", []) + [
                    "deploy_correlation: GitHub rate limit exceeded"
                ],
            }
        except GitHubClientError as e:
            logger.error(
                f"GitHub client error for incident {incident_id}: {e}"
            )
            return {
                "deploy_findings": None,
                "errors": state.get("errors", []) + [
                    f"deploy_correlation: GitHub error — {str(e)}"
                ],
            }

        logger.info(
            f"Fetched {len(commits)} commits for incident {incident_id}"
        )

        # Step 2 — deterministic: calculate time to first error per commit
        log_findings = state.get("log_findings")
        first_error_timestamp = (
            log_findings.get("first_error_timestamp")
            if log_findings
            else None
        )

        enriched_commits = []
        for commit in commits:
            time_to_error = None
            if first_error_timestamp:
                time_to_error = calculate_time_to_first_error(
                    committed_at=commit["committed_at"],
                    first_error_timestamp=first_error_timestamp,
                )
            enriched_commits.append({
                **commit,
                "time_to_first_error_seconds": time_to_error,
            })

        # Step 3 — LLM: reason over commits and correlate with log findings
        llm_result = await _reason_over_deploys(
            commits=enriched_commits,
            log_findings=log_findings,
        )

        deploy_findings = {
            "commits_found": len(commits),
            "commits": enriched_commits,
            "most_likely_commit_sha": llm_result["most_likely_commit_sha"],
            "correlation_confidence": llm_result["correlation_confidence"],
            "verdict": llm_result["verdict"],
            "reasoning": llm_result["reasoning"],
        }

        logger.info(
            f"Deploy correlation complete for {incident_id} — "
            f"{len(commits)} commits found, "
            f"confidence: {llm_result['correlation_confidence']}"
        )

        return {"deploy_findings": deploy_findings}

    except Exception as e:
        logger.error(
            f"Deploy correlation agent failed for incident {incident_id}: {e}"
        )
        return {
            "deploy_findings": None,
            "errors": state.get("errors", []) + [
                f"deploy_correlation: {str(e)}"
            ],
        }        