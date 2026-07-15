# models/management_schemas.py
from __future__ import annotations

from pydantic import BaseModel, HttpUrl, Field



# POST /management/organisations
class OrganisationRequest(BaseModel):
    """Request body for registering a new organisation."""

    name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Organisation display name",
        examples=["Acme Corp SRE Team"]
    )
    admin_email: str = Field(
        ...,
        description="Admin contact email for the organisation",
        examples=["sre-admin@acme.com"]
    )


class OrganisationResponse(BaseModel):
    """Response returned after successfully registering an organisation.

    The api_key field is shown exactly once — it cannot be retrieved again.
    """

    organisation_id: str
    name: str
    api_key: str
    key_prefix: str
    message: str



# POST /management/log-source
class LogSourceRequest(BaseModel):
    """Request body for configuring a log source connector."""

    source_type: str = Field(
        ...,
        pattern="^(gcp|aws|datadog|manual)$",
        description="Log source type",
        examples=["gcp"]
    )
    credentials: dict = Field(
        ...,
        description="Credentials for the log source — stored in Secret Manager",
        examples=[{"project_id": "my-gcp-project", "service_account_key": "..."}]
    )
    config_metadata: dict | None = Field(
        default=None,
        description="Non-sensitive configuration like project IDs and log filters",
        examples=[{"project_id": "my-gcp-project", "log_filter": "severity>=ERROR"}]
    )


class LogSourceResponse(BaseModel):
    """Response returned after configuring a log source."""

    organisation_id: str
    source_type: str
    secret_name: str
    message: str



# POST /management/webhook
class WebhookRequest(BaseModel):
    """Request body for configuring a webhook delivery endpoint."""

    url: HttpUrl = Field(
        ...,
        description="URL to POST RCA reports to when analysis completes",
        examples=["https://your-system.com/rca-webhook"]
    )
    secret: str = Field(
        ...,
        min_length=16,
        description="Signing secret for HMAC-SHA256 webhook verification",
        examples=["your-webhook-signing-secret"]
    )


class WebhookResponse(BaseModel):
    """Response returned after configuring a webhook."""

    organisation_id: str
    webhook_url: str
    message: str



# GET /management/organisations/me
class OrganisationDetailsResponse(BaseModel):
    """Response for getting current organisation details."""

    organisation_id: str
    name: str
    log_source_type: str | None
    webhook_configured: bool
    created_at: str