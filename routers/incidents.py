# routers/incidents.py
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models.incident import AgentRun, Feedback, Incident, RCAReport
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
    db: AsyncSession = Depends(get_db),
) -> IncidentResponse:
    """Create a new incident and queue it for RCA analysis.

    Returns 202 Accepted immediately — analysis runs in the background.
    The caller uses GET /incidents/{id} to poll for progress.
    """
    # Generate a human-readable incident ID
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    unique_suffix = str(uuid.uuid4())[:8].upper()
    incident_id = f"INC-{date_str}-{unique_suffix}"

    # Create the incident record in the database
    incident = Incident(
        id=incident_id,
        description=request.description,
        github_repo_url=str(request.github_repo_url),
        reported_at=request.reported_at.isoformat(),
        status="pending",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(incident)
    await db.flush()

    logger.info(f"Incident {incident_id} created — queued for analysis")

    return IncidentResponse(
        incident_id=incident_id,
        status="pending",
        message="Incident created. Upload logs via POST /incidents/{id}/logs to start analysis.",
    )

@router.post("/{incident_id}/logs", response_model=LogUploadResponse, status_code=200)
async def upload_logs(
    incident_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> LogUploadResponse:
    """Upload a raw log file for an existing incident.

    Stores the log content on the incident record and updates
    status to 'processing' to trigger the analysis pipeline.
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

    # Store log content and update status
    incident.investigation_window = {"raw_logs": content.decode("utf-8", errors="replace")}
    incident.status = "processing"
    incident.started_at = datetime.now(timezone.utc).isoformat()

    logger.info(f"Logs uploaded for incident {incident_id} — {log_size_bytes} bytes")

    return LogUploadResponse(
        incident_id=incident_id,
        log_size_bytes=log_size_bytes,
        status="processing",
    )