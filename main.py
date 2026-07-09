# main.py
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from routers import incidents, reports

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown events.

    Startup: initialise connections and resources.
    Shutdown: cleanly close connections.
    """
    logger.info("IncidentIQ starting up")
    # Database connection pool will be initialised here in the next step
    yield
    logger.info("IncidentIQ shutting down")


app = FastAPI(
    title="IncidentIQ",
    description="Multi-agent incident root cause analysis platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(incidents.router)
app.include_router(reports.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for load balancers and uptime monitors."""
    return {"status": "ok"}