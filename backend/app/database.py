"""Database connection pool, transaction management, and migration runner."""

from contextlib import asynccontextmanager

import asyncpg
from sqlalchemy import pool as sa_pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from alembic.config import Config

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

_pool: asyncpg.Pool | None = None


def _get_alembic_url() -> str:
    """Return a SQLAlchemy-compatible asyncpg URL for Alembic."""
    url = get_settings().database_url
    if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


async def _run_migrations() -> None:
    """Run Alembic migrations asynchronously using an async SQLAlchemy engine."""
    connectable = create_async_engine(_get_alembic_url(), poolclass=sa_pool.NullPool)

    def do_run_migrations(connection) -> None:
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.attributes["connection"] = connection
        command.upgrade(alembic_cfg, "head")

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
        logger.info("Database migrations applied successfully")
    finally:
        await connectable.dispose()


async def init_db() -> asyncpg.Pool:
    """Initialize the asyncpg connection pool and run migrations."""
    global _pool
    settings = get_settings()

    _pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        command_timeout=settings.db_command_timeout,
    )
    logger.info("Database pool initialized")

    await _run_migrations()
    return _pool


async def close_db() -> None:
    """Close the asyncpg connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


def get_pool() -> asyncpg.Pool:
    """Return the initialized connection pool."""
    if _pool is None:
        raise RuntimeError("Database pool has not been initialized")
    return _pool


@asynccontextmanager
async def get_connection():
    """Acquire a single connection from the pool and release it on exit."""
    async with get_pool().acquire() as conn:
        yield conn


@asynccontextmanager
async def transaction():
    """Acquire a connection and wrap operations in a transaction."""
    async with get_connection() as conn:
        async with conn.transaction():
            yield conn
