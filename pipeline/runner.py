# pipeline/runner.py
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from pipeline.graph import build_graph
from pipeline.state import IncidentState
from tools.connectors import get_connector
from utils.secret_manager import retrieve_secret
from models.incident import AgentRun, Incident, LogSourceConfig, RCAReport, WebhookConfig
from utils.webhook import deliver_webhook

logger = logging.getLogger(__name__)

# Build the graph once at module level — not on every run
pipeline = build_graph()


async def run_pipeline(
    incident_id: str,
    description: str,
    raw_logs: str,
    github_repo_url: str,
    reported_at: str,
    organisation_id: str | None = None,
) -> None:
    """Execute the full LangGraph pipeline for an incident.

    Runs as a FastAPI background task — not in the request/response cycle.
    Fetches logs via connector if organisation has one configured.
    Updates the incident status in the database when complete.

    Args:
        incident_id: The incident ID to analyse.
        description: Plain English incident description.
        raw_logs: Manually uploaded log content (used as fallback).
        github_repo_url: GitHub repository URL.
        reported_at: ISO format string of when the incident was reported.
        organisation_id: Organisation UUID string, or None for legacy runs.
    """
    logger.info(f"Pipeline starting for incident {incident_id}")

    # Fetch logs via connector if available
    logs_to_analyse = await _fetch_logs_for_incident(
        organisation_id=organisation_id,
        raw_logs=raw_logs,
        reported_at=reported_at,
    )

    async with AsyncSessionLocal() as db:
        try:
            initial_state: IncidentState = {
                "incident_id": incident_id,
                "description": description,
                "raw_logs": logs_to_analyse,
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

            # Deliver webhook after committing the report
            if final_report:
                await _deliver_webhook_for_org(
                    organisation_id=organisation_id,
                    incident_id=incident_id,
                    final_report=final_report,
                )

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

async def _fetch_logs_for_incident(
    organisation_id: str | None,
    raw_logs: str,
    reported_at: str,
) -> str:
    """Fetch logs using the organisation's configured log source connector.

    If the organisation has a log source configured, fetches logs
    automatically. Falls back to manual upload logs if not configured
    or if fetching fails.

    Args:
        organisation_id: The organisation's UUID string, or None.
        raw_logs: Manually uploaded log content as fallback.
        reported_at: ISO format incident reported time for window calc.

    Returns:
        Log content as a plain string ready for the pipeline.
    """
    if not organisation_id:
        logger.info("No organisation_id — using manual logs")
        return raw_logs

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(LogSourceConfig).where(
                LogSourceConfig.organisation_id
                == __import__("uuid").UUID(organisation_id),
                LogSourceConfig.is_active == 1,
            )
        )
        log_source = result.scalar_one_or_none()

    if not log_source or log_source.source_type == "manual":
        logger.info(
            f"Org {organisation_id} using manual log upload"
        )
        return raw_logs

    # Fetch credentials from Secret Manager
    try:
        credentials = await retrieve_secret(log_source.secret_name)
    except RuntimeError as e:
        logger.error(
            f"Failed to retrieve credentials for org {organisation_id}: {e}"
            f" — falling back to manual logs"
        )
        return raw_logs

    # Calculate a basic window for log fetching
    try:
        from datetime import timedelta
        reported = datetime.fromisoformat(
            reported_at.replace("Z", "+00:00")
        )
        window_start = (reported - timedelta(minutes=30)).isoformat()
        window_end = reported.isoformat()
    except ValueError:
        window_start = reported_at
        window_end = reported_at

    # Build the connector and fetch logs
    try:
        connector = await get_connector(
            source_type=log_source.source_type,
            credentials=credentials,
        )

        service_name = (
            log_source.config_metadata.get("service_name", "unknown")
            if log_source.config_metadata
            else "unknown"
        )

        fetched_logs = await connector.fetch_logs(
            service_name=service_name,
            window_start=window_start,
            window_end=window_end,
        )

        if fetched_logs:
            logger.info(
                f"Fetched {len(fetched_logs)} chars of logs "
                f"via {log_source.source_type} connector "
                f"for org {organisation_id}"
            )
            return fetched_logs

        logger.warning(
            f"Connector returned empty logs for org {organisation_id} "
            f"— falling back to manual logs"
        )
        return raw_logs

    except Exception as e:
        logger.error(
            f"Connector failed for org {organisation_id}: {e} "
            f"— falling back to manual logs"
        )
        return raw_logs
    
async def _deliver_webhook_for_org(
    organisation_id: str | None,
    incident_id: str,
    final_report: dict,
) -> None:
    """Deliver RCA report webhook for the organisation if configured.

    Fetches the organisation's webhook config and delivers the report.
    Updates last_delivered_at and last_delivery_status in the database.

    Args:
        organisation_id: The organisation's UUID string, or None.
        incident_id: The incident ID for the report.
        final_report: The complete RCA report dict.
    """
    if not organisation_id:
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WebhookConfig).where(
                WebhookConfig.organisation_id
                == __import__("uuid").UUID(organisation_id),
                WebhookConfig.is_active == 1,
            )
        )
        webhook_config = result.scalar_one_or_none()

        if not webhook_config:
            logger.info(
                f"No webhook configured for org {organisation_id}"
            )
            return

        logger.info(
            f"Delivering webhook for incident {incident_id} "
            f"to {webhook_config.url}"
        )

        success = await deliver_webhook(
            url=webhook_config.url,
            secret=webhook_config.secret,
            incident_id=incident_id,
            report=final_report,
        )

        # Update delivery status in database
        webhook_config.last_delivered_at = (
            datetime.now(timezone.utc).isoformat()
        )
        webhook_config.last_delivery_status = (
            "success" if success else "failed"
        )
        await db.commit()

        if success:
            logger.info(
                f"Webhook delivered for incident {incident_id}"
            )
        else:
            logger.error(
                f"Webhook delivery failed for incident {incident_id}"
            )    