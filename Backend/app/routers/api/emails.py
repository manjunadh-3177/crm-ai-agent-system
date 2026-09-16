"""Router for email history tracking."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthContext, get_auth_context
from app.core.db import get_db
from app.models.email_message import EmailMessage
from app.schemas.crm import EmailMessageRead

router = APIRouter(prefix="/emails", tags=["Emails"])


@router.get("", response_model=list[EmailMessageRead])
async def list_emails(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[EmailMessageRead]:
    """List email messages for the current user's team."""
    result = await db.execute(
        select(EmailMessage)
        .where(EmailMessage.team_id == auth.team_id)
        .order_by(desc(EmailMessage.created_at))
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get("/contact/{contact_id}", response_model=list[EmailMessageRead])
async def list_contact_emails(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[EmailMessageRead]:
    """List emails associated with a specific contact."""
    result = await db.execute(
        select(EmailMessage)
        .where(
            EmailMessage.team_id == auth.team_id,
            EmailMessage.contact_id == contact_id,
        )
        .order_by(desc(EmailMessage.created_at))
    )
    return list(result.scalars().all())


@router.get("/deal/{deal_id}", response_model=list[EmailMessageRead])
async def list_deal_emails(
    deal_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[EmailMessageRead]:
    """List emails associated with a specific deal."""
    result = await db.execute(
        select(EmailMessage)
        .where(
            EmailMessage.team_id == auth.team_id,
            EmailMessage.deal_id == deal_id,
        )
        .order_by(desc(EmailMessage.created_at))
    )
    return list(result.scalars().all())
