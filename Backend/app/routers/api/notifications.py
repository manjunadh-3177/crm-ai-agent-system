"""Notifications API router."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthContext, get_auth_context
from app.core.db import get_db
from app.schemas.crm import NotificationRead
from app.services.notifications import (
    count_unread,
    delete_notification,
    list_notifications,
    mark_all_read,
    mark_notification_read,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=list[NotificationRead])
async def get_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[NotificationRead]:
    """List notifications for the current team."""
    return await list_notifications(
        db, team_id=auth.team_id, unread_only=unread_only, limit=limit
    )


@router.get("/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> dict:
    """Return unread notification count for the badge."""
    n = await count_unread(db, team_id=auth.team_id)
    return {"unread_count": n}


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def post_mark_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> NotificationRead:
    """Mark a single notification as read."""
    notification = await mark_notification_read(
        db, notification_id=notification_id, team_id=auth.team_id
    )
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    return notification


@router.post("/read-all")
async def post_mark_all_read(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> dict:
    """Mark all notifications as read."""
    updated = await mark_all_read(db, team_id=auth.team_id)
    return {"updated": updated}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification_route(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> Response:
    """Delete a notification."""
    deleted = await delete_notification(
        db, notification_id=notification_id, team_id=auth.team_id
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
