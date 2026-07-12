# pipeline/state.py
from __future__ import annotations

from datetime import datetime
from typing import TypedDict


class IncidentState(TypedDict):
    """Shared state object that flows through every node in the LangGraph pipeline.

    Each agent reads what it needs and writes only its own outputs.
    Fields are optional until the agent responsible for them runs.
    """

    # --- Input fields (set before pipeline starts) ---
    incident_id: str
    description: str
    raw_logs: str
    github_repo_url: str
    reported_at: str

    # --- Set by Triage Agent ---
    severity: str | None
    affected_services: list[str] | None
    investigation_window: dict[str, str] | None
    incident_type: str | None

    # --- Set by Log Analysis Agent ---
    log_findings: dict | None

    # --- Set by Deploy Correlation Agent ---
    deploy_findings: dict | None

    # --- Set by Synthesis Agent ---
    hypotheses: list[dict] | None

    # --- Set by Report Agent ---
    final_report: dict | None

    # --- Error tracking (any agent can append here) ---
    errors: list[str]