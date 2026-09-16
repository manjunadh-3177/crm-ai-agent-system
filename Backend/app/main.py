"""Acufy CRM FastAPI application entry point."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.agents.followup_agent import SUPPORTED_EVENTS, run_followup_agent
from app.core.auth import auth_context_middleware
from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.events import register_handler
from app.events.ws import start_redis_ws_bridge, stop_redis_ws_bridge
from app.routers import health
from app.routers.admin import router as admin_router
from app.routers.ai import router as ai_router
from app.routers.copilot import router as copilot_router
from app.routers.api.v1 import router as api_v1_router
from app.routers.me import router as me_router
from app.routers.ws import router as ws_router


def _register_local_followup_handlers() -> None:
    """Register async local fallback handlers when Redis/worker is not used."""

    async def _run_agent_handler(event_name: str, payload: dict) -> None:
        async def _run() -> None:
            async with AsyncSessionLocal() as session:
                await run_followup_agent(session, event_name=event_name, payload=payload)

        asyncio.create_task(_run())

    for event_name in SUPPORTED_EVENTS:
        register_handler(event_name, _run_agent_handler)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle startup and shutdown hooks for the application."""
    del app
    settings = get_settings()
    if not settings.redis_url:
        _register_local_followup_handlers()
    await start_redis_ws_bridge()
    yield
    await stop_redis_ws_bridge()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title="Acufy CRM",
        description="Stage 1 backend skeleton for Acufy CRM.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health.router)
    application.middleware("http")(auth_context_middleware)
    application.include_router(admin_router)
    application.include_router(ai_router)
    application.include_router(copilot_router)
    application.include_router(me_router)
    application.include_router(api_v1_router)
    application.include_router(ws_router)
    return application


app = create_app()
