"""Lead Qualifier Agent for automatic contact scoring."""

import logging
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.contact import Contact
from app.models.task import Task
from app.services.audit import log_audit
from app.events import emit_event
from app.services.notifications import create_notification

logger = logging.getLogger(__name__)

def score_contact(contact: Contact) -> tuple[int, str, str]:
    """
    Score lead using simple deterministic rules:
    +30 if email exists
    +20 if phone exists
    +20 if linked company/account exists
    +15 if title exists
    +15 if notes/description exists
    """
    score = 0
    reasons = []

    if contact.email:
        score += 30
        reasons.append("Email provided (+30)")
    
    if contact.phone:
        score += 20
        reasons.append("Phone provided (+20)")

    if contact.account_id:
        score += 20
        reasons.append("Linked to Account (+20)")

    if contact.job_title:
        score += 15
        reasons.append("Job Title provided (+15)")

    if contact.description:
        score += 15
        reasons.append("Description provided (+15)")

    # Cap at 100
    score = min(100, score)

    # Tiering
    if score >= 80:
        tier = "Hot"
    elif score >= 50:
        tier = "Warm"
    else:
        tier = "Cold"

    reason_str = ", ".join(reasons) if reasons else "Insufficient data"
    return score, tier, reason_str

async def run_lead_qualifier(db: AsyncSession, contact_id: UUID, team_id: UUID) -> None:
    """Run the lead qualifier agent on a contact."""
    try:
        contact = await db.get(Contact, contact_id)
        if not contact or contact.team_id != team_id:
            return

        score, tier, reason = score_contact(contact)
        
        contact.lead_score = score
        contact.lead_tier = tier
        contact.lead_reason = reason
        
        await db.flush()

        # Audit log
        await log_audit(
            db,
            action="agent.lead_qualified",
            entity_type="contact",
            entity_id=str(contact_id),
            actor_type="ai",
            team_id=team_id,
            metadata={"score": score, "tier": tier, "reason": reason}
        )

        # If Hot lead, auto create task
        if tier == "Hot":
            new_task = Task(
                team_id=team_id,
                title=f"Follow up new hot lead: {contact.first_name} {contact.last_name}",
                description=f"Auto-generated for {tier} lead (Score: {score}).\nReason: {reason}",
                priority="high",
                status="open",
                contact_id=contact_id
            )
            db.add(new_task)
            await db.flush()
            
            await log_audit(
                db,
                action="task.created",
                entity_type="task",
                entity_id=str(new_task.id),
                actor_type="system",
                team_id=team_id,
                metadata={"reason": "hot_lead_automation"}
            )

            # Generate notification
            await create_notification(
                db,
                team_id=team_id,
                type="lead.hot",
                title="New Hot Lead Qualified",
                message=f"{contact.first_name} {contact.last_name} has been qualified as a Hot lead (Score: {score}).",
                entity_type="contact",
                entity_id=str(contact_id),
            )

        await db.commit()
        await emit_event("contact.updated", {"id": str(contact_id), "team_id": str(team_id)})

        # V2 automation trigger for hot leads
        if tier == "Hot":
            from app.services.automations import run_trigger
            await run_trigger(
                db,
                "lead.qualified_hot",
                {
                    "id": str(contact_id),
                    "contact_id": str(contact_id),
                    "lead_tier": tier,
                    "lead_score": score,
                    "team_id": str(team_id),
                },
                team_id,
            )

    except Exception as e:
        logger.error(f"Error in lead_qualifier_agent: {e}")
        await db.rollback()
