# main.py
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from config import settings

from prometheus_fastapi_instrumentator import Instrumentator

from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from database import engine
from middleware.auth import APIKeyMiddleware
from routers import incidents, reports
from routers import management

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown events.

    Startup: connection pool is created automatically by SQLAlchemy.
    Shutdown: all connections in the pool are closed cleanly.
    """
    logger.info("IncidentIQ starting up")

    # Validate CORS configuration at startup
    if not settings.cors_allowed_origins:
        logger.error(
            "CORS_ALLOWED_ORIGINS is not configured. "
            "Set explicit trusted origins in your .env file. "
            "Never use ['*'] in production."
        )
        raise ValueError(
            "CORS_ALLOWED_ORIGINS must be explicitly configured. "
            "Add CORS_ALLOWED_ORIGINS=[\"https://your-domain.com\"] to .env"
        )

    if "*" in settings.cors_allowed_origins:
        logger.warning(
            "CORS is configured with wildcard '*' — this allows any website to call your API. "
            "Replace with explicit trusted origins before deploying to production."
        )

    yield
    await engine.dispose()
    logger.info("IncidentIQ shutting down — database connections released")


app = FastAPI(
    title="IncidentIQ",
    description="Multi-agent incident root cause analysis platform",
    version="0.1.0",
    lifespan=lifespan,
)
Instrumentator().instrument(app).expose(app)
# Register middleware — runs on every request before route handlers
# CORS must be registered first, then authentication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET","POST"],
    allow_headers=["Authorization","Content-Type"],
)
app.add_middleware(APIKeyMiddleware)

app.include_router(incidents.router)
app.include_router(reports.router)
app.include_router(management.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for load balancers and uptime monitors."""
    return {"status": "ok"}