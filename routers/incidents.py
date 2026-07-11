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