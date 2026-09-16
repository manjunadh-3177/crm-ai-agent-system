"""Service for creating and managing in-app notifications."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


async def create_notification(
    db: AsyncSession,
    *,
    team_id: UUID,
    type: str,
    title: str,
    message: str,
    user_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> Notification:
    """Persist a new notification record."""
    notification = Notification(
        team_id=team_id,
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
        is_read=False,
    )
    db.add(notification)
    # Caller is responsible for commit
    return notification


async def list_notifications(
    db: AsyncSession,
    *,
    team_id: UUID,
    unread_only: bool = False,
    limit: int = 50,
) -> list[Notification]:
    """Return notifications for a team, newest first."""
    query = (
        select(Notification)
        .where(Notification.team_id == team_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    result = await db.execute(query)
    return list(result.scalars().all())


async def mark_notification_read(
    db: AsyncSession,
    *,
    notification_id: UUID,
    team_id: UUID,
) -> Notification | None:
    """Mark a single notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.team_id == team_id,
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        return None
    notification.is_read = True
    await db.commit()
    await db.refresh(notification)
    return notification


async def mark_all_read(db: AsyncSession, *, team_id: UUID) -> int:
    """Mark all unread notifications as read. Returns count updated."""
    result = await db.execute(
        update(Notification)
        .where(Notification.team_id == team_id, Notification.is_read.is_(False))
        .values(is_read=True)
        .returning(Notification.id)
    )
    await db.commit()
    return len(result.fetchall())


async def delete_notification(
    db: AsyncSession,
    *,
    notification_id: UUID,
    team_id: UUID,
) -> bool:
    """Delete a notification. Returns True if deleted."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.team_id == team_id,
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        return False
    await db.delete(notification)
    await db.commit()
    return True


async def count_unread(db: AsyncSession, *, team_id: UUID) -> int:
    """Return number of unread notifications for a team."""
    result = await db.execute(
        select(Notification).where(
            Notification.team_id == team_id,
            Notification.is_read.is_(False),
        )
    )
    return len(result.scalars().all())
