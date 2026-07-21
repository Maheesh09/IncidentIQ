# database.py
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=5,
    max_overflow=20,
    # Neon is a serverless PostgreSQL — it closes idle connections after
    # a few minutes of inactivity. pool_pre_ping sends a lightweight
    # SELECT 1 before handing out a pooled connection; if Neon has closed
    # it, SQLAlchemy opens a fresh connection instead of raising
    # InterfaceError: connection is closed.
    pool_pre_ping=True,
    # Proactively recycle connections after 5 minutes so we never hand
    # out a connection that Neon has already closed on its end.
    pool_recycle=300,
    connect_args={"ssl": "require"} if "neon.tech" in settings.database_url else {},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy ORM models."""
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async database session.

    Commits on success, rolls back on any exception, always closes.

    Yields:
        An active AsyncSession bound to a single request.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise