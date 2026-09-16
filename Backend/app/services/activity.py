"""Activity feed service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.note import Note
from app.schemas.crm import ActivityFeedItem


async def get_activity_feed(
    db: AsyncSession,
    *,
    team_id: UUID,
    limit: int = 50,
) -> list[ActivityFeedItem]:
    """Get unified activity feed combining audit logs and notes."""

    # Get recent audit logs
    logs_query = (
        select(AuditLog)
        .where(AuditLog.team_id == team_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    logs_result = await db.execute(logs_query)
    logs = logs_result.scalars().all()

    # Get recent notes
    notes_query = (
        select(Note)
        .where(Note.team_id == team_id)
        .order_by(Note.created_at.desc())
        .limit(limit)
    )
    notes_result = await db.execute(notes_query)
    notes = notes_result.scalars().all()

    # Combine and sort
    items: list[ActivityFeedItem] = []

    for log in logs:
        # Avoid showing "note.created" etc as audit logs if we already show the note itself,
        # but the prompt says combining recent audit_logs and recent notes. Let's include everything.
        # Actually, let's filter out note audit logs to avoid duplicates if possible, or just leave them.
        items.append(
            ActivityFeedItem(
                id=log.id,
                type="audit_log",
                time=log.created_at,
                title=log.action,
                description=f"{log.actor_type} performed {log.action}",
                actor_id=log.actor_id,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                metadata_json=log.metadata_json,
            )
        )

    for note in notes:
        items.append(
            ActivityFeedItem(
                id=note.id,
                type="note",
                time=note.created_at,
                title="Note Added",
                description=note.body,
                actor_id=note.created_by_user_id,
                entity_type=note.entity_type,
                entity_id=str(note.entity_id),
                metadata_json=None,
            )
        )

    # Sort by time descending and limit
    items.sort(key=lambda x: x.time, reverse=True)
    return items[:limit]
