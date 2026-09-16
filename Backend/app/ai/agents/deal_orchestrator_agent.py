"""Deal Orchestrator Agent for automatic health monitoring."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.events import emit_event
from app.models.deal import Deal
from app.models.task import Task
from app.services.audit import log_audit
from app.services.notifications import create_notification

logger = logging.getLogger(__name__)

def analyze_deal_health(deal: Deal) -> tuple[str, str]:
    """
    Analyze deal health based on inactivity:
    0-6 days = healthy
    7-13 = at_risk
    14+ = stalled
    """
    now = datetime.now(UTC)
    # Handle naive vs aware datetime if needed, but updated_at should be aware
    updated_at = deal.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)

    delta = now - updated_at
    days_inactive = delta.days

    if days_inactive >= 14:
        return "stalled", f"No activity for {days_inactive} days. High risk of churn."
    elif days_inactive >= 7:
        return "at_risk", f"No activity for {days_inactive} days. Needs attention."
    else:
        return "healthy", f"Recent activity within {days_inactive} days."

async def run_deal_orchestrator(db: AsyncSession, deal_id: UUID, team_id: UUID) -> None:
    """Run the deal orchestrator agent on a deal."""
    try:
        deal = await db.get(Deal, deal_id)
        if not deal or deal.team_id != team_id:
            return

        health, reason = analyze_deal_health(deal)

        deal.deal_health = health
        deal.deal_reason = reason

        await db.flush()

        # Audit log
        await log_audit(
            db,
            action="agent.deal_orchestrated",
            entity_type="deal",
            entity_id=str(deal_id),
            actor_type="ai",
            team_id=team_id,
            metadata={"health": health, "reason": reason}
        )

        # If stalled, auto create task
        if health == "stalled":
            new_task = Task(
                team_id=team_id,
                title=f"Follow up stalled deal: {deal.name}",
                description=f"Auto-generated for stalled deal (Inactivity: {reason}).",
                priority="high",
                status="open",
                deal_id=deal_id,
                contact_id=deal.contact_id,
                account_id=deal.account_id
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
                metadata={"reason": "stalled_deal_automation"}
            )

            # Generate notification
            await create_notification(
                db,
                team_id=team_id,
                type="deal.stalled",
                title="Stalled Deal Detected",
                message=f"Deal '{deal.name}' has been inactive for {analyze_deal_health(deal)[1]}. Action required.",
                entity_type="deal",
                entity_id=str(deal_id),
            )

        await db.commit()
        await emit_event("deal.updated", {"id": str(deal_id), "team_id": str(team_id)})

    except Exception as e:
        logger.error(f"Error in deal_orchestrator_agent: {e}")
        await db.rollback()
