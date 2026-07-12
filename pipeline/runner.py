# pipeline/runner.py
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from models.incident import AgentRun, Incident, RCAReport
from pipeline.graph import build_graph
from pipeline.state import IncidentState

logger = logging.getLogger(__name__)

# Build the graph once at module level — not on every run
pipeline = build_graph()


async def run_pipeline(
    incident_id: str,
    description: str,
    raw_logs: str,
    github_repo_url: str,
    reported_at: str,
) -> None:
    """Execute the full LangGraph pipeline for an incident.

    Runs as a FastAPI background task — not in the request/response cycle.
    Updates the incident status in the database when complete.

    Args:
        incident_id: The incident ID to analyse.
        description: Plain English incident description.
        raw_logs: Raw log file content as a string.
        github_repo_url: GitHub repository URL.
        reported_at: ISO format string of when the incident was reported.
    """
    logger.info(f"Pipeline starting for incident {incident_id}")

    async with AsyncSessionLocal() as db:
        try:
            # Build the initial state
            initial_state: IncidentState = {
                "incident_id": incident_id,
                "description": description,
                "raw_logs": raw_logs,
                "github_repo_url": github_repo_url,
                "reported_at": reported_at,
                "severity": None,
                "affected_services": None,
                "investigation_window": None,
                "incident_type": None,
                "log_findings": None,
                "deploy_findings": None,
                "hypotheses": None,
                "final_report": None,
                "errors": [],
            }

            # Run the full pipeline
            final_state = await pipeline.ainvoke(initial_state)

            # Persist the final report to the database
            final_report = final_state.get("final_report")

            if final_report:
                report = RCAReport(
                    incident_id=incident_id,
                    summary=final_report.get("summary", ""),
                    timeline=final_report.get("timeline", []),
                    hypotheses=final_report.get("root_causes", []),
                    prevention_note=final_report.get("prevention_note"),
                    raw_report=final_report,
                    generated_at=datetime.now(timezone.utc).isoformat(),
                )
                db.add(report)

            # Update incident status to completed
            result = await db.execute(
                __import__("sqlalchemy").select(Incident).where(
                    Incident.id == incident_id
                )
            )
            incident = result.scalar_one_or_none()

            if incident:
                incident.status = "completed"
                incident.severity = final_state.get("severity")
                incident.incident_type = final_state.get("incident_type")
                incident.affected_services = final_state.get("affected_services")
                incident.investigation_window = final_state.get(
                    "investigation_window"
                )
                incident.completed_at = datetime.now(timezone.utc).isoformat()
                incident.analysis_duration_seconds = (
                    final_report.get("analysis_duration_seconds")
                    if final_report
                    else None
                )

            await db.commit()
            logger.info(f"Pipeline completed successfully for incident {incident_id}")

        except Exception as e:
            logger.error(f"Pipeline failed for incident {incident_id}: {e}")

            # Mark the incident as failed in the database
            try:
                result = await db.execute(
                    __import__("sqlalchemy").select(Incident).where(
                        Incident.id == incident_id
                    )
                )
                incident = result.scalar_one_or_none()
                if incident:
                    incident.status = "failed"
                    incident.completed_at = datetime.now(timezone.utc).isoformat()
                await db.commit()
            except Exception as db_error:
                logger.error(
                    f"Failed to mark incident {incident_id} as failed: {db_error}"
                )