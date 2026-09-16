"""Read-only stage routes."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthContext, get_auth_context
from app.core.db import get_db
from app.models import DealStage
from app.schemas.crm import DealStageRead
from app.services.seeding import ensure_default_pipeline_stages


router = APIRouter(tags=["stages"])


@router.get("/stages", response_model=list[DealStageRead])
async def list_stages(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[DealStage]:
    """Return all deal stages."""
    await ensure_default_pipeline_stages(db, auth.team_id)
    await db.commit()
    result = await db.execute(
        select(DealStage)
        .where(DealStage.team_id == auth.team_id)
        .order_by(DealStage.position, DealStage.created_at)
    )
    return list(result.scalars().all())
