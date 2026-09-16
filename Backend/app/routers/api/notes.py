"""Notes API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthContext, get_auth_context
from app.core.db import get_db
from app.schemas.crm import NoteCreate, NoteOut, NoteUpdate
from app.services.notes import (
    create_note,
    delete_note,
    list_notes,
    update_note,
)


router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("", response_model=list[NoteOut])
async def get_notes(
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[NoteOut]:
    """Return notes for the authenticated team."""
    return await list_notes(
        db,
        team_id=auth.team_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )


@router.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
async def post_note(
    payload: NoteCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> NoteOut:
    """Create a new note."""
    return await create_note(db, payload, team_id=auth.team_id, actor_id=auth.user_id)


@router.patch("/{note_id}", response_model=NoteOut)
async def patch_note(
    note_id: UUID,
    payload: NoteUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> NoteOut:
    """Update a note."""
    return await update_note(
        db,
        note_id,
        payload,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note_route(
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> None:
    """Delete a note."""
    await delete_note(db, note_id, team_id=auth.team_id, actor_id=auth.user_id)
