"""Notes service layer."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.events import emit_event
from app.models import Note
from app.schemas.crm import NoteCreate, NoteUpdate
from app.services.audit import log_audit


async def list_notes(
    db: AsyncSession,
    *,
    team_id: UUID,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
) -> list[Note]:
    """Return notes for a team, optionally filtered by entity."""
    query = select(Note).where(Note.team_id == team_id)
    
    if entity_type:
        query = query.where(Note.entity_type == entity_type)
    if entity_id:
        query = query.where(Note.entity_id == entity_id)
        
    query = query.order_by(Note.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_note_or_404(db: AsyncSession, note_id: UUID, *, team_id: UUID) -> Note:
    """Return a note or raise 404."""
    query = select(Note).where(Note.id == note_id, Note.team_id == team_id)
    result = await db.execute(query)
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found.")
    return note


async def create_note(
    db: AsyncSession,
    payload: NoteCreate,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> Note:
    """Create a new note."""
    note = Note(team_id=team_id, created_by_user_id=actor_id, **payload.model_dump())
    db.add(note)
    await db.flush()
    
    await log_audit(
        db,
        action="note.created",
        entity_type="note",
        entity_id=str(note.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={
            "related_entity_type": payload.entity_type,
            "related_entity_id": str(payload.entity_id),
        },
    )
    await db.commit()
    
    await emit_event("note.created", {"id": str(note.id), "team_id": str(team_id)})
    return note


async def update_note(
    db: AsyncSession,
    note_id: UUID,
    payload: NoteUpdate,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> Note:
    """Update an existing note."""
    note = await get_note_or_404(db, note_id, team_id=team_id)
    data = payload.model_dump(exclude_unset=True)
    
    for field, value in data.items():
        setattr(note, field, value)
        
    await log_audit(
        db,
        action="note.updated",
        entity_type="note",
        entity_id=str(note.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"updated_fields": list(data.keys())},
    )
    await db.commit()
    
    await emit_event("note.updated", {"id": str(note.id), "team_id": str(team_id)})
    return note


async def delete_note(
    db: AsyncSession,
    note_id: UUID,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> None:
    """Delete a note."""
    note = await get_note_or_404(db, note_id, team_id=team_id)
    
    await log_audit(
        db,
        action="note.deleted",
        entity_type="note",
        entity_id=str(note.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={},
    )
    await db.delete(note)
    await db.commit()
    
    await emit_event("note.deleted", {"id": str(note_id), "team_id": str(team_id)})
