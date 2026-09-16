"""Database configuration and session management."""

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


settings = get_settings()


class Base(DeclarativeBase):
    """Base class for future SQLAlchemy models."""


engine: AsyncEngine = create_async_engine(
    str(settings.database_url),
    pool_pre_ping=True,
    echo=settings.app_debug,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for request-scoped use."""
    async with AsyncSessionLocal() as session:
        auth_context = getattr(request.state, "auth_context", None)
        if auth_context is not None:
            session.info["team_id"] = auth_context.team_id
            session.info["user_id"] = auth_context.user_id
            await session.execute(
                text("SELECT set_config('app.current_team_id', :team_id, true)"),
                {"team_id": str(auth_context.team_id)},
            )
            await session.execute(
                text("SELECT set_config('app.current_user_id', :user_id, true)"),
                {"user_id": str(auth_context.user_id)},
            )
        yield session


def register_models() -> None:
    """Import model modules so metadata is fully registered."""
    import app.models  # noqa: F401


async def create_all_tables() -> None:
    """Create all registered tables."""
    register_models()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


def _get_table_names(sync_connection: Connection) -> list[str]:
    """Read table names from the current database."""
    inspector = inspect(sync_connection)
    return sorted(inspector.get_table_names())


async def get_table_names() -> list[str]:
    """Return the current database table names."""
    async with engine.connect() as connection:
        return await connection.run_sync(_get_table_names)
