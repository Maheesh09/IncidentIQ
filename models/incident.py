# models/incident.py
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import ARRAY, Integer, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from database import Base


class Incident(Base):
    """ORM model for the incidents table.

    Represents a single production incident submitted for RCA analysis.
    Status transitions: pending -> processing -> completed | failed
    """

    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    github_repo_url: Mapped[str] = mapped_column(Text, nullable=False)
    reported_at: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    incident_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    affected_services: Mapped[list | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    investigation_window: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    started_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    analysis_duration_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        String(50), nullable=False, server_default=func.now()
    )

class AgentRun(Base):
    """ORM model for the agent_runs table.

    One row per agent per incident. Tracks what each agent found,
    how long it took, and whether it succeeded or errored.
    """

    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("incidents.id"), nullable=False
    )
    agent_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    findings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
class RCAReport(Base):
    """ORM model for the rca_reports table.

    One row per incident (enforced by unique=True on incident_id).
    Stores the final structured RCA report produced by the Report Agent.
    """

    __tablename__ = "rca_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("incidents.id"), unique=True, nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    timeline: Mapped[dict] = mapped_column(JSONB, nullable=False)
    hypotheses: Mapped[dict] = mapped_column(JSONB, nullable=False)
    prevention_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    generated_at: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=func.now()
    )    

class Feedback(Base):
    """ORM model for the feedback table.

    One row per incident (enforced by unique=True on incident_id).
    Stores SRE confirmation or rejection of the RCA hypothesis.
    Used in Phase 2 to calibrate synthesis agent prompts.
    """

    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("incidents.id"), unique=True, nullable=False
    )
    hypothesis_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    verdict: Mapped[str] = mapped_column(String(20), nullable=False)
    actual_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=func.now()
    )    