"""Current auth context route."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.core.auth import resolve_request_auth_context
from app.core.db import AsyncSessionLocal
from app.services.seeding import seed_starter_data_if_empty

router = APIRouter(tags=["auth"])

@router.get("/me")
async def get_me(request: Request) -> dict[str, Any]:
    """Return the current user/team auth context safely without crashing."""
    context = getattr(request.state, "auth_context", None)
    if context is None:
        try:
            context = await resolve_request_auth_context(request)
        except HTTPException:
            context = None

    if context is None:
        return {"authenticated": False, "user": None}

    # Auto-seed starter data for new Auth0 users if their workspace is empty
    if not context.auth_disabled:
        async with AsyncSessionLocal() as session:
            await seed_starter_data_if_empty(session, team_id=context.team_id, user_id=context.user_id)

    return {
        "authenticated": True,
        "user": {
            "sub": context.user_id,
            "user_id": context.user_id,
            "email": context.email,
            "name": context.full_name,
            "full_name": context.full_name,
            "team_id": str(context.team_id),
            "team_name": context.team_name,
            "roles": [context.role],
            "role": context.role,
            "auth_disabled": context.auth_disabled,
        }
    }
