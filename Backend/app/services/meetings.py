"""Meetings service layer."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from icalendar import Calendar, Event

from app.events import emit_event
from app.models import Account, Contact, Deal, Meeting, Team
from app.schemas.crm import MeetingCreate, MeetingUpdate
from app.services.audit import log_audit
from app.services.notifications import create_notification


def _detail_options():
    return (
        selectinload(Meeting.contact),
        selectinload(Meeting.deal),
        selectinload(Meeting.account),
    )


async def list_meetings(
    db: AsyncSession,
    *,
    team_id: UUID,
    status_filter: str | None = None,
    type_filter: str | None = None,
) -> list[Meeting]:
    """Return meetings for a team."""
    query = select(Meeting).options(*_detail_options()).where(Meeting.team_id == team_id)
    
    if status_filter:
        query = query.where(Meeting.status == status_filter)
    if type_filter:
        query = query.where(Meeting.meeting_type == type_filter)
        
    query = query.order_by(Meeting.starts_at)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_upcoming_meetings(db: AsyncSession, *, team_id: UUID, limit: int = 5) -> list[Meeting]:
    """Return upcoming scheduled meetings."""
    now = datetime.now(timezone.utc)
    query = (
        select(Meeting)
        .options(*_detail_options())
        .where(
            Meeting.team_id == team_id,
            Meeting.status == "scheduled",
            Meeting.ends_at > now,
        )
        .order_by(Meeting.starts_at)
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_meeting_or_404(db: AsyncSession, meeting_id: UUID, *, team_id: UUID) -> Meeting:
    """Return a meeting or raise 404."""
    query = select(Meeting).options(*_detail_options()).where(Meeting.id == meeting_id, Meeting.team_id == team_id)
    result = await db.execute(query)
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found.")
    return meeting


async def create_meeting(
    db: AsyncSession,
    payload: MeetingCreate,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> Meeting:
    """Create a new meeting."""
    await _validate_meeting_payload(db, payload, team_id=team_id)
    
    meeting = Meeting(team_id=team_id, **payload.model_dump())
    db.add(meeting)
    await db.flush()
    
    await log_audit(
        db,
        action="meeting.created",
        entity_type="meeting",
        entity_id=str(meeting.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"title": meeting.title, "starts_at": meeting.starts_at.isoformat()},
    )

    # Notification for meeting today
    if meeting.starts_at.date() == datetime.now(timezone.utc).date():
        await create_notification(
            db,
            team_id=team_id,
            type="meeting.today",
            title="Meeting Today",
            message=f"You have a meeting scheduled for today: {meeting.title}",
            entity_type="meeting",
            entity_id=str(meeting.id),
        )

    await db.commit()
    
    return await get_meeting_or_404(db, meeting.id, team_id=team_id)


async def update_meeting(
    db: AsyncSession,
    meeting_id: UUID,
    payload: MeetingUpdate,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> Meeting:
    """Update an existing meeting."""
    meeting = await get_meeting_or_404(db, meeting_id, team_id=team_id)
    data = payload.model_dump(exclude_unset=True)
    
    merged = {
        "title": meeting.title,
        "description": meeting.description,
        "starts_at": meeting.starts_at,
        "ends_at": meeting.ends_at,
        "timezone": meeting.timezone,
        "location": meeting.location,
        "meeting_type": meeting.meeting_type,
        "reminder_minutes": meeting.reminder_minutes,
        "contact_id": meeting.contact_id,
        "deal_id": meeting.deal_id,
        "account_id": meeting.account_id,
    }
    merged.update(data)
    
    await _validate_meeting_payload(db, MeetingCreate(**merged), team_id=team_id)
    
    for field, value in data.items():
        setattr(meeting, field, value)
        
    await log_audit(
        db,
        action="meeting.updated",
        entity_type="meeting",
        entity_id=str(meeting.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"updated_fields": sorted(data.keys())},
    )
    await db.commit()
    return await get_meeting_or_404(db, meeting.id, team_id=team_id)


async def mark_completed(
    db: AsyncSession,
    meeting_id: UUID,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> Meeting:
    """Mark a meeting as completed."""
    meeting = await get_meeting_or_404(db, meeting_id, team_id=team_id)
    if meeting.status != "scheduled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only scheduled meetings can be completed.")
        
    meeting.status = "completed"
    
    await log_audit(
        db,
        action="meeting.completed",
        entity_type="meeting",
        entity_id=str(meeting.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={},
    )
    await db.commit()
    
    from app.services.automations import run_trigger
    await run_trigger(db, "meeting.completed", {"id": str(meeting.id), "meeting_type": meeting.meeting_type, "status": meeting.status, "contact_id": str(meeting.contact_id) if meeting.contact_id else None, "deal_id": str(meeting.deal_id) if meeting.deal_id else None, "account_id": str(meeting.account_id) if meeting.account_id else None}, team_id)
    
    return meeting


async def cancel_meeting(
    db: AsyncSession,
    meeting_id: UUID,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> Meeting:
    """Cancel a scheduled meeting."""
    meeting = await get_meeting_or_404(db, meeting_id, team_id=team_id)
    if meeting.status != "scheduled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only scheduled meetings can be cancelled.")
        
    meeting.status = "cancelled"
    
    await log_audit(
        db,
        action="meeting.cancelled",
        entity_type="meeting",
        entity_id=str(meeting.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={},
    )
    await db.commit()
    return meeting


async def delete_meeting(
    db: AsyncSession,
    meeting_id: UUID,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> None:
    """Delete a meeting."""
    meeting = await get_meeting_or_404(db, meeting_id, team_id=team_id)
    
    await log_audit(
        db,
        action="meeting.deleted",
        entity_type="meeting",
        entity_id=str(meeting.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"title": meeting.title},
    )
    await db.delete(meeting)
    await db.commit()


async def generate_ics(
    db: AsyncSession,
    meeting_id: UUID,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> str:
    """Generate an ICS file content for a meeting."""
    meeting = await get_meeting_or_404(db, meeting_id, team_id=team_id)
    
    cal = Calendar()
    cal.add('prodid', '-//Acufy CRM//Calendar Hub//EN')
    cal.add('version', '2.0')
    
    event = Event()
    event.add('summary', meeting.title)
    event.add('dtstart', meeting.starts_at)
    event.add('dtend', meeting.ends_at)
    event.add('dtstamp', datetime.now(timezone.utc))
    
    if meeting.description:
        event.add('description', meeting.description)
    if meeting.location:
        event.add('location', meeting.location)
        
    cal.add_component(event)
    
    await log_audit(
        db,
        action="meeting.exported",
        entity_type="meeting",
        entity_id=str(meeting.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={},
    )
    await db.commit()
    
    return cal.to_ical().decode('utf-8')


async def _validate_meeting_payload(db: AsyncSession, payload: MeetingCreate, *, team_id: UUID) -> None:
    """Validate meeting payload data."""
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ends_at must be strictly after starts_at.",
        )
        
    if payload.contact_id is not None:
        contact = await db.get(Contact, payload.contact_id)
        if contact is None or contact.team_id != team_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found.")
            
    if payload.deal_id is not None:
        deal = await db.get(Deal, payload.deal_id)
        if deal is None or deal.team_id != team_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found.")
            
    if payload.account_id is not None:
        account = await db.get(Account, payload.account_id)
        if account is None or account.team_id != team_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
