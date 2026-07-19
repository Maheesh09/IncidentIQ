# models/management_schemas.py
from __future__ import annotations
import re

from pydantic import BaseModel, HttpUrl, Field, EmailStr, field_validator
from typing import Any
# POST /management/notifications
VALID_NOTIFICATION_TYPES = {"slack", "pagerduty"}

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
    """Current organisation details and configuration status."""

    organisation_id: str
    name: str
    admin_email: str | None
    log_source_type: str | None
    webhook_configured: bool
    slack_configured: bool = False
    slack_last_notified_at: str | None = None
    slack_last_status: str | None = None
    pagerduty_configured: bool = False
    pagerduty_last_notified_at: str | None = None
    pagerduty_last_status: str | None = None
    created_at: str


class NotificationRequest(BaseModel):
    """Request body for configuring a Slack or PagerDuty notification channel.

    One organisation can have both channels configured simultaneously.
    Credentials are stored in Secret Manager — never in the database.

    Slack requires:
        credentials: {"webhook_url": "https://hooks.slack.com/services/..."}
        config_metadata: {"channel": "#incidents"}  (informational only)

    PagerDuty requires:
        credentials: {"routing_key": "<32-char hex integration key>"}
        config_metadata: {"service_name": "Auth Service"}  (used in alert title)
    """

    notification_type: str = Field(
        ...,
        description="Notification channel type",
        examples=["slack", "pagerduty"],
    )
    credentials: dict = Field(
        ...,
        description="Channel credentials — stored in Secret Manager",
        examples=[
            {"webhook_url": "https://hooks.slack.com/services/T.../B.../..."},
            {"routing_key": "abc123...32chars"},
        ],
    )
    config_metadata: dict | None = Field(
        default=None,
        description="Non-sensitive config like channel name or service label",
        examples=[
            {"channel": "#incidents"},
            {"service_name": "Auth Service"},
        ],
    )

    @field_validator("notification_type")
    @classmethod
    def validate_notification_type(cls, value: str) -> str:
        """Reject unknown notification types.

        Args:
            value: The notification_type string from the request.

        Returns:
            The validated type, lowercased for consistency.

        Raises:
            ValueError: If the type is not slack or pagerduty.
        """
        normalised = value.lower().strip()
        if normalised not in VALID_NOTIFICATION_TYPES:
            raise ValueError(
                f"notification_type must be one of: "
                f"{', '.join(sorted(VALID_NOTIFICATION_TYPES))}. "
                f"Got: {value!r}"
            )
        return normalised

    @field_validator("credentials")
    @classmethod
    def validate_credentials(cls, value: dict, info: Any) -> dict:
        """Validate credentials shape against the notification type.

        Slack must supply webhook_url (a Slack hooks.slack.com URL).
        PagerDuty must supply routing_key (32 hex characters).

        Args:
            value: The credentials dict.
            info: Pydantic validation info — gives access to other fields.

        Returns:
            The validated credentials dict unchanged.

        Raises:
            ValueError: If required credential fields are missing or malformed.
        """
        notification_type = (info.data or {}).get("notification_type")

        if notification_type == "slack":
            webhook_url = value.get("webhook_url", "")
            if not webhook_url:
                raise ValueError(
                    "Slack credentials must include webhook_url"
                )
            if not str(webhook_url).startswith("https://hooks.slack.com/"):
                raise ValueError(
                    "webhook_url must be a Slack incoming webhook URL "
                    "(starts with https://hooks.slack.com/)"
                )

        elif notification_type == "pagerduty":
            routing_key = value.get("routing_key", "")
            if not routing_key:
                raise ValueError(
                    "PagerDuty credentials must include routing_key"
                )
            if not re.fullmatch(r"[a-f0-9]{32}", routing_key.lower()):
                raise ValueError(
                    "routing_key must be a 32-character hex string "
                    "(found in PagerDuty → Service → Integrations → Events API v2)"
                )

        return value


class NotificationResponse(BaseModel):
    """Response returned after configuring a notification channel."""

    organisation_id: str
    notification_type: str
    secret_name: str
    message: str


class NotificationStatusResponse(BaseModel):
    """Current notification configuration for an organisation."""

    slack_configured: bool
    pagerduty_configured: bool
    slack_last_notified_at: str | None = None
    slack_last_status: str | None = None
    pagerduty_last_notified_at: str | None = None
    pagerduty_last_status: str | None = None    