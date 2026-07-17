# routers/management.py
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.incident import APIKey, LogSourceConfig, Organisation, WebhookConfig
from models.management_schemas import (
    LogSourceRequest,
    LogSourceResponse,
    OrganisationDetailsResponse,
    OrganisationRequest,
    OrganisationResponse,
    WebhookRequest,
    WebhookResponse,
)
from utils.auth import generate_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/management", tags=["management"])


@router.post(
    "/organisations",
    response_model=OrganisationResponse,
    status_code=201,
)
async def register_organisation(
    request: OrganisationRequest,
    db: AsyncSession = Depends(get_db),
) -> OrganisationResponse:
    """Register a new organisation and generate its first API key.

    The API key is returned once and never stored in plaintext.
    The customer must save it immediately — it cannot be retrieved again.
    """
    # Check if organisation name already exists
    result = await db.execute(
        select(Organisation).where(Organisation.name == request.name)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Organisation '{request.name}' already exists"
        )

    # Create the organisation
    organisation = Organisation(
        name=request.name,
        is_active=1,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(organisation)
    await db.flush()

    # Generate API key
    raw_key, key_hash, key_prefix = generate_api_key()

    api_key = APIKey(
        organisation_id=organisation.id,
        name="Default key",
        key_hash=key_hash,
        key_prefix=key_prefix,
        is_active=1,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(api_key)
    await db.flush()

    logger.info(
        f"Organisation '{request.name}' registered — "
        f"id: {organisation.id}, key prefix: {key_prefix}"
    )

    return OrganisationResponse(
        organisation_id=str(organisation.id),
        name=organisation.name,
        api_key=raw_key,
        key_prefix=key_prefix,
        message=(
            "Organisation registered successfully. "
            "Save your API key now — it will not be shown again."
        ),
    )

@router.post(
    "/log-source",
    response_model=LogSourceResponse,
    status_code=200,
)

async def configure_log_source(
    request: Request,
    body: LogSourceRequest,
    db: AsyncSession = Depends(get_db),
) -> LogSourceResponse:
    """Configure a log source connector for the organisation.

    Credentials are stored in Google Cloud Secret Manager.
    Only the secret name is stored in the database.
    """
    organisation_id = request.state.organisation_id

    # Validate credentials structure based on source type
    if body.source_type == "gcp":
        required = {"project_id", "service_account_key"}
        missing = required - set(body.credentials.keys())
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"GCP credentials missing required fields: {missing}"
            )

    elif body.source_type == "aws":
        required = {"access_key_id", "secret_access_key", "region"}
        missing = required - set(body.credentials.keys())
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"AWS credentials missing required fields: {missing}"
            )

    elif body.source_type == "datadog":
        required = {"api_key", "app_key"}
        missing = required - set(body.credentials.keys())
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Datadog credentials missing required fields: {missing}"
            )

    # Store credentials in Secret Manager
    from utils.secret_manager import store_secret
    secret_name = f"org-{organisation_id}-log-source"

    if body.source_type != "manual":
        await store_secret(
            secret_name=secret_name,
            secret_value=body.credentials,
        )
    else:
        secret_name = "manual-no-credentials"

    # Save or update log source config in database
    result = await db.execute(
        select(LogSourceConfig).where(
            LogSourceConfig.organisation_id == uuid.UUID(organisation_id)
        )
    )
    existing_config = result.scalar_one_or_none()

    if existing_config:
        existing_config.source_type = body.source_type
        existing_config.secret_name = secret_name
        existing_config.config_metadata = body.config_metadata
        existing_config.updated_at = datetime.now(timezone.utc).isoformat()
    else:
        log_source = LogSourceConfig(
            organisation_id=uuid.UUID(organisation_id),
            source_type=body.source_type,
            secret_name=secret_name,
            config_metadata=body.config_metadata,
            is_active=1,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        db.add(log_source)

    logger.info(
        f"Log source configured for org {organisation_id}: "
        f"{body.source_type}"
    )

    return LogSourceResponse(
        organisation_id=organisation_id,
        source_type=body.source_type,
        secret_name=secret_name,
        message=f"Log source '{body.source_type}' configured successfully",
    )

@router.post(
    "/webhook",
    response_model=WebhookResponse,
    status_code=200,
)
async def configure_webhook(
    request: Request,
    body: WebhookRequest,
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    """Configure a webhook endpoint for RCA report delivery.

    When the pipeline completes, IncidentIQ POSTs the report
    to this URL signed with the provided secret.
    """
    organisation_id = request.state.organisation_id

    # Save or update webhook config in database
    result = await db.execute(
        select(WebhookConfig).where(
            WebhookConfig.organisation_id == uuid.UUID(organisation_id)
        )
    )
    existing_config = result.scalar_one_or_none()

    webhook_url = str(body.url)

    if existing_config:
        existing_config.url = webhook_url
        existing_config.secret = body.secret
        existing_config.is_active = 1
        existing_config.updated_at = datetime.now(timezone.utc).isoformat()
    else:
        webhook_config = WebhookConfig(
            organisation_id=uuid.UUID(organisation_id),
            url=webhook_url,
            secret=body.secret,
            is_active=1,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        db.add(webhook_config)

    logger.info(
        f"Webhook configured for org {organisation_id}: {webhook_url}"
    )

    return WebhookResponse(
        organisation_id=organisation_id,
        webhook_url=webhook_url,
        message="Webhook configured successfully",
    )

@router.get(
    "/organisations/me",
    response_model=OrganisationDetailsResponse,
    status_code=200,
)
async def get_organisation_details(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> OrganisationDetailsResponse:
    """Get current organisation details and configuration status."""
    organisation_id = request.state.organisation_id

    result = await db.execute(
        select(Organisation).where(
            Organisation.id == uuid.UUID(organisation_id)
        )
    )
    organisation = result.scalar_one_or_none()

    if organisation is None:
        raise HTTPException(status_code=404, detail="Organisation not found")

    log_source_result = await db.execute(
        select(LogSourceConfig).where(
            LogSourceConfig.organisation_id == uuid.UUID(organisation_id)
        )
    )
    log_source = log_source_result.scalar_one_or_none()

    webhook_result = await db.execute(
        select(WebhookConfig).where(
            WebhookConfig.organisation_id == uuid.UUID(organisation_id)
        )
    )
    webhook = webhook_result.scalar_one_or_none()

    return OrganisationDetailsResponse(
        organisation_id=organisation_id,
        name=organisation.name,
        log_source_type=log_source.source_type if log_source else None,
        webhook_configured=webhook is not None and webhook.is_active == 1,
        created_at=organisation.created_at,
    )    