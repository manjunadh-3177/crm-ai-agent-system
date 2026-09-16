"""Read-only team routes."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthContext, get_auth_context
from app.core.db import get_db
from app.models import Team
from app.schemas.crm import TeamRead

router = APIRouter(tags=["teams"])


@router.get("/teams", response_model=list[TeamRead])
async def list_teams(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[Team]:
    """Return the current team only."""
    result = await db.execute(select(Team).where(Team.id == auth.team_id).order_by(Team.created_at))
    return list(result.scalars().all())
