# main.py
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

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
    yield
    await engine.dispose()
    logger.info("IncidentIQ shutting down — database connections released")


app = FastAPI(
    title="IncidentIQ",
    description="Multi-agent incident root cause analysis platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Register middleware — runs on every request before route handlers
app.add_middleware(APIKeyMiddleware)

app.include_router(incidents.router)
app.include_router(reports.router)
app.include_router(management.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for load balancers and uptime monitors."""
    return {"status": "ok"}