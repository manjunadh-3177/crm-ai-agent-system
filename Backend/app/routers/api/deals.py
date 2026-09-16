"""Deal routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.proposal_agent import run_proposal_agent
from app.core.auth import AuthContext, get_auth_context
from app.core.db import get_db
from app.schemas.crm import (
    BulkDealStageUpdateRequest,
    BulkOperationResponse,
    DealContactRoleCreate,
    DealContactRoleRead,
    DealContactRoleUpdate,
    DealCreate,
    DealDetailRead,
    DealLineItemCreate,
    DealLineItemUpdate,
    DealStageUpdate,
    DealSummaryRead,
    DealTimelineItem,
    DealUpdate,
    ProposalDraftResponse,
)
from app.services.audit import list_deal_timeline
from app.services.deals import (
    add_deal_line_item,
    create_deal,
    create_deal_stakeholder,
    delete_deal_stakeholder,
    get_deal_or_404,
    list_deal_stakeholders,
    list_deals,
    remove_deal_line_item,
    update_deal,
    update_deal_line_item,
    update_deal_stage,
    update_deal_stakeholder,
)
from app.services.import_export import bulk_update_deal_stage

router = APIRouter(tags=["deals"])


@router.get("/deals", response_model=list[DealSummaryRead])
async def get_deals(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[DealSummaryRead]:
    """Return all deals."""
    return await list_deals(db, team_id=auth.team_id)


@router.get("/deals/{deal_id}", response_model=DealDetailRead)
async def get_deal_detail(
    deal_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> DealDetailRead:
    """Return a single deal with line items and related entities."""
    return await get_deal_or_404(db, deal_id, team_id=auth.team_id, include_detail=True)


@router.get("/deals/{deal_id}/timeline", response_model=list[DealTimelineItem])
async def get_deal_timeline(
    deal_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[DealTimelineItem]:
    """Return audit-log-backed timeline items for a deal."""
    await get_deal_or_404(db, deal_id, team_id=auth.team_id)
    return await list_deal_timeline(db, deal_id, team_id=auth.team_id)


@router.get("/deals/{deal_id}/stakeholders", response_model=list[DealContactRoleRead])
async def get_deal_stakeholders(
    deal_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[DealContactRoleRead]:
    """Return stakeholders for a single deal."""
    return await list_deal_stakeholders(db, deal_id, team_id=auth.team_id)


@router.post("/deals", response_model=DealSummaryRead, status_code=status.HTTP_201_CREATED)
async def post_deal(
    payload: DealCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> DealSummaryRead:
    """Create a deal."""
    return await create_deal(db, payload, team_id=auth.team_id, actor_id=auth.user_id)


@router.patch("/deals/{deal_id}", response_model=DealSummaryRead)
async def patch_deal(
    deal_id: UUID,
    payload: DealUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> DealSummaryRead:
    """Update a deal."""
    return await update_deal(
        db,
        deal_id,
        payload,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )


@router.patch("/deals/{deal_id}/stage", response_model=DealSummaryRead)
async def patch_deal_stage(
    deal_id: UUID,
    payload: DealStageUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> DealSummaryRead:
    """Move a deal to another stage."""
    return await update_deal_stage(
        db,
        deal_id,
        payload,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )


@router.post("/deals/bulk-stage", response_model=BulkOperationResponse)
async def post_bulk_deal_stage(
    payload: BulkDealStageUpdateRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> BulkOperationResponse:
    """Move multiple deals to the same stage."""
    return await bulk_update_deal_stage(
        db,
        payload,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )


@router.post("/deals/{deal_id}/line-items", response_model=DealDetailRead, status_code=status.HTTP_201_CREATED)
async def post_deal_line_item(
    deal_id: UUID,
    payload: DealLineItemCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> DealDetailRead:
    """Attach a product to a deal."""
    return await add_deal_line_item(
        db,
        deal_id,
        payload,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )


@router.post("/deals/{deal_id}/stakeholders", response_model=DealContactRoleRead, status_code=status.HTTP_201_CREATED)
async def post_deal_stakeholder(
    deal_id: UUID,
    payload: DealContactRoleCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> DealContactRoleRead:
    """Attach a stakeholder contact to a deal."""
    return await create_deal_stakeholder(
        db,
        deal_id,
        payload,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )


@router.patch("/deals/{deal_id}/line-items/{line_item_id}", response_model=DealDetailRead)
async def patch_deal_line_item(
    deal_id: UUID,
    line_item_id: UUID,
    payload: DealLineItemUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> DealDetailRead:
    """Update an existing line item."""
    return await update_deal_line_item(
        db,
        deal_id,
        line_item_id,
        payload,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )


@router.patch("/deals/{deal_id}/stakeholders/{stakeholder_id}", response_model=DealContactRoleRead)
async def patch_deal_stakeholder(
    deal_id: UUID,
    stakeholder_id: UUID,
    payload: DealContactRoleUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> DealContactRoleRead:
    """Update an existing stakeholder role."""
    return await update_deal_stakeholder(
        db,
        deal_id,
        stakeholder_id,
        payload,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )


@router.delete("/deals/{deal_id}/line-items/{line_item_id}", response_model=DealDetailRead)
async def delete_deal_line_item(
    deal_id: UUID,
    line_item_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> DealDetailRead:
    """Remove a line item from a deal."""
    return await remove_deal_line_item(
        db,
        deal_id,
        line_item_id,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )


@router.delete("/deals/{deal_id}/stakeholders/{stakeholder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stakeholder(
    deal_id: UUID,
    stakeholder_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> None:
    """Remove a stakeholder from a deal."""
    await delete_deal_stakeholder(
        db,
        deal_id,
        stakeholder_id,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )


@router.post("/deals/{deal_id}/proposal", response_model=ProposalDraftResponse)
async def post_deal_proposal(
    deal_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> ProposalDraftResponse:
    """Generate a proposal draft for a deal."""
    draft = await run_proposal_agent(
        db,
        deal_id=deal_id,
        team_id=auth.team_id,
        actor_id=auth.user_id,
        trigger="manual",
        force=True,
    )
    if draft is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Proposal generation failed.")
    return draft
