"""Meetings API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthContext, get_auth_context
from app.core.db import get_db
from app.schemas.crm import MeetingCreate, MeetingRead, MeetingUpdate
from app.services.meetings import (
    cancel_meeting,
    create_meeting,
    delete_meeting,
    generate_ics,
    get_upcoming_meetings,
    list_meetings,
    mark_completed,
    update_meeting,
)

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.get("", response_model=list[MeetingRead])
async def get_meetings(
    status_filter: str | None = None,
    type_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[MeetingRead]:
    """Return meetings for the authenticated team."""
    return await list_meetings(
        db,
        team_id=auth.team_id,
        status_filter=status_filter,
        type_filter=type_filter,
    )


@router.get("/upcoming", response_model=list[MeetingRead])
async def get_upcoming(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[MeetingRead]:
    """Return upcoming meetings for the dashboard."""
    return await get_upcoming_meetings(db, team_id=auth.team_id, limit=5)


@router.post("", response_model=MeetingRead, status_code=status.HTTP_201_CREATED)
async def post_meeting(
    payload: MeetingCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> MeetingRead:
    """Create a new meeting."""
    return await create_meeting(db, payload, team_id=auth.team_id, actor_id=auth.user_id)


@router.patch("/{meeting_id}", response_model=MeetingRead)
async def patch_meeting(
    meeting_id: UUID,
    payload: MeetingUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> MeetingRead:
    """Update a meeting."""
    return await update_meeting(
        db,
        meeting_id,
        payload,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )


@router.patch("/{meeting_id}/complete", response_model=MeetingRead)
async def complete_meeting(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> MeetingRead:
    """Mark a meeting as completed."""
    return await mark_completed(db, meeting_id, team_id=auth.team_id, actor_id=auth.user_id)


@router.patch("/{meeting_id}/cancel", response_model=MeetingRead)
async def patch_cancel_meeting(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> MeetingRead:
    """Cancel a meeting."""
    return await cancel_meeting(db, meeting_id, team_id=auth.team_id, actor_id=auth.user_id)


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting_route(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> None:
    """Delete a meeting."""
    await delete_meeting(db, meeting_id, team_id=auth.team_id, actor_id=auth.user_id)


@router.get("/{meeting_id}/ics")
async def get_meeting_ics(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> Response:
    """Generate and return an ICS file for the meeting."""
    ics_content = await generate_ics(db, meeting_id, team_id=auth.team_id, actor_id=auth.user_id)
    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename=meeting_{meeting_id}.ics"},
    )
