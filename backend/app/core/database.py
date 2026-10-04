from typing import AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Configure connect_args and pool class for transaction poolers (such as Supabase PgBouncer on port 6543)
connect_args = {}
extra_engine_kwargs = {}

if "6543" in settings.ASYNC_DATABASE_URL or "pooler.supabase.com" in settings.ASYNC_DATABASE_URL:
    connect_args["statement_cache_size"] = 0
    # Use NullPool for PgBouncer transaction pooling mode as recommended by Supabase/SQLAlchemy
    extra_engine_kwargs["poolclass"] = NullPool
elif "sqlite" in settings.ASYNC_DATABASE_URL:
    connect_args["check_same_thread"] = False
    extra_engine_kwargs["poolclass"] = NullPool
else:
    # Generous pooling for standard PostgreSQL
    extra_engine_kwargs["pool_size"] = 10
    extra_engine_kwargs["max_overflow"] = 20
    extra_engine_kwargs["pool_timeout"] = 15.0

# Asynchronous engine and session factory for FastAPI endpoints
async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=(settings.ENVIRONMENT == "debug"),
    future=True,
    pool_pre_ping=True,
    connect_args=connect_args,
    **extra_engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# Synchronous engine for Alembic and migration scripts
def get_sync_engine():
    return create_engine(
        settings.SYNC_DATABASE_URL,
        pool_pre_ping=True,
    )
