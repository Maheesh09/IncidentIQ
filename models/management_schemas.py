# models/management_schemas.py
from __future__ import annotations
import re

from pydantic import BaseModel, HttpUrl, Field, EmailStr, field_validator



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
    admin_email: EmailStr = Field(
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
    admin_email: EmailStr
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
    @field_validator("config_metadata")
    @classmethod
    def validate_service_name(cls, value: dict | None) -> dict | None:
        """Reject service names containing query-syntax metacharacters.

        service_name is interpolated directly into GCP and Datadog filter
        expressions. Restricting it to a conservative character set closes
        the injection path at the point of configuration rather than in
        each connector.

        Args:
            value: The config_metadata dict, or None.

        Returns:
            The validated dict unchanged.

        Raises:
            ValueError: If service_name contains disallowed characters.
        """
        if not value:
            return value

        service_name = value.get("service_name")
        if service_name is None:
            return value

        if not isinstance(service_name, str):
            raise ValueError("service_name must be a string")

        if not re.fullmatch(r"[A-Za-z0-9._\-/]{1,128}", service_name):
            raise ValueError(
                "service_name may only contain letters, digits, and the "
                "characters . _ - / (max 128 chars)"
            )

        return value


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
    admin_email: EmailStr | None = None
    log_source_type: str | None
    webhook_configured: bool
    created_at: str