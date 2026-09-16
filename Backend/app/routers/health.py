"""Health check endpoints."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import get_ai_health
from app.core.db import get_db, get_table_names
from app.events import check_redis_connection, get_registered_events

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Return basic service health status."""
    return {"status": "ok"}


@router.get("/health/db", response_model=None)
async def database_health_check(
    db: AsyncSession = Depends(get_db),
) -> dict[str, str] | JSONResponse:
    """Return database connectivity status."""
    try:
        await db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "error", "database": "unavailable"},
        )

    return {"status": "ok", "database": "connected"}


@router.get("/health/tables", response_model=None)
async def database_tables_health() -> dict[str, list[str]] | JSONResponse:
    """Return the list of tables currently created in the database."""
    try:
        tables = await get_table_names()
    except SQLAlchemyError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "error", "tables": []},
        )

    return {"status": "ok", "tables": tables}


@router.get("/health/events")
async def events_health() -> dict[str, str | list[str]]:
    """Return registered event names."""
    return {
        "status": "ok",
        "registered_events": get_registered_events(),
    }


@router.get("/health/redis", response_model=None)
async def redis_health() -> dict[str, str] | JSONResponse:
    """Return Redis connectivity status."""
    if await check_redis_connection():
        return {"status": "ok", "redis": "connected"}

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "error", "redis": "unavailable"},
    )


@router.get("/health/ai")
async def ai_health() -> dict[str, str]:
    """Return configured AI provider information."""
    return get_ai_health()
