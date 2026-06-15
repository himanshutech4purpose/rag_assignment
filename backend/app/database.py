import asyncpg
from app.config import settings

pool: asyncpg.Pool | None = None


async def init_db():
    global pool
    pool = await asyncpg.create_pool(settings.database_url)
    async with pool.acquire() as conn:
        with open("init.sql") as f:
            await conn.execute(f.read())


async def close_db():
    global pool
    if pool:
        await pool.close()


def get_pool() -> asyncpg.Pool:
    return pool
