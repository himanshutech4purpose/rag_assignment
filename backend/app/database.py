"""Database engine, session management, transaction handling, and migrations."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command
from alembic.config import Config

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

settings = get_settings()


def _get_async_database_url() -> str:
    """Return an asyncpg-compatible URL for SQLAlchemy async engines."""
    url = settings.database_url
    if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


# Global async engine. Created at import time so Alembic and the app share the
# same connection pool. Disposed explicitly in close_db during shutdown.
engine = create_async_engine(
    _get_async_database_url(),
    future=True,
    echo=False,
    pool_pre_ping=True,
)

# Session factory used by the dependency injection system and manual transactions.
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def _run_migrations() -> None:
    """Run Alembic migrations from the async application lifespan.

    ``command.upgrade`` is synchronous and internally creates its own async
    engine/event loop via ``alembic/env.py``. Running it in a separate thread
    avoids nesting event loops when called from within Uvicorn's loop.
    """

    def do_run_migrations() -> None:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")

    await asyncio.to_thread(do_run_migrations)
    logger.info("Database migrations applied successfully")


async def init_db() -> None:
    """Initialize the database layer and run pending migrations."""
    await _run_migrations()


async def close_db() -> None:
    """Dispose the SQLAlchemy engine and close the connection pool."""
    await engine.dispose()
    logger.info("Database engine disposed")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session that auto-commits on success and rolls back on error.

    Intended for use as a FastAPI dependency. Closing is handled by the
    ``AsyncSessionLocal`` context manager.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def transaction() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional scope around a series of operations.

    Useful for services that need to manage their own transaction boundaries
    without going through the FastAPI dependency layer.
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():
            yield session
