# routers/incidents.py
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from pipeline.runner import run_pipeline
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models.incident import AgentRun, Feedback, Incident, LogSourceConfig, RCAReport
from models.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    IncidentRequest,
    IncidentResponse,
    IncidentStatusResponse,
    LogUploadResponse,
    RCAReportResponse,
    HypothesisSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/incidents", tags=["incidents"])

@router.post("/", response_model=IncidentResponse, status_code=202)
async def create_incident(
    request: IncidentRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,                    # raw ASGI request — gives us state from middleware
    db: AsyncSession = Depends(get_db),
) -> IncidentResponse:
    """Create a new incident and queue it for RCA analysis.

    Returns 202 Accepted immediately — analysis runs in the background.
    If org has a non-manual log source, pipeline starts immediately.
    The caller uses GET /incidents/{id} to poll for progress.
    """
    # Pull organisation_id stamped by APIKeyMiddleware
    organisation_id_str: str | None = getattr(http_request.state, "organisation_id", None)

    # Generate a human-readable incident ID
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    unique_suffix = str(uuid.uuid4())[:8].upper()
    incident_id = f"INC-{date_str}-{unique_suffix}"

    # Create the incident record — now with organisation_id stamped correctly
    incident = Incident(
        id=incident_id,
        description=request.description,
        github_repo_url=str(request.github_repo_url),
        reported_at=request.reported_at.isoformat(),
        status="pending",
        created_at=datetime.now(timezone.utc).isoformat(),
        organisation_id=uuid.UUID(organisation_id_str) if organisation_id_str else None,
    )
    db.add(incident)
    await db.flush()

    # Auto-trigger pipeline if org has a non-manual log source configured
    auto_triggered = False
    if organisation_id_str:
        log_source_result = await db.execute(
            select(LogSourceConfig).where(
                LogSourceConfig.organisation_id == uuid.UUID(organisation_id_str),
                LogSourceConfig.is_active == 1,
            )
        )
        log_source = log_source_result.scalar_one_or_none()

        if log_source and log_source.source_type != "manual":
            incident.status = "processing"
            incident.started_at = datetime.now(timezone.utc).isoformat()
            await db.flush()

            background_tasks.add_task(
                run_pipeline,
                incident_id=incident_id,
                description=request.description,
                raw_logs="",
                github_repo_url=str(request.github_repo_url),
                reported_at=request.reported_at.isoformat(),
                organisation_id=organisation_id_str,
            )
            auto_triggered = True

    logger.info(
        f"Incident {incident_id} created — "
        f"{'pipeline auto-triggered via connector' if auto_triggered else 'awaiting log upload'}"
    )

    message = (
        "Incident created. Analysis started automatically via your configured log source."
        if auto_triggered
        else "Incident created. Upload logs via POST /incidents/{id}/logs to start analysis."
    )

    return IncidentResponse(
        incident_id=incident_id,
        status="processing" if auto_triggered else "pending",
        message=message,
    )

@router.post("/{incident_id}/logs", response_model=LogUploadResponse, status_code=200)
async def upload_logs(
    incident_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> LogUploadResponse:
    """Upload a raw log file for an existing incident.

    Stores the log content on the incident record, updates status
    to 'processing', and triggers the LangGraph pipeline as a
    background task.
    """
    # Verify the incident exists
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail=f"Incident {incident_id} not found"
        )

    if incident.status not in ("pending",):
        raise HTTPException(
            status_code=409,
            detail=f"Incident {incident_id} already has logs uploaded"
        )

    # Read and validate file size
    content = await file.read()
    log_size_bytes = len(content)

    if log_size_bytes > settings.max_log_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Log file exceeds maximum size of {settings.max_log_size_bytes // (1024 * 1024)}MB"
        )

    # Decode log content
    raw_logs = content.decode("utf-8", errors="replace")

    # Update incident status and store started_at
    incident.status = "processing"
    incident.started_at = datetime.now(timezone.utc).isoformat()

    # Flush so the status update is visible before pipeline starts
    await db.flush()

    # Trigger the pipeline as a background task
    background_tasks.add_task(
        run_pipeline,
        incident_id=incident_id,
        description=incident.description,
        raw_logs=raw_logs,
        github_repo_url=incident.github_repo_url,
        reported_at=incident.reported_at,
        organisation_id=str(incident.organisation_id) if incident.organisation_id else None,
    )

    logger.info(
        f"Logs uploaded for incident {incident_id} — "
        f"{log_size_bytes} bytes — pipeline queued"
    )

    return LogUploadResponse(
        incident_id=incident_id,
        log_size_bytes=log_size_bytes,
        status="processing",
    )

@router.get("/{incident_id}", response_model=IncidentStatusResponse, status_code=200)
async def get_incident_status(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
) -> IncidentStatusResponse:
    """Poll the current analysis status of an incident.

    Returns pipeline progress including which agents have completed
    and which are still pending.
    """
    # Fetch the incident
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail=f"Incident {incident_id} not found"
        )

    # Fetch all agent runs for this incident
    agent_result = await db.execute(
        select(AgentRun).where(AgentRun.incident_id == incident_id)
    )
    agent_runs = agent_result.scalars().all()

    # Calculate completed and pending agents
    all_agents = ["triage", "log_analysis", "deploy_correlation", "synthesis", "report"]
    completed = [run.agent_type for run in agent_runs if run.status == "completed"]
    pending = [agent for agent in all_agents if agent not in completed]
    current_agent = next(
        (run.agent_type for run in agent_runs if run.status == "running"), None
    )

    # Calculate elapsed seconds
    elapsed_seconds = None
    if incident.started_at:
        started = datetime.fromisoformat(incident.started_at)
        elapsed_seconds = int(
            (datetime.now(timezone.utc) - started).total_seconds()
        )

    return IncidentStatusResponse(
        incident_id=incident_id,
        status=incident.status,
        current_agent=current_agent,
        agents_completed=completed,
        agents_pending=pending,
        started_at=incident.started_at,
        elapsed_seconds=elapsed_seconds,
        error_message=incident.error_message,
    )

@router.get("/{incident_id}/report", response_model=RCAReportResponse, status_code=200)
async def get_incident_report(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
) -> RCAReportResponse:
    """Retrieve the final RCA report for a completed incident.

    Only available when incident status is 'completed'.
    Returns 409 if analysis is still in progress.
    """
    # Fetch the incident
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail=f"Incident {incident_id} not found"
        )

    if incident.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Report not yet available — incident status is '{incident.status}'"
        )

    # Fetch the RCA report
    report_result = await db.execute(
        select(RCAReport).where(RCAReport.incident_id == incident_id)
    )
    report = report_result.scalar_one_or_none()

    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"Report for incident {incident_id} not found"
        )

    # Build hypothesis objects from JSONB data
    hypotheses = [
        HypothesisSchema(
            rank=h["rank"],
            confidence=h["confidence"],
            root_cause=h["root_cause"],
            evidence=h["evidence"],
            reasoning=h["reasoning"],
        )
        for h in report.hypotheses
    ]

    return RCAReportResponse(
        incident_id=incident_id,
        summary=report.summary,
        timeline=report.timeline,
        root_causes=hypotheses,
        immediate_fix=report.raw_report.get("immediate_fix") if report.raw_report else None,
        prevention_note=report.prevention_note,
        generated_at=report.generated_at,
        analysis_duration_seconds=incident.analysis_duration_seconds,
    )

@router.post("/{incident_id}/feedback", response_model=FeedbackResponse, status_code=200)
async def submit_feedback(
    incident_id: str,
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """Submit SRE feedback on an RCA report.

    Confirms or rejects the hypothesis after the incident is resolved.
    Used in Phase 2 to calibrate synthesis agent prompts.
    """
    # Fetch the incident
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail=f"Incident {incident_id} not found"
        )

    if incident.status != "completed":
        raise HTTPException(
            status_code=409,
            detail="Feedback can only be submitted for completed incidents"
        )

    # Check feedback hasn't already been submitted
    feedback_result = await db.execute(
        select(Feedback).where(Feedback.incident_id == incident_id)
    )
    existing_feedback = feedback_result.scalar_one_or_none()

    if existing_feedback is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Feedback already submitted for incident {incident_id}"
        )

    # Cross-field validation
    if request.verdict == "rejected" and not request.actual_cause:
        raise HTTPException(
            status_code=400,
            detail="actual_cause is required when verdict is 'rejected'"
        )

    # Store feedback
    feedback = Feedback(
        incident_id=incident_id,
        hypothesis_rank=request.hypothesis_rank,
        verdict=request.verdict,
        actual_cause=request.actual_cause,
        submitted_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(feedback)

    logger.info(
        f"Feedback recorded for incident {incident_id} — "
        f"verdict: {request.verdict}, rank: {request.hypothesis_rank}"
    )

    return FeedbackResponse(
        incident_id=incident_id,
        feedback_recorded=True,
    )