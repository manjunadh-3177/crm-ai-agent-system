"""Activity feed API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthContext, get_auth_context
from app.core.db import get_db
from app.schemas.crm import ActivityFeedItem
from app.services.activity import get_activity_feed

router = APIRouter(prefix="/activity-feed", tags=["activity"])


@router.get("", response_model=list[ActivityFeedItem])
async def get_activity_feed_route(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[ActivityFeedItem]:
    """Return unified activity feed for the authenticated team."""
    return await get_activity_feed(
        db,
        team_id=auth.team_id,
        limit=limit,
    )
