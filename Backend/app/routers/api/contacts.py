"""Contact routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthContext, get_auth_context
from app.core.db import get_db
from app.schemas.crm import BulkDeleteRequest, BulkOperationResponse, ContactCreate, ContactRead, ContactUpdate
from app.services.contacts import create_contact, delete_contact, list_contacts, update_contact
from app.services.import_export import bulk_delete_contacts


router = APIRouter(tags=["contacts"])


@router.get("/contacts", response_model=list[ContactRead])
async def get_contacts(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[ContactRead]:
    """Return all contacts."""
    return await list_contacts(db, team_id=auth.team_id)


@router.post("/contacts", response_model=ContactRead, status_code=status.HTTP_201_CREATED)
async def post_contact(
    payload: ContactCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> ContactRead:
    """Create a contact."""
    return await create_contact(db, payload, team_id=auth.team_id, actor_id=auth.user_id)


@router.patch("/contacts/{contact_id}", response_model=ContactRead)
async def patch_contact(
    contact_id: UUID,
    payload: ContactUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> ContactRead:
    """Update a contact."""
    return await update_contact(db, contact_id, payload, team_id=auth.team_id)


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_contact(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> Response:
    """Delete a contact."""
    await delete_contact(db, contact_id, team_id=auth.team_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/contacts/bulk-delete", response_model=BulkOperationResponse)
async def post_bulk_delete_contacts(
    payload: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> BulkOperationResponse:
    """Delete multiple contacts for the active team."""
    return await bulk_delete_contacts(
        db,
        payload,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )
