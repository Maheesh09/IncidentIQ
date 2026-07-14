# pipeline/runner.py
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
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
    Tracks each agent's execution in the agent_runs table.
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

            # Record pipeline-level agent runs before invocation
            agent_runs: dict[str, AgentRun] = {}
            for agent_type in [
                "triage",
                "log_analysis",
                "deploy_correlation",
                "synthesis",
                "report",
            ]:
                agent_runs[agent_type] = await _record_agent_start(
                    db, incident_id, agent_type
                )
            await db.commit()

            # Run the full pipeline
            final_state = await pipeline.ainvoke(initial_state)

            # Determine success or failure per agent from final state
            errors = final_state.get("errors", [])

            await _record_agent_finish(
                db, agent_runs["triage"],
                status="completed" if not any("triage" in e for e in errors) else "failed",
                findings={
                    "severity": final_state.get("severity"),
                    "incident_type": final_state.get("incident_type"),
                    "affected_services": final_state.get("affected_services"),
                    "investigation_window": final_state.get("investigation_window"),
                },
                error_message=next(
                    (e for e in errors if "triage" in e), None
                ),
            )

            await _record_agent_finish(
                db, agent_runs["log_analysis"],
                status="completed" if final_state.get("log_findings") else "failed",
                findings=final_state.get("log_findings"),
                error_message=next(
                    (e for e in errors if "log_analysis" in e), None
                ),
            )

            await _record_agent_finish(
                db, agent_runs["deploy_correlation"],
                status="completed" if final_state.get("deploy_findings") else "failed",
                findings=final_state.get("deploy_findings"),
                error_message=next(
                    (e for e in errors if "deploy_correlation" in e), None
                ),
            )

            await _record_agent_finish(
                db, agent_runs["synthesis"],
                status="completed" if final_state.get("hypotheses") else "failed",
                findings={"hypotheses": final_state.get("hypotheses")},
                error_message=next(
                    (e for e in errors if "synthesis" in e), None
                ),
            )

            await _record_agent_finish(
                db, agent_runs["report"],
                status="completed" if final_state.get("final_report") else "failed",
                findings=final_state.get("final_report"),
                error_message=next(
                    (e for e in errors if "report" in e), None
                ),
            )

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
                select(Incident).where(Incident.id == incident_id)
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
            logger.info(
                f"Pipeline completed successfully for incident {incident_id}"
            )

        except Exception as e:
            logger.error(f"Pipeline failed for incident {incident_id}: {e}")
            try:
                result = await db.execute(
                    select(Incident).where(Incident.id == incident_id)
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
                

async def _record_agent_start(
    db: AsyncSession,
    incident_id: str,
    agent_type: str,
) -> AgentRun:
    """Create an AgentRun record when an agent begins execution.

    Args:
        db: Active database session.
        incident_id: The incident being analysed.
        agent_type: Name of the agent starting (e.g. 'triage').

    Returns:
        The created AgentRun ORM object.
    """
    agent_run = AgentRun(
        incident_id=incident_id,
        agent_type=agent_type,
        status="running",
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(agent_run)
    await db.flush()
    return agent_run


async def _record_agent_finish(
    db: AsyncSession,
    agent_run: AgentRun,
    status: str,
    findings: dict | None = None,
    error_message: str | None = None,
) -> None:
    """Update an AgentRun record when an agent completes or fails.

    Args:
        db: Active database session.
        agent_run: The AgentRun object to update.
        status: Final status — 'completed' or 'failed'.
        findings: Structured output from the agent, if any.
        error_message: Error description if the agent failed.
    """
    completed_at = datetime.now(timezone.utc).isoformat()

    started = datetime.fromisoformat(agent_run.started_at)
    completed = datetime.fromisoformat(completed_at)
    duration_ms = int((completed - started).total_seconds() * 1000)

    agent_run.status = status
    agent_run.findings = findings
    agent_run.error_message = error_message
    agent_run.completed_at = completed_at
    agent_run.duration_ms = duration_ms

    await db.flush()                

    