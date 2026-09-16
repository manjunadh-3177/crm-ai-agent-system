"""Contact service layer."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.events import emit_event
from app.jobs import enqueue_background_job
from app.models import Contact, Team
from app.schemas.crm import ContactCreate, ContactUpdate
from app.services.audit import log_audit


async def list_contacts(db: AsyncSession, *, team_id: UUID) -> list[Contact]:
    """Return all contacts."""
    result = await db.execute(
        select(Contact).where(Contact.team_id == team_id).order_by(Contact.created_at)
    )
    return list(result.scalars().all())


async def create_contact(
    db: AsyncSession,
    payload: ContactCreate,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> Contact:
    """Create a contact after validating its team."""
    team = await db.get(Team, team_id)
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found.",
        )

    contact = Contact(team_id=team_id, **payload.model_dump())
    db.add(contact)
    await db.flush()
    await log_audit(
        db,
        action="contact.created",
        entity_type="contact",
        entity_id=str(contact.id),
        actor_type="user",
        team_id=contact.team_id,
        actor_id=actor_id,
        metadata={"email": contact.email},
    )
    await db.commit()
    await db.refresh(contact)
    await emit_event(
        "contact.created",
        {
            "contact_id": str(contact.id),
            "team_id": str(contact.team_id),
            "email": contact.email,
        },
    )

    from app.ai.graphs.crm_orchestration import NEW_LEAD_GRAPH, run_new_lead_graph

    queue_result = await enqueue_background_job(
        "crm_graph_job",
        NEW_LEAD_GRAPH,
        str(contact.team_id),
        actor_id,
        contact_id=str(contact.id),
        trigger="contact.created",
    )
    if not queue_result.get("queued"):
        try:
            await run_new_lead_graph(
                db,
                contact_id=contact.id,
                team_id=contact.team_id,
                actor_id=actor_id,
                trigger="contact.created",
            )
        except Exception:
            # Keep contact creation resilient even if orchestration fails.
            pass

    # Automation triggers (V2)
    from app.services.automations import run_trigger
    await run_trigger(
        db,
        "contact.created",
        {
            "id": str(contact.id),
            "contact_id": str(contact.id),
            "team_id": str(team_id),
            "email": contact.email,
            "lead_tier": contact.lead_tier,
        },
        team_id,
    )

    await db.refresh(contact)
    return contact


async def update_contact(
    db: AsyncSession,
    contact_id: UUID,
    payload: ContactUpdate,
    *,
    team_id: UUID,
) -> Contact:
    """Patch an existing contact."""
    contact = await db.get(Contact, contact_id)
    if contact is None or contact.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found.",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)

    await db.commit()
    await db.refresh(contact)
    await emit_event(
        "contact.updated",
        {
            "contact_id": str(contact.id),
            "team_id": str(contact.team_id),
            "updated_fields": sorted(payload.model_dump(exclude_unset=True).keys()),
        },
    )
    return contact


async def delete_contact(db: AsyncSession, contact_id: UUID, *, team_id: UUID) -> None:
    """Delete a contact."""
    contact = await db.get(Contact, contact_id)
    if contact is None or contact.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found.",
        )

    payload = {
        "contact_id": str(contact.id),
        "team_id": str(contact.team_id),
        "email": contact.email,
    }
    await db.delete(contact)
    await db.commit()
    await emit_event("contact.deleted", payload)
