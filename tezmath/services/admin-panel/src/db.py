from functools import lru_cache

import asyncpg
from pydantic_settings import BaseSettings

_pool: asyncpg.Pool | None = None


class DBSettings(BaseSettings):
    database_url: str

    class Config:
        env_file = ".env"


@lru_cache
def get_db_settings() -> DBSettings:
    return DBSettings()


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=get_db_settings().database_url, min_size=2, max_size=10)
    return _pool
