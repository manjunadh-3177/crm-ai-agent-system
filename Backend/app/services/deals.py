"""Deal service layer."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.events import emit_event
from app.jobs import enqueue_background_job
from app.models import (
    Account,
    Contact,
    Deal,
    DealContactRole,
    DealLineItem,
    DealStage,
    Product,
    Team,
    User,
)
from app.schemas.crm import (
    DealContactRoleCreate,
    DealContactRoleUpdate,
    DealCreate,
    DealLineItemCreate,
    DealLineItemUpdate,
    DealStageUpdate,
    DealUpdate,
)
from app.services.audit import log_audit
from app.services.seeding import seed_pipeline_data_if_empty

DECIMAL_ZERO = Decimal("0.00")


def _detail_options():
    return (
        selectinload(Deal.stage),
        selectinload(Deal.owner),
        selectinload(Deal.contact),
        selectinload(Deal.account),
        selectinload(Deal.team),
        selectinload(Deal.line_items).selectinload(DealLineItem.product),
        selectinload(Deal.stakeholders).selectinload(DealContactRole.contact),
    )


async def list_deals(db: AsyncSession, *, team_id: UUID) -> list[Deal]:
    """Return all deals with relationships used by the UI."""
    await seed_pipeline_data_if_empty(db, team_id, user_id=db.info.get("user_id"))
    result = await db.execute(
        select(Deal)
        .options(*_detail_options())
        .where(Deal.team_id == team_id)
        .order_by(Deal.created_at)
    )
    return list(result.scalars().all())


async def get_deal_or_404(
    db: AsyncSession,
    deal_id: UUID,
    *,
    team_id: UUID,
    include_detail: bool = False,
) -> Deal:
    """Return a deal or raise 404."""
    query = select(Deal).where(Deal.id == deal_id, Deal.team_id == team_id)
    if include_detail:
        query = query.options(*_detail_options())
    else:
        query = query.options(selectinload(Deal.stage), selectinload(Deal.owner))

    result = await db.execute(query)
    deal = result.scalar_one_or_none()
    if deal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deal not found.",
        )
    return deal


async def create_deal(
    db: AsyncSession,
    payload: DealCreate,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> Deal:
    """Create a deal after validating relationships."""
    await _validate_deal_payload(db, payload, team_id=team_id)
    deal = Deal(team_id=team_id, **payload.model_dump())
    db.add(deal)
    await db.flush()
    await log_audit(
        db,
        action="deal.created",
        entity_type="deal",
        entity_id=str(deal.id),
        actor_type="user",
        team_id=deal.team_id,
        actor_id=actor_id,
        metadata={"stage_id": str(deal.stage_id)},
    )
    await db.commit()
    created_deal = await get_deal_or_404(db, deal.id, team_id=team_id, include_detail=True)
    await emit_event(
        "deal.created",
        {
            "deal_id": str(created_deal.id),
            "team_id": str(created_deal.team_id),
            "stage_id": str(created_deal.stage_id),
            "contact_id": str(created_deal.contact_id) if created_deal.contact_id else None,
            "account_id": str(created_deal.account_id) if created_deal.account_id else None,
        },
    )
    from app.ai.graphs.crm_orchestration import DEAL_RESCUE_GRAPH, run_deal_rescue_graph
    rescue_queue = await enqueue_background_job(
        "crm_graph_job",
        DEAL_RESCUE_GRAPH,
        str(team_id),
        actor_id,
        deal_id=str(created_deal.id),
        trigger="deal.created",
    )
    if not rescue_queue.get("queued"):
        await run_deal_rescue_graph(
            db,
            team_id=team_id,
            actor_id=actor_id,
            deal_id=created_deal.id,
            trigger="deal.created",
        )
    from app.services.automations import run_trigger
    await run_trigger(db, "deal.created", {"id": str(created_deal.id), "amount": float(created_deal.amount) if created_deal.amount else 0.0, "stage": created_deal.stage.name if created_deal.stage else None, "contact_id": str(created_deal.contact_id) if created_deal.contact_id else None, "account_id": str(created_deal.account_id) if created_deal.account_id else None}, team_id)

    return created_deal


async def update_deal(
    db: AsyncSession,
    deal_id: UUID,
    payload: DealUpdate,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> Deal:
    """Patch a deal after validating relationships."""
    deal = await db.get(Deal, deal_id)
    if deal is None or deal.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deal not found.",
        )

    data = payload.model_dump(exclude_unset=True)
    merged = {
        "name": deal.name,
        "amount": deal.amount,
        "currency": deal.currency,
        "probability": deal.probability,
        "expected_close_date": deal.expected_close_date,
        "owner_user_id": deal.owner_user_id,
        "stage_id": deal.stage_id,
        "contact_id": deal.contact_id,
        "account_id": deal.account_id,
    }
    merged.update(data)
    await _validate_deal_payload(db, DealCreate(**merged), team_id=team_id)

    for field, value in data.items():
        setattr(deal, field, value)

    if "amount" in data and deal.amount is not None:
        deal.amount = Decimal(str(deal.amount)).quantize(Decimal("0.01"))

    await db.commit()
    updated_deal = await get_deal_or_404(db, deal.id, team_id=team_id, include_detail=True)
    await emit_event(
        "deal.updated",
        {
            "deal_id": str(updated_deal.id),
            "team_id": str(updated_deal.team_id),
            "updated_fields": sorted(data.keys()),
        },
    )

    from app.ai.graphs.crm_orchestration import DEAL_RESCUE_GRAPH, run_deal_rescue_graph
    rescue_queue = await enqueue_background_job(
        "crm_graph_job",
        DEAL_RESCUE_GRAPH,
        str(team_id),
        actor_id,
        deal_id=str(updated_deal.id),
        trigger="deal.updated",
    )
    if not rescue_queue.get("queued"):
        await run_deal_rescue_graph(
            db,
            team_id=team_id,
            actor_id=actor_id,
            deal_id=updated_deal.id,
            trigger="deal.updated",
        )

    return updated_deal


async def update_deal_stage(
    db: AsyncSession,
    deal_id: UUID,
    payload: DealStageUpdate,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> Deal:
    """Update only the stage for a deal."""
    deal = await db.get(Deal, deal_id)
    if deal is None or deal.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deal not found.",
        )

    stage = await db.get(DealStage, payload.stage_id)
    if stage is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found.",
        )
    if stage.team_id != deal.team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stage must belong to the same team as the deal.",
        )

    previous_stage_id = str(deal.stage_id)
    deal.stage_id = payload.stage_id
    await log_audit(
        db,
        action="deal.stage_changed",
        entity_type="deal",
        entity_id=str(deal.id),
        actor_type="user",
        team_id=deal.team_id,
        actor_id=actor_id,
        metadata={
            "from_stage_id": previous_stage_id,
            "to_stage_id": str(payload.stage_id),
        },
    )
    await db.commit()
    updated_deal = await get_deal_or_404(db, deal.id, team_id=team_id, include_detail=True)
    await emit_event(
        "deal.stage_changed",
        {
            "deal_id": str(updated_deal.id),
            "team_id": str(updated_deal.team_id),
            "from_stage_id": previous_stage_id,
            "to_stage_id": str(updated_deal.stage_id),
        },
    )
    from app.services.automations import run_trigger
    await run_trigger(db, "deal.stage_changed", {"id": str(updated_deal.id), "amount": float(updated_deal.amount) if updated_deal.amount else 0.0, "stage": updated_deal.stage.name if updated_deal.stage else None, "contact_id": str(updated_deal.contact_id) if updated_deal.contact_id else None, "account_id": str(updated_deal.account_id) if updated_deal.account_id else None}, team_id)

    from app.ai.graphs.crm_orchestration import (
        DEAL_RESCUE_GRAPH,
        PROPOSAL_GRAPH,
        run_deal_rescue_graph,
        run_proposal_graph,
    )
    rescue_queue = await enqueue_background_job(
        "crm_graph_job",
        DEAL_RESCUE_GRAPH,
        str(team_id),
        actor_id,
        deal_id=str(updated_deal.id),
        trigger="deal.stage_changed",
    )
    if not rescue_queue.get("queued"):
        await run_deal_rescue_graph(
            db,
            team_id=team_id,
            actor_id=actor_id,
            deal_id=updated_deal.id,
            trigger="deal.stage_changed",
        )
    if updated_deal.stage and updated_deal.stage.name.strip().lower() == "proposal":
        proposal_queue = await enqueue_background_job(
            "crm_graph_job",
            PROPOSAL_GRAPH,
            str(team_id),
            actor_id,
            deal_id=str(updated_deal.id),
            trigger="deal.stage_changed",
        )
        if not proposal_queue.get("queued"):
            await run_proposal_graph(
                db,
                deal_id=updated_deal.id,
                team_id=team_id,
                actor_id=actor_id,
                trigger="deal.stage_changed",
            )

    return updated_deal


async def add_deal_line_item(
    db: AsyncSession,
    deal_id: UUID,
    payload: DealLineItemCreate,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> Deal:
    """Attach a product to a deal."""
    deal = await get_deal_or_404(db, deal_id, team_id=team_id, include_detail=True)
    product = await db.get(Product, payload.product_id)
    if product is None or product.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    unit_price = payload.unit_price if payload.unit_price is not None else product.price
    currency = product.currency
    if currency != deal.currency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product currency must match the deal currency.",
        )

    line_item = DealLineItem(
        team_id=team_id,
        deal_id=deal.id,
        product_id=product.id,
        quantity=_quantize(payload.quantity),
        unit_price=_quantize(unit_price),
        subtotal=_quantize(payload.quantity * unit_price),
        currency=currency,
    )
    previous_sum = _current_line_item_sum(deal.line_items)
    db.add(line_item)
    await db.flush()
    deal.line_items.append(line_item)
    await _recalculate_deal_amount(deal, previous_sum=previous_sum)
    await log_audit(
        db,
        action="deal.line_item.created",
        entity_type="deal_line_item",
        entity_id=str(line_item.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={
            "deal_id": str(deal.id),
            "product_id": str(product.id),
            "quantity": str(line_item.quantity),
            "unit_price": str(line_item.unit_price),
            "subtotal": str(line_item.subtotal),
        },
    )
    await db.commit()
    return await get_deal_or_404(db, deal.id, team_id=team_id, include_detail=True)


async def update_deal_line_item(
    db: AsyncSession,
    deal_id: UUID,
    line_item_id: UUID,
    payload: DealLineItemUpdate,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> Deal:
    """Update quantity or price on a deal line item."""
    deal = await get_deal_or_404(db, deal_id, team_id=team_id, include_detail=True)
    line_item = next((item for item in deal.line_items if item.id == line_item_id), None)
    if line_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Line item not found.")

    previous_sum = _current_line_item_sum(deal.line_items)
    data = payload.model_dump(exclude_unset=True)
    if "quantity" in data and data["quantity"] is not None:
        line_item.quantity = _quantize(data["quantity"])
    if "unit_price" in data and data["unit_price"] is not None:
        line_item.unit_price = _quantize(data["unit_price"])
    line_item.subtotal = _quantize(line_item.quantity * line_item.unit_price)
    await _recalculate_deal_amount(deal, previous_sum=previous_sum)
    await log_audit(
        db,
        action="deal.line_item.updated",
        entity_type="deal_line_item",
        entity_id=str(line_item.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={
            "deal_id": str(deal.id),
            "updated_fields": sorted(data.keys()),
            "subtotal": str(line_item.subtotal),
        },
    )
    await db.commit()
    return await get_deal_or_404(db, deal.id, team_id=team_id, include_detail=True)


async def remove_deal_line_item(
    db: AsyncSession,
    deal_id: UUID,
    line_item_id: UUID,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> Deal:
    """Remove a product from a deal."""
    deal = await get_deal_or_404(db, deal_id, team_id=team_id, include_detail=True)
    line_item = next((item for item in deal.line_items if item.id == line_item_id), None)
    if line_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Line item not found.")

    previous_sum = _current_line_item_sum(deal.line_items)
    line_item_id_str = str(line_item.id)
    await log_audit(
        db,
        action="deal.line_item.deleted",
        entity_type="deal_line_item",
        entity_id=line_item_id_str,
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"deal_id": str(deal.id), "product_id": str(line_item.product_id)},
    )
    await db.delete(line_item)
    deal.line_items = [item for item in deal.line_items if item.id != line_item_id]
    await _recalculate_deal_amount(deal, previous_sum=previous_sum)
    await db.commit()
    return await get_deal_or_404(db, deal.id, team_id=team_id, include_detail=True)


async def list_deal_stakeholders(
    db: AsyncSession,
    deal_id: UUID,
    *,
    team_id: UUID,
) -> list[DealContactRole]:
    """Return stakeholders for a deal newest first."""
    deal = await get_deal_or_404(db, deal_id, team_id=team_id)
    result = await db.execute(
        select(DealContactRole)
        .options(selectinload(DealContactRole.contact))
        .where(DealContactRole.team_id == team_id, DealContactRole.deal_id == deal.id)
        .order_by(DealContactRole.created_at.desc())
    )
    return list(result.scalars().all())


async def create_deal_stakeholder(
    db: AsyncSession,
    deal_id: UUID,
    payload: DealContactRoleCreate,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> DealContactRole:
    """Attach a contact to an account-linked deal as a stakeholder."""
    deal = await get_deal_or_404(db, deal_id, team_id=team_id)
    await _validate_deal_stakeholder_payload(db, deal, payload.contact_id, team_id=team_id)

    existing = await _get_stakeholder_by_contact(db, deal_id=deal.id, contact_id=payload.contact_id, team_id=team_id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This contact is already a stakeholder on the deal. Update the role instead.",
        )

    stakeholder = DealContactRole(
        team_id=team_id,
        deal_id=deal.id,
        contact_id=payload.contact_id,
        role=payload.role,
    )
    db.add(stakeholder)
    await db.flush()
    await log_audit(
        db,
        action="stakeholder.created",
        entity_type="deal_contact_role",
        entity_id=str(stakeholder.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={
            "deal_id": str(deal.id),
            "contact_id": str(payload.contact_id),
            "role": payload.role,
        },
    )
    await db.commit()
    return await _get_stakeholder_or_404(db, stakeholder.id, deal_id=deal.id, team_id=team_id)


async def update_deal_stakeholder(
    db: AsyncSession,
    deal_id: UUID,
    stakeholder_id: UUID,
    payload: DealContactRoleUpdate,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> DealContactRole:
    """Update a stakeholder role on a deal."""
    stakeholder = await _get_stakeholder_or_404(db, stakeholder_id, deal_id=deal_id, team_id=team_id)
    stakeholder.role = payload.role
    await log_audit(
        db,
        action="stakeholder.updated",
        entity_type="deal_contact_role",
        entity_id=str(stakeholder.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={
            "deal_id": str(deal_id),
            "contact_id": str(stakeholder.contact_id),
            "role": payload.role,
        },
    )
    await db.commit()
    return await _get_stakeholder_or_404(db, stakeholder.id, deal_id=deal_id, team_id=team_id)


async def delete_deal_stakeholder(
    db: AsyncSession,
    deal_id: UUID,
    stakeholder_id: UUID,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> None:
    """Remove a stakeholder from a deal."""
    stakeholder = await _get_stakeholder_or_404(db, stakeholder_id, deal_id=deal_id, team_id=team_id)
    await log_audit(
        db,
        action="stakeholder.deleted",
        entity_type="deal_contact_role",
        entity_id=str(stakeholder.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={
            "deal_id": str(deal_id),
            "contact_id": str(stakeholder.contact_id),
            "role": stakeholder.role,
        },
    )
    await db.delete(stakeholder)
    await db.commit()


async def _validate_deal_payload(db: AsyncSession, payload: DealCreate, *, team_id: UUID) -> None:
    """Validate deal relationships and required business rules."""
    if payload.contact_id is None and payload.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of contact_id or account_id is required.",
        )

    team = await db.get(Team, team_id)
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found.",
        )

    stage = await db.get(DealStage, payload.stage_id)
    if stage is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found.",
        )
    if stage.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stage must belong to the same team as the deal.",
        )

    if payload.owner_user_id is not None:
        owner = await db.get(User, payload.owner_user_id)
        if owner is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Owner user not found.",
            )
        if owner.team_id != team_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Owner must belong to the same team as the deal.",
            )

    if payload.contact_id is not None:
        contact = await db.get(Contact, payload.contact_id)
        if contact is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact not found.",
            )
        if contact.team_id != team_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contact must belong to the same team as the deal.",
            )

    if payload.account_id is not None:
        account = await db.get(Account, payload.account_id)
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found.",
            )
        if account.team_id != team_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account must belong to the same team as the deal.",
            )


async def _recalculate_deal_amount(deal: Deal, *, previous_sum: Decimal) -> None:
    """Keep deal amount aligned to line items unless a manual override already exists."""
    current_sum = _current_line_item_sum(deal.line_items)
    current_amount = _quantize(deal.amount) if deal.amount is not None else None
    auto_managed = current_amount is None or (previous_sum > DECIMAL_ZERO and current_amount == previous_sum)
    if auto_managed:
        deal.amount = current_sum if current_sum > DECIMAL_ZERO else None


def _current_line_item_sum(line_items: list[DealLineItem]) -> Decimal:
    return sum((_quantize(item.subtotal) for item in line_items), start=DECIMAL_ZERO)


def _quantize(value: Decimal | float | int | None) -> Decimal:
    if value is None:
        return DECIMAL_ZERO
    return Decimal(str(value)).quantize(Decimal("0.01"))


async def _validate_deal_stakeholder_payload(
    db: AsyncSession,
    deal: Deal,
    contact_id: UUID,
    *,
    team_id: UUID,
) -> None:
    if deal.account_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stakeholders are only available for account-linked deals.",
        )

    contact = await db.get(Contact, contact_id)
    if contact is None or contact.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found.",
        )


async def _get_stakeholder_by_contact(
    db: AsyncSession,
    *,
    deal_id: UUID,
    contact_id: UUID,
    team_id: UUID,
) -> DealContactRole | None:
    result = await db.execute(
        select(DealContactRole).where(
            DealContactRole.team_id == team_id,
            DealContactRole.deal_id == deal_id,
            DealContactRole.contact_id == contact_id,
        )
    )
    return result.scalar_one_or_none()


async def _get_stakeholder_or_404(
    db: AsyncSession,
    stakeholder_id: UUID,
    *,
    deal_id: UUID,
    team_id: UUID,
) -> DealContactRole:
    result = await db.execute(
        select(DealContactRole)
        .options(selectinload(DealContactRole.contact))
        .where(
            DealContactRole.id == stakeholder_id,
            DealContactRole.team_id == team_id,
            DealContactRole.deal_id == deal_id,
        )
    )
    stakeholder = result.scalar_one_or_none()
    if stakeholder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stakeholder not found.",
        )
    return stakeholder
