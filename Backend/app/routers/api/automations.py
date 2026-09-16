"""Automations API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthContext, get_auth_context
from app.core.db import get_db
from app.schemas.crm import AutomationRuleCreate, AutomationRuleOut, AutomationRuleUpdate
from app.services.automations import (
    create_rule,
    delete_rule,
    list_rules,
    update_rule,
)

router = APIRouter(prefix="/automations", tags=["automations"])


@router.get("", response_model=list[AutomationRuleOut])
async def get_rules(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[AutomationRuleOut]:
    """Return automation rules for the authenticated team."""
    return await list_rules(db, team_id=auth.team_id)


@router.post("", response_model=AutomationRuleOut, status_code=status.HTTP_201_CREATED)
async def post_rule(
    payload: AutomationRuleCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> AutomationRuleOut:
    """Create a new automation rule."""
    return await create_rule(db, payload, team_id=auth.team_id, actor_id=auth.user_id)


@router.patch("/{rule_id}", response_model=AutomationRuleOut)
async def patch_rule(
    rule_id: UUID,
    payload: AutomationRuleUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> AutomationRuleOut:
    """Update an automation rule."""
    return await update_rule(
        db,
        rule_id,
        payload,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )


@router.post("/{rule_id}/toggle", response_model=AutomationRuleOut)
async def toggle_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> AutomationRuleOut:
    """Toggle the enabled status of an automation rule."""
    # First, get the current rule to find its state
    from app.services.automations import get_rule_or_404
    rule = await get_rule_or_404(db, rule_id, auth.team_id)

    payload = AutomationRuleUpdate(is_enabled=not rule.is_enabled)
    return await update_rule(
        db,
        rule_id,
        payload,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule_route(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> None:
    """Delete an automation rule."""
    await delete_rule(db, rule_id, team_id=auth.team_id, actor_id=auth.user_id)
