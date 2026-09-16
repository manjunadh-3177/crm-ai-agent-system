"""Account service helpers."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Account, Deal, DealContactRole, Team
from app.schemas.crm import (
    AccountActivitySummaryRead,
    AccountCreate,
    AccountDetailClosedDealRead,
    AccountDetailContactRead,
    AccountDetailOpenDealRead,
    AccountDetailRead,
    AccountDetailStakeholderRead,
)
from app.services.audit import log_audit


DECIMAL_ZERO = Decimal("0.00")


async def list_accounts(db: AsyncSession, *, team_id: UUID) -> list[Account]:
    """Return all team-scoped accounts."""
    result = await db.execute(
        select(Account).where(Account.team_id == team_id).order_by(Account.created_at)
    )
    return list(result.scalars().all())


async def get_account_detail_or_404(
    db: AsyncSession,
    account_id: UUID,
    *,
    team_id: UUID,
) -> AccountDetailRead:
    """Return a 360-degree account detail view scoped to the current team."""
    result = await db.execute(
        select(Account)
        .options(
            selectinload(Account.deals).selectinload(Deal.stage),
            selectinload(Account.deals).selectinload(Deal.contact),
            selectinload(Account.deals)
            .selectinload(Deal.stakeholders)
            .selectinload(DealContactRole.contact),
        )
        .where(Account.id == account_id, Account.team_id == team_id)
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    contact_map: dict[UUID, AccountDetailContactRead] = {}
    open_deals: list[AccountDetailOpenDealRead] = []
    closed_deals: list[AccountDetailClosedDealRead] = []
    stakeholders: list[AccountDetailStakeholderRead] = []
    pipeline_value = DECIMAL_ZERO
    won_value = DECIMAL_ZERO
    last_activity_candidates = [account.updated_at]

    for deal in sorted(account.deals, key=lambda item: item.updated_at, reverse=True):
        stage_name = deal.stage.name if deal.stage else "Unknown"
        last_activity_candidates.append(deal.updated_at)

        if deal.contact is not None:
            contact_map.setdefault(
                deal.contact.id,
                AccountDetailContactRead(
                    id=deal.contact.id,
                    first_name=deal.contact.first_name,
                    last_name=deal.contact.last_name,
                    email=deal.contact.email,
                    phone=deal.contact.phone,
                ),
            )
            last_activity_candidates.append(deal.contact.updated_at)

        for stakeholder in deal.stakeholders:
            if stakeholder.contact is None:
                continue
            contact_map.setdefault(
                stakeholder.contact.id,
                AccountDetailContactRead(
                    id=stakeholder.contact.id,
                    first_name=stakeholder.contact.first_name,
                    last_name=stakeholder.contact.last_name,
                    email=stakeholder.contact.email,
                    phone=stakeholder.contact.phone,
                ),
            )
            stakeholders.append(
                AccountDetailStakeholderRead(
                    deal_name=deal.name,
                    contact_name=f"{stakeholder.contact.first_name} {stakeholder.contact.last_name}",
                    role=stakeholder.role,
                )
            )
            last_activity_candidates.append(stakeholder.updated_at)
            last_activity_candidates.append(stakeholder.contact.updated_at)

        if deal.stage and deal.stage.is_closed:
            closed_deals.append(
                AccountDetailClosedDealRead(
                    id=deal.id,
                    name=deal.name,
                    amount=deal.amount,
                    stage=stage_name,
                    updated_at=deal.updated_at,
                )
            )
            if stage_name.lower() == "won" and deal.amount is not None:
                won_value += Decimal(str(deal.amount))
        else:
            open_deals.append(
                AccountDetailOpenDealRead(
                    id=deal.id,
                    name=deal.name,
                    amount=deal.amount,
                    stage=stage_name,
                    probability=deal.probability,
                    expected_close_date=deal.expected_close_date,
                )
            )
            if deal.amount is not None:
                pipeline_value += Decimal(str(deal.amount))

    contacts = sorted(contact_map.values(), key=lambda item: (item.first_name.lower(), item.last_name.lower(), item.email.lower()))
    stakeholders.sort(key=lambda item: (item.deal_name.lower(), item.contact_name.lower(), item.role))

    return AccountDetailRead(
        id=account.id,
        name=account.name,
        website=account.domain,
        industry=account.industry,
        size=None,
        created_at=account.created_at,
        contacts=contacts,
        open_deals=open_deals,
        closed_deals=closed_deals,
        stakeholders=stakeholders,
        activity_summary=AccountActivitySummaryRead(
            total_contacts=len(contacts),
            total_open_deals=len(open_deals),
            pipeline_value=pipeline_value.quantize(Decimal("0.01")),
            won_value=won_value.quantize(Decimal("0.01")),
            last_activity_at=max((value for value in last_activity_candidates if value is not None), default=None),
        ),
    )


async def create_account(
    db: AsyncSession,
    payload: AccountCreate,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> Account:
    """Create an account for a team."""
    team = await db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")

    account = Account(team_id=team_id, **payload.model_dump())
    db.add(account)
    await db.flush()
    await log_audit(
        db,
        action="account.created",
        entity_type="account",
        entity_id=str(account.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"name": account.name},
    )
    await db.commit()
    await db.refresh(account)
    return account
