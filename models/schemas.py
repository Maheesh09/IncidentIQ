# models/schemas.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, HttpUrl, Field

class IncidentRequest(BaseModel):
    """Request body for creating a new incident."""

    description: str = Field(
        ...,
        min_length=10,
        description="Plain English description of what is going wrong",
        examples=["Auth service returning 500s since 14:32"]
    )
    github_repo_url: HttpUrl = Field(
        ...,
        description="Full GitHub repository URL to correlate deployments against",
        examples=["https://github.com/org/repo"]
    )
    reported_at: datetime = Field(
        ...,
        description="Timestamp when the incident was first reported (ISO 8601)",
        examples=["2026-07-03T14:35:00Z"]
    )


class IncidentResponse(BaseModel):
    """Response body returned after successfully creating an incident."""

    incident_id: str
    status: str
    message: str


# POST /incidents/{id}/logs
class LogUploadResponse(BaseModel):
    """Response body returned after successfully uploading a log file."""

    incident_id: str
    log_size_bytes: int
    status: str


# GET /incidents/{id}
class AgentStatus(BaseModel):
    """Represents the current status of a single agent in the pipeline."""

    agent_type: str
    status: str


class IncidentStatusResponse(BaseModel):
    """Response body for polling the current status of an incident analysis."""

    incident_id: str
    status: str
    current_agent: str | None
    agents_completed: list[str]
    agents_pending: list[str]
    started_at: str | None
    elapsed_seconds: int | None    


# GET /incidents/{id}/report
class HypothesisSchema(BaseModel):
    """Represents a single ranked root cause hypothesis."""

    rank: int
    confidence: float
    root_cause: str
    evidence: list[str]
    reasoning: str


class RCAReportResponse(BaseModel):
    """Response body for the final RCA report."""

    incident_id: str
    summary: str
    timeline: list[str]
    root_causes: list[HypothesisSchema]
    immediate_fix: str | None
    prevention_note: str | None
    generated_at: str
    analysis_duration_seconds: int | None


# POST /incidents/{id}/feedback
class FeedbackRequest(BaseModel):
    """Request body for submitting SRE feedback on an RCA report."""

    hypothesis_rank: int = Field(
        ...,
        ge=1,
        description="Rank of the hypothesis being evaluated (1 = highest confidence)",
        examples=[1]
    )
    verdict: str = Field(
        ...,
        pattern="^(confirmed|rejected)$",
        description="Whether the hypothesis was correct",
        examples=["confirmed"]
    )
    actual_cause: str | None = Field(
        default=None,
        description="The real root cause — required when verdict is rejected",
        examples=["Redis connection pool was exhausted due to config change"]
    )


class FeedbackResponse(BaseModel):
    """Response body returned after feedback is recorded."""

    incident_id: str
    feedback_recorded: bool