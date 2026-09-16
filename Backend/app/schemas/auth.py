"""Schemas for auth/session endpoints."""

from uuid import UUID

from pydantic import BaseModel


class MeResponse(BaseModel):
    """Current authenticated user/team context."""

    user_id: str
    email: str
    team_id: UUID
    team_name: str
    role: str
    full_name: str | None = None
    auth_disabled: bool
