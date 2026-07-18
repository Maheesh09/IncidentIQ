# middleware/auth.py
from __future__ import annotations

import logging

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware

from database import AsyncSessionLocal
from models.incident import APIKey, Organisation
from utils.auth import hash_api_key

from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Routes that don't require authentication
PUBLIC_ROUTES = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/management/organisations",
}

# Route prefixes that don't require authentication
PUBLIC_PREFIXES = ()

# Only refresh last_used_at if the recorded value is older than this.
# Prevents a database write on every single authenticated request while
# still keeping the audit timestamp accurate to within a few minutes.
LAST_USED_REFRESH_SECONDS = 300

async def _touch_last_used(db: AsyncSession, api_key: APIKey) -> None:
    """Refresh an API key's last_used_at timestamp, throttled.

    Writes only if the existing timestamp is missing or older than
    LAST_USED_REFRESH_SECONDS. Failures are swallowed — an audit
    timestamp is never worth failing an authenticated request over.

    Args:
        db: Active database session from the middleware.
        api_key: The authenticated APIKey ORM object.
    """
    now = datetime.now(timezone.utc)

    if api_key.last_used_at is not None:
        try:
            previous = datetime.fromisoformat(api_key.last_used_at)
            # Tolerate rows written before timestamps were timezone-aware
            if previous.tzinfo is None:
                previous = previous.replace(tzinfo=timezone.utc)
            if (now - previous).total_seconds() < LAST_USED_REFRESH_SECONDS:
                return
        except ValueError:
            # Unparseable timestamp — overwrite it with a good one
            logger.warning(
                f"Unparseable last_used_at on key {api_key.key_prefix}, overwriting"
            )

    try:
        api_key.last_used_at = now.isoformat()
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.warning(
            f"Failed to update last_used_at for key {api_key.key_prefix}: {e}"
        )

class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware that validates API keys on every protected request.

    Extracts the API key from the Authorization header, validates it
    against the database, and attaches the organisation to request state.
    Rejects unauthenticated requests with 401 before they reach routes.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process each request through API key validation.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The response from the route handler, or a 401/403 error.
        """
        # Allow public routes through without authentication
        if request.url.path in PUBLIC_ROUTES:
            return await call_next(request)

        if request.url.path.startswith(PUBLIC_PREFIXES):
            return await call_next(request)

        # Extract API key from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Missing API key — include Authorization: Bearer <key>"
                },
            )

        raw_key = auth_header.removeprefix("Bearer ").strip()
        if not raw_key.startswith("iqk_live_"):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Invalid API key format — key must start with iqk_live_"
                },
            )

        # Validate key against database
        key_hash = hash_api_key(raw_key)

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(APIKey, Organisation)
                .join(Organisation, APIKey.organisation_id == Organisation.id)
                .where(
                    APIKey.key_hash == key_hash,
                    APIKey.is_active == 1,
                    Organisation.is_active == 1,
                )
            )
            row = result.first()

            # Refresh the audit timestamp while we still have a session open.
            # Reusing this session avoids opening a second connection.
            if row is not None:
                await _touch_last_used(db, row[0])

        if row is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or revoked API key"},
            )

        api_key, organisation = row

        # Attach organisation to request state for route handlers
        request.state.organisation_id = str(organisation.id)
        request.state.organisation_name = organisation.name
        request.state.api_key_id = str(api_key.id)

        logger.info(
            f"Authenticated request from org '{organisation.name}' "
            f"to {request.method} {request.url.path}"
        )

        return await call_next(request)