"""Reusable audit logging helpers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog
from app.schemas.crm import DealTimelineItem


async def log_audit(
    db: AsyncSession,
    *,
    action: str,
    entity_type: str,
    actor_type: str,
    team_id: UUID | None = None,
    actor_id: str | None = None,
    entity_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Persist an audit log row in the current transaction."""
    row = AuditLog(
        team_id=team_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=metadata or {},
    )
    db.add(row)
    await db.flush()
    return row


async def list_audit_logs(db: AsyncSession, *, team_id: UUID) -> list[AuditLog]:
    """Return audit logs newest first."""
    result = await db.execute(
        select(AuditLog).where(AuditLog.team_id == team_id).order_by(AuditLog.created_at.desc())
    )
    return list(result.scalars().all())


async def list_audit_logs_by_actions(
    db: AsyncSession,
    actions: list[str],
    *,
    team_id: UUID,
    limit: int = 20,
) -> list[AuditLog]:
    """Return filtered audit logs newest first."""
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.action.in_(actions), AuditLog.team_id == team_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_deal_timeline(
    db: AsyncSession,
    deal_id: UUID,
    *,
    team_id: UUID,
) -> list[DealTimelineItem]:
    """Return deal timeline items derived from audit logs only."""
    relevant_actions = [
        "deal.created",
        "deal.stage_changed",
        "proposal.generated",
        "approval.created",
        "approval.approved",
        "approval.rejected",
        "email.executed",
    ]
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.team_id == team_id, AuditLog.action.in_(relevant_actions))
        .order_by(AuditLog.created_at.desc())
    )
    logs = list(result.scalars().all())
    deal_id_str = str(deal_id)
    timeline: list[DealTimelineItem] = []
    for log in logs:
        metadata = log.metadata_json or {}
        metadata_deal_id = metadata.get("deal_id")
        if log.entity_type == "deal" and log.entity_id == deal_id_str:
            timeline.append(_to_timeline_item(log))
            continue
        if metadata_deal_id == deal_id_str:
            timeline.append(_to_timeline_item(log))
    return timeline


def _to_timeline_item(log: AuditLog) -> DealTimelineItem:
    metadata = log.metadata_json or {}
    return DealTimelineItem(
        id=log.id,
        type=log.action,
        time=log.created_at,
        description=_describe_timeline_entry(log.action, metadata),
    )


def _describe_timeline_entry(action: str, metadata: dict[str, Any]) -> str:
    if action == "deal.created":
        return "Deal was created."
    if action == "deal.stage_changed":
        from_stage = metadata.get("from_stage_id")
        to_stage = metadata.get("to_stage_id")
        if from_stage or to_stage:
            return f"Deal stage changed from {from_stage or 'unknown'} to {to_stage or 'unknown'}."
        return "Deal stage changed."
    if action == "proposal.generated":
        title = metadata.get("title")
        return f"Proposal draft generated{f': {title}' if title else '.'}"
    if action == "approval.created":
        return "Approval request created for outbound draft."
    if action == "approval.approved":
        return "Approval was approved."
    if action == "approval.rejected":
        return "Approval was rejected."
    if action == "email.executed":
        provider = metadata.get("provider")
        return f"Approved email executed{f' via {provider}' if provider else ''}."
    return action
