"""OpportunityWatchAgent for timely deal and account follow-up signals."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.events import emit_event
from app.models import AuditLog, Deal, Task
from app.services.audit import log_audit
from app.services.notifications import create_notification


logger = logging.getLogger(__name__)

STALE_DAYS = 14
CLOSE_SOON_DAYS = 7
HIGH_VALUE = Decimal("50000.00")
HIGH_VALUE_IDLE_DAYS = 7
ACCOUNT_TOUCH_DAYS = 30


@dataclass(slots=True)
class OpportunitySignal:
    deal: Deal
    kind: str
    title: str
    message: str
    next_action: str
    priority: str = "med"


async def run_opportunity_watch(
    db: AsyncSession,
    *,
    team_id: UUID,
    actor_id: str | None = None,
    deal_id: UUID | None = None,
    trigger: str = "manual",
) -> dict[str, object]:
    """Scan team opportunities and create notifications/tasks for timely actions."""
    try:
        deals = await _load_deals(db, team_id=team_id, deal_id=deal_id)
        if not deals:
            return await _finish(db, team_id, actor_id, trigger, 0, "no_deals")

        latest_activity = await _latest_activity_by_entity(db, team_id=team_id)
        signals: list[OpportunitySignal] = []
        for deal in deals:
            if deal.stage and deal.stage.is_closed:
                continue
            signals.extend(_signals_for_deal(deal, latest_activity))

        created = 0
        for signal in signals:
            if await _recent_signal_exists(db, team_id=team_id, deal_id=signal.deal.id, kind=signal.kind):
                continue
            await _create_signal_outputs(db, signal, team_id=team_id, actor_id=actor_id, trigger=trigger)
            created += 1

        return await _finish(db, team_id, actor_id, trigger, created, "completed")
    except Exception as exc:
        logger.exception("OpportunityWatchAgent failed")
        await db.rollback()
        await log_audit(
            db,
            action="agent.opportunity_watch.failed",
            entity_type="team",
            actor_type="ai",
            team_id=team_id,
            actor_id=actor_id,
            metadata={"trigger": trigger, "reason": str(exc)},
        )
        await db.commit()
        return {"status": "error", "created": 0, "reason": str(exc)}


async def _load_deals(db: AsyncSession, *, team_id: UUID, deal_id: UUID | None) -> list[Deal]:
    query = (
        select(Deal)
        .options(selectinload(Deal.stage), selectinload(Deal.contact), selectinload(Deal.account))
        .where(Deal.team_id == team_id)
    )
    if deal_id is not None:
        query = query.where(Deal.id == deal_id)
    result = await db.execute(query.order_by(Deal.updated_at.desc()))
    return list(result.scalars().all())


async def _latest_activity_by_entity(db: AsyncSession, *, team_id: UUID) -> dict[str, datetime]:
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.team_id == team_id)
        .order_by(AuditLog.created_at.desc())
        .limit(1000)
    )
    latest: dict[str, datetime] = {}
    for log in result.scalars().all():
        if log.entity_type and log.entity_id:
            latest.setdefault(f"{log.entity_type}:{log.entity_id}", log.created_at)
        metadata = log.metadata_json or {}
        deal_id = metadata.get("deal_id")
        if deal_id:
            latest.setdefault(f"deal:{deal_id}", log.created_at)
        account_id = metadata.get("account_id")
        if account_id:
            latest.setdefault(f"account:{account_id}", log.created_at)
    return latest


def _signals_for_deal(deal: Deal, latest_activity: dict[str, datetime]) -> list[OpportunitySignal]:
    now = datetime.now(timezone.utc)
    last_deal_touch = _aware(latest_activity.get(f"deal:{deal.id}") or deal.updated_at)
    idle_days = max((now - last_deal_touch).days, 0)
    signals: list[OpportunitySignal] = []

    if idle_days >= STALE_DAYS:
        signals.append(
            OpportunitySignal(
                deal=deal,
                kind="stale_deal",
                title="Stale deal needs follow-up",
                message=f"{deal.name} has had no recorded activity for {idle_days} days.",
                next_action="Send a focused follow-up and confirm the buying timeline.",
                priority="high",
            )
        )

    if deal.expected_close_date:
        days_to_close = (deal.expected_close_date - now.date()).days
        if 0 <= days_to_close <= CLOSE_SOON_DAYS:
            signals.append(
                OpportunitySignal(
                    deal=deal,
                    kind="close_date_near",
                    title="Close date is approaching",
                    message=f"{deal.name} is expected to close in {days_to_close} days.",
                    next_action="Schedule a closing-plan check-in and confirm decision criteria.",
                    priority="high",
                )
            )

    if deal.amount is not None and deal.amount >= HIGH_VALUE and idle_days >= HIGH_VALUE_IDLE_DAYS:
        signals.append(
            OpportunitySignal(
                deal=deal,
                kind="high_value_idle",
                title="High-value deal is idle",
                message=f"{deal.name} is worth {deal.amount} {deal.currency} and has been idle for {idle_days} days.",
                next_action="Escalate owner attention and prepare executive-level next steps.",
                priority="high",
            )
        )

    if deal.account_id is not None:
        last_account_touch = _aware(latest_activity.get(f"account:{deal.account_id}") or deal.updated_at)
        account_idle_days = max((now - last_account_touch).days, 0)
        if account_idle_days >= ACCOUNT_TOUCH_DAYS:
            signals.append(
                OpportunitySignal(
                    deal=deal,
                    kind="account_no_touch",
                    title="Account has no recent touchpoint",
                    message=f"{deal.account.name if deal.account else 'Account'} has no recorded touchpoint for {account_idle_days} days.",
                    next_action="Create an account touchpoint and update relationship status.",
                    priority="med",
                )
            )

    return signals


async def _recent_signal_exists(db: AsyncSession, *, team_id: UUID, deal_id: UUID, kind: str) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    result = await db.execute(
        select(AuditLog.id)
        .where(
            AuditLog.team_id == team_id,
            AuditLog.action == "agent.opportunity_watch.alert",
            AuditLog.entity_type == "deal",
            AuditLog.entity_id == str(deal_id),
            AuditLog.created_at >= cutoff,
        )
        .limit(20)
    )
    rows = result.scalars().all()
    if not rows:
        return False
    metadata_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.id.in_(rows))
    )
    return any((log.metadata_json or {}).get("kind") == kind for log in metadata_result.scalars().all())


async def _create_signal_outputs(
    db: AsyncSession,
    signal: OpportunitySignal,
    *,
    team_id: UUID,
    actor_id: str | None,
    trigger: str,
) -> None:
    await create_notification(
        db,
        team_id=team_id,
        type=f"opportunity.{signal.kind}",
        title=signal.title,
        message=f"{signal.message} Suggested action: {signal.next_action}",
        entity_type="deal",
        entity_id=str(signal.deal.id),
    )
    task = Task(
        team_id=team_id,
        title=f"{signal.title}: {signal.deal.name}",
        description=f"{signal.message}\n\nNext best action: {signal.next_action}",
        priority=signal.priority,
        status="open",
        deal_id=signal.deal.id,
        contact_id=signal.deal.contact_id,
        account_id=signal.deal.account_id,
        assigned_user_id=str(signal.deal.owner_user_id) if signal.deal.owner_user_id else None,
        due_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db.add(task)
    await db.flush()
    await log_audit(
        db,
        action="task.created",
        entity_type="task",
        entity_id=str(task.id),
        actor_type="ai",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"deal_id": str(signal.deal.id), "source": "OpportunityWatchAgent", "kind": signal.kind},
    )
    await log_audit(
        db,
        action="agent.opportunity_watch.alert",
        entity_type="deal",
        entity_id=str(signal.deal.id),
        actor_type="ai",
        team_id=team_id,
        actor_id=actor_id,
        metadata={
            "kind": signal.kind,
            "trigger": trigger,
            "message": signal.message,
            "next_best_action": signal.next_action,
            "task_id": str(task.id),
        },
    )


async def _finish(
    db: AsyncSession,
    team_id: UUID,
    actor_id: str | None,
    trigger: str,
    created: int,
    status: str,
) -> dict[str, object]:
    action = "agent.opportunity_watch.completed" if status == "completed" else "agent.opportunity_watch.no_action"
    await log_audit(
        db,
        action=action,
        entity_type="team",
        actor_type="ai",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"trigger": trigger, "signals_created": created, "status": status},
    )
    await db.commit()
    await emit_event("agent.opportunity_watch.completed", {"team_id": str(team_id), "signals_created": created})
    return {"status": status, "signals_created": created}


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
