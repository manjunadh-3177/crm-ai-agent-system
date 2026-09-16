"""Automations service — V2.

Supported triggers:
  contact.created, deal.created, lead.qualified_hot, meeting.completed, task.overdue

Supported conditions:
  always, lead_tier_equals, deal_health_equals

Supported actions:
  notify_user, create_task, assign_owner, create_meeting, change_status, draft_email
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.events import emit_event
from app.models.automation import AutomationRule
from app.schemas.ai import DraftEmailResponse
from app.schemas.crm import AutomationRuleCreate, AutomationRuleUpdate, NoteCreate, TaskCreate
from app.services.audit import log_audit

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------

async def list_rules(db: AsyncSession, team_id: UUID) -> list[AutomationRule]:
    """List automation rules for a team (newest first)."""
    result = await db.execute(
        select(AutomationRule)
        .where(AutomationRule.team_id == team_id)
        .order_by(AutomationRule.created_at.desc())
    )
    return list(result.scalars().all())


async def get_rule_or_404(db: AsyncSession, rule_id: UUID, team_id: UUID) -> AutomationRule:
    """Get an automation rule by ID, scoped to team."""
    rule = await db.get(AutomationRule, rule_id)
    if not rule or rule.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation rule not found.")
    return rule


async def create_rule(
    db: AsyncSession,
    payload: AutomationRuleCreate,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> AutomationRule:
    """Create a new automation rule."""
    rule = AutomationRule(team_id=team_id, **payload.model_dump())
    db.add(rule)
    await db.flush()
    await log_audit(
        db,
        action="automation.created",
        entity_type="automation_rule",
        entity_id=str(rule.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"name": rule.name, "trigger": rule.trigger_type, "action": rule.action_type},
    )
    await db.commit()
    await emit_event("automation.created", {"id": str(rule.id), "team_id": str(team_id)})
    return rule


async def update_rule(
    db: AsyncSession,
    rule_id: UUID,
    payload: AutomationRuleUpdate,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> AutomationRule:
    """Update an automation rule."""
    rule = await get_rule_or_404(db, rule_id, team_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(rule, field, value)
    await log_audit(
        db,
        action="automation.updated",
        entity_type="automation_rule",
        entity_id=str(rule.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"updated_fields": list(data.keys())},
    )
    await db.commit()
    await emit_event("automation.updated", {"id": str(rule.id), "team_id": str(team_id)})
    return rule


async def delete_rule(
    db: AsyncSession,
    rule_id: UUID,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> None:
    """Delete an automation rule."""
    rule = await get_rule_or_404(db, rule_id, team_id)
    await log_audit(
        db,
        action="automation.deleted",
        entity_type="automation_rule",
        entity_id=str(rule.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"name": rule.name},
    )
    await db.delete(rule)
    await db.commit()
    await emit_event("automation.deleted", {"id": str(rule_id), "team_id": str(team_id)})


# ---------------------------------------------------------------------------
# V2 Condition evaluator
# ---------------------------------------------------------------------------

def evaluate_condition(condition: str, condition_value: Any, payload: dict[str, Any]) -> bool:
    """Evaluate a single condition against an event payload."""
    if condition == "always":
        return True

    if condition == "stage_equals" and "stage" in payload:
        return str(payload["stage"]).lower() == str(condition_value).lower()

    if condition == "deal_value_gt" and "amount" in payload:
        try:
            return float(payload["amount"]) > float(condition_value)
        except (ValueError, TypeError):
            return False

    if condition == "priority_equals" and "priority" in payload:
        return str(payload.get("priority", "")).lower() == str(condition_value).lower()

    # V2 new conditions
    if condition == "lead_tier_equals" and "lead_tier" in payload:
        return str(payload.get("lead_tier", "")).lower() == str(condition_value).lower()

    if condition == "deal_health_equals" and "deal_health" in payload:
        return str(payload.get("deal_health", "")).lower() == str(condition_value).lower()

    return False


# ---------------------------------------------------------------------------
# V2 Action executor
# ---------------------------------------------------------------------------

async def _execute_action(
    db: AsyncSession,
    rule: AutomationRule,
    trigger_type: str,
    payload: dict[str, Any],
    team_id: UUID,
) -> None:
    """Execute a single rule action. Raises on unrecoverable error."""
    action = rule.action_type
    action_payload = rule.action_payload_json or {}

    # ── create_task ─────────────────────────────────────────────────────────
    if action == "create_task":
        from app.services.tasks import create_task
        deal_id_raw = (
            action_payload.get("deal_id")
            or payload.get("deal_id")
            or (payload.get("id") if trigger_type.startswith("deal") else None)
        )
        task_create = TaskCreate(
            title=action_payload.get("title", f"Automated: {rule.name}"),
            description=action_payload.get("description", "Created by automation rule."),
            priority=action_payload.get("priority", "med"),
            status="open",
            contact_id=payload.get("contact_id"),
            account_id=payload.get("account_id"),
            deal_id=str(deal_id_raw) if deal_id_raw else None,
            assigned_user_id=action_payload.get("assigned_user_id"),
        )
        await create_task(db, task_create, team_id=team_id, actor_id="automation")

    # ── create_note ──────────────────────────────────────────────────────────
    elif action == "create_note":
        from app.services.notes import create_note
        entity_id = action_payload.get("entity_id") or payload.get("id")
        entity_type = action_payload.get("entity_type", "deal")
        if entity_id:
            note_create = NoteCreate(
                body=action_payload.get("body", f"Automated Note — {rule.name}"),
                entity_type=entity_type,
                entity_id=UUID(str(entity_id)),
            )
            await create_note(db, note_create, team_id=team_id, actor_id="automation")
        else:
            logger.warning("Rule %s: create_note skipped — no entity_id", rule.id)

    # ── notify_user ──────────────────────────────────────────────────────────
    elif action == "notify_user":
        from app.services.notifications import create_notification
        await create_notification(
            db,
            team_id=team_id,
            type="automation.notification",
            title=action_payload.get("title", f"Automation: {rule.name}"),
            message=action_payload.get("message", f"Rule '{rule.name}' triggered on {trigger_type}."),
            entity_type=action_payload.get("entity_type"),
            entity_id=action_payload.get("entity_id") or payload.get("id"),
        )

    # ── create_notification (legacy alias for notify_user) ───────────────────
    elif action == "create_notification":
        from app.services.notifications import create_notification
        await create_notification(
            db,
            team_id=team_id,
            type="automation.notification",
            title=action_payload.get("title", f"Automation: {rule.name}"),
            message=action_payload.get("message", f"Rule '{rule.name}' executed on {trigger_type}."),
            entity_type=action_payload.get("entity_type"),
            entity_id=action_payload.get("entity_id") or payload.get("id"),
        )

    # ── assign_owner ──────────────────────────────────────────────────────────
    elif action == "assign_owner":
        owner_id = action_payload.get("assigned_user_id")
        if not owner_id:
            logger.warning("Rule %s: assign_owner skipped — no assigned_user_id in payload", rule.id)
            return
        entity_id_raw = payload.get("id")
        if not entity_id_raw:
            return
        entity_id = UUID(str(entity_id_raw))

        if trigger_type.startswith("task"):
            from app.models.task import Task
            task = await db.get(Task, entity_id)
            if task and task.team_id == team_id:
                task.assigned_user_id = owner_id
                await db.flush()
        elif trigger_type.startswith("deal"):
            from app.models.deal import Deal
            deal = await db.get(Deal, entity_id)
            if deal and deal.team_id == team_id:
                deal.owner_id = owner_id if hasattr(deal, "owner_id") else deal.owner_id
                await db.flush()
        elif trigger_type.startswith("contact"):
            from app.models.contact import Contact
            contact = await db.get(Contact, entity_id)
            if contact and contact.team_id == team_id and hasattr(contact, "assigned_user_id"):
                contact.assigned_user_id = owner_id
                await db.flush()

    # ── create_meeting ────────────────────────────────────────────────────────
    elif action == "create_meeting":
        from datetime import timedelta

        from app.schemas.crm import MeetingCreate
        from app.services.meetings import create_meeting
        contact_id = action_payload.get("contact_id") or payload.get("contact_id")
        if not contact_id:
            logger.warning("Rule %s: create_meeting skipped — no contact_id", rule.id)
            return
        now = datetime.now(UTC)
        offset_days = int(action_payload.get("days_from_now", 1))
        starts = now.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=offset_days)
        ends = starts + timedelta(minutes=int(action_payload.get("duration_minutes", 30)))
        deal_id_raw = action_payload.get("deal_id") or payload.get("deal_id") or (
            payload.get("id") if trigger_type.startswith("deal") else None
        )
        meeting_create = MeetingCreate(
            title=action_payload.get("title", f"Follow-up: {rule.name}"),
            description=action_payload.get("description", "Auto-scheduled by automation."),
            starts_at=starts,
            ends_at=ends,
            timezone="UTC",
            meeting_type=action_payload.get("meeting_type", "call"),
            contact_id=UUID(str(contact_id)),
            deal_id=UUID(str(deal_id_raw)) if deal_id_raw else None,
        )
        await create_meeting(db, meeting_create, team_id=team_id, actor_id="automation")

    # ── change_status ─────────────────────────────────────────────────────────
    elif action == "change_status":
        new_status = action_payload.get("status")
        if not new_status:
            logger.warning("Rule %s: change_status skipped — no status in payload", rule.id)
            return
        entity_id_raw = payload.get("id")
        if not entity_id_raw:
            return
        entity_id = UUID(str(entity_id_raw))

        if trigger_type.startswith("task"):
            from app.models.task import Task
            task = await db.get(Task, entity_id)
            if task and task.team_id == team_id:
                task.status = new_status
                await db.flush()
        elif trigger_type.startswith("deal"):
            from app.models.deal import Deal
            deal = await db.get(Deal, entity_id)
            if deal and deal.team_id == team_id and hasattr(deal, "status"):
                deal.status = new_status
                await db.flush()

    # ── create_ai_email_approval ──────────────────────────────────────────────
    elif action in {"create_ai_email_approval", "draft_email"}:
        from app.services.ai_email import persist_draft_and_approval
        contact_id = action_payload.get("contact_id") or payload.get("contact_id")
        if contact_id:
            draft_response = DraftEmailResponse(
                subject=action_payload.get("subject", "Automated Follow-up"),
                body=action_payload.get("body", "Please review this automated email."),
                tone="professional",
            )
            deal_id_raw = (
                action_payload.get("deal_id")
                or payload.get("deal_id")
                or (payload.get("id") if trigger_type.startswith("deal") else None)
            )
            await persist_draft_and_approval(
                db,
                contact_id=UUID(str(contact_id)),
                team_id=team_id,
                deal_id=UUID(str(deal_id_raw)) if deal_id_raw else None,
                response=draft_response,
            )
        else:
            logger.warning("Rule %s: create_ai_email_approval skipped — no contact_id", rule.id)

    else:
        logger.warning("Rule %s: unknown action type '%s'", rule.id, action)


# ---------------------------------------------------------------------------
# V2 Trigger runner
# ---------------------------------------------------------------------------

async def run_trigger(
    db: AsyncSession,
    trigger_type: str,
    payload: dict[str, Any],
    team_id: UUID,
) -> None:
    """Run all enabled automation rules matching the trigger type."""
    result = await db.execute(
        select(AutomationRule).where(
            AutomationRule.team_id == team_id,
            AutomationRule.trigger_type == trigger_type,
            AutomationRule.is_enabled.is_(True),
        )
    )
    rules = result.scalars().all()

    for rule in rules:
        try:
            conditions = rule.conditions_json or {}
            condition_type = conditions.get("type", "always")
            condition_value = conditions.get("value")

            if not evaluate_condition(condition_type, condition_value, payload):
                continue

            await _execute_action(db, rule, trigger_type, payload, team_id)

            # Update execution tracking
            rule.run_count = (rule.run_count or 0) + 1
            rule.last_run_at = datetime.now(UTC)

            await log_audit(
                db,
                action="automation.executed",
                entity_type="automation_rule",
                entity_id=str(rule.id),
                actor_type="system",
                team_id=team_id,
                actor_id="automation",
                metadata={"trigger": trigger_type, "action": rule.action_type},
            )
            await db.commit()

        except Exception as e:
            logger.error("Error executing automation rule %s: %s", rule.id, e)
            await db.rollback()
            continue
