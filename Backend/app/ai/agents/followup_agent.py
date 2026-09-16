"""Single-purpose follow-up agent triggered by CRM deal events."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Deal
from app.services.audit import log_audit

SUPPORTED_EVENTS = {"deal.created", "deal.stage_changed"}


async def run_followup_agent(db: AsyncSession, *, event_name: str, payload: dict) -> dict:
    """Evaluate a deal event and create follow-up draft when useful."""
    if event_name not in SUPPORTED_EVENTS:
        return {"status": "ignored", "reason": "unsupported_event"}

    deal_id = payload.get("deal_id")
    if not deal_id:
        return {"status": "ignored", "reason": "missing_deal_id"}

    deal = await _load_deal_context(db, UUID(str(deal_id)))
    if deal is None:
        return {"status": "ignored", "reason": "deal_not_found"}

    await log_audit(
        db,
        action="agent.followup.triggered",
        entity_type="deal",
        entity_id=str(deal.id),
        actor_type="system",
        team_id=deal.team_id,
        metadata={
            "event_name": event_name,
            "stage": deal.stage.name if deal.stage else None,
            "contact_id": str(deal.contact_id) if deal.contact_id else None,
            "account_id": str(deal.account_id) if deal.account_id else None,
        },
    )
    await db.commit()

    settings = get_settings()
    if settings.use_swarm_graph:
        from app.ai.graphs.swarm_followup_graph import run_swarm_followup_graph

        result = await run_swarm_followup_graph(db, event_name=event_name, payload=payload)
    else:
        from app.ai.graphs.followup_graph import run_followup_graph

        result = await run_followup_graph(db, event_name=event_name, payload=payload)

    if result["status"] == "failed":
        return {
            "status": "failed",
            "reason": result["result"],
            "graph_name": result.get("graph_name"),
            "run_id": result.get("run_id"),
        }

    if result["result"] in {"no_action_needed", "blocked_pre_approval"}:
        await log_audit(
            db,
            action="agent.followup.no_action",
            entity_type="deal",
            entity_id=str(deal.id),
            actor_type="system",
            team_id=deal.team_id,
            metadata={
                "event_name": event_name,
                "reason": result["result"],
            },
        )
        await db.commit()
        return {
            "status": "no_action_needed",
            "reason": result["result"],
            "graph_name": result.get("graph_name"),
            "run_id": result.get("run_id"),
        }

    if result["result"] == "draft_created":
        await log_audit(
            db,
            action="agent.followup.draft_created",
            entity_type="deal",
            entity_id=str(deal.id),
            actor_type="system",
            team_id=deal.team_id,
            metadata={
                "event_name": event_name,
                "approval_id": result.get("approval_id"),
                "contact_id": str(deal.contact_id) if deal.contact_id else None,
                "graph_name": result.get("graph_name"),
            },
        )
        await db.commit()
        return {
            "status": "draft_created",
            "approval_id": result.get("approval_id"),
            "graph_name": result.get("graph_name"),
            "run_id": result.get("run_id"),
        }

    return {
        "status": result["result"],
        "graph_name": result.get("graph_name"),
        "run_id": result.get("run_id"),
    }


async def _load_deal_context(db: AsyncSession, deal_id: UUID) -> Deal | None:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    result = await db.execute(select(Deal).options(selectinload(Deal.stage)).where(Deal.id == deal_id))
    return result.scalar_one_or_none()
