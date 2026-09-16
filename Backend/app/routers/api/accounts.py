"""Account routes."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthContext, get_auth_context
from app.core.db import get_db
from app.schemas.crm import AccountDetailRead, AccountRead
from app.services.accounts import get_account_detail_or_404, list_accounts as list_accounts_service


router = APIRouter(tags=["accounts"])


@router.get("/accounts", response_model=list[AccountRead])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[AccountRead]:
    """Return all accounts."""
    return await list_accounts_service(db, team_id=auth.team_id)


@router.get("/accounts/{account_id}", response_model=AccountDetailRead)
async def get_account_detail(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> AccountDetailRead:
    """Return a team-scoped 360-degree account view."""
    return await get_account_detail_or_404(db, account_id, team_id=auth.team_id)
