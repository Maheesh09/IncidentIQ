# models/incident.py
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import ARRAY, Integer, String, Text, ForeignKey, func, UniqueConstraint
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
    organisation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organisations.id"),
        nullable=True,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

class Organisation(Base):
    """ORM model for the organisations table.

    One row per customer organisation using IncidentIQ as a service.
    All incidents, reports, and feedback are scoped to an organisation.
    """

    __tablename__ = "organisations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_email: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Integer, nullable=False, default=1
    )
    created_at: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=func.now()
    )

class APIKey(Base):
    """ORM model for the api_keys table.

    Each organisation can have multiple API keys.
    Keys are hashed before storage — the raw key is shown only once
    at creation time and never stored in plaintext.
    """

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organisations.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    is_active: Mapped[bool] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=func.now()
    )
    last_used_at: Mapped[str | None] = mapped_column(String(50), nullable=True)        

class LogSourceConfig(Base):
    """ORM model for the log_source_configs table.

    Stores how to fetch logs for each organisation.
    Credentials are stored in Google Cloud Secret Manager —
    only the secret name is stored here, never the credentials themselves.
    """

    __tablename__ = "log_source_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organisations.id"),
        unique=True,
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    secret_name: Mapped[str] = mapped_column(String(255), nullable=False)
    config_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[str | None] = mapped_column(String(50), nullable=True)

class WebhookConfig(Base):
    """ORM model for the webhook_configs table.

    Stores where to deliver RCA reports for each organisation.
    When the pipeline completes, IncidentIQ POSTs the report
    to the customer's configured webhook URL.
    """

    __tablename__ = "webhook_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organisations.id"),
        unique=True,
        nullable=False,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    secret: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_delivered_at: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    last_delivery_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
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
    organisation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organisations.id"),
        nullable=True,
        index=True,
    )
    
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
    organisation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organisations.id"),
        nullable=True,
        index=True,
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
    organisation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organisations.id"),
        nullable=True,
        index=True,
    )

class NotificationConfig(Base):
    """ORM model for the notification_configs table.

    One row per channel per organisation. Supports Slack and PagerDuty.
    Credentials (webhook URL, routing key) are stored in Secret Manager;
    this row holds only the reference name and non-sensitive config.

    A single organisation can have both a Slack and a PagerDuty config
    simultaneously — the unique constraint is on (organisation_id, notification_type).
    """

    __tablename__ = "notification_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organisations.id"),
        nullable=False,
        index=True,
    )
    notification_type: Mapped[str] = mapped_column(
        String(20), nullable=False         # "slack" | "pagerduty"
    )
    secret_name: Mapped[str] = mapped_column(
        String(255), nullable=False        # GCP Secret Manager reference
    )
    config_metadata: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True               # e.g. {"channel": "#incidents"}
    )
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_notified_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_notification_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "notification_type",
            name="uq_notification_org_type",
        ),
    )    