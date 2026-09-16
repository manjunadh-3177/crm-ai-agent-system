"""ProposalAgent for tenant-scoped proposal draft generation."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.events import emit_event
from app.models import Document
from app.schemas.crm import ProposalDraftResponse
from app.services.audit import log_audit
from app.services.proposals import generate_deal_proposal


logger = logging.getLogger(__name__)


async def run_proposal_agent(
    db: AsyncSession,
    *,
    deal_id: UUID,
    team_id: UUID,
    actor_id: str | None = None,
    trigger: str = "manual",
    force: bool = True,
) -> ProposalDraftResponse | None:
    """Generate a proposal draft document for a deal without sending externally."""
    try:
        if not force:
            existing = await db.scalar(
                select(Document)
                .where(
                    Document.team_id == team_id,
                    Document.deal_id == deal_id,
                    Document.document_type == "proposal",
                    Document.status == "draft",
                )
                .order_by(Document.created_at.desc())
                .limit(1)
            )
            if existing is not None:
                await log_audit(
                    db,
                    action="agent.proposal.skipped",
                    entity_type="deal",
                    entity_id=str(deal_id),
                    actor_type="ai",
                    team_id=team_id,
                    actor_id=actor_id,
                    metadata={"trigger": trigger, "reason": "draft_already_exists", "document_id": str(existing.id)},
                )
                await db.commit()
                await emit_event(
                    "agent.proposal.skipped",
                    {"deal_id": str(deal_id), "team_id": str(team_id), "document_id": str(existing.id)},
                )
                return None

        draft = await generate_deal_proposal(db, deal_id=deal_id, team_id=team_id, actor_id=actor_id)
        await log_audit(
            db,
            action="agent.proposal.generated",
            entity_type="document",
            entity_id=str(draft.document.id),
            actor_type="ai",
            team_id=team_id,
            actor_id=actor_id,
            metadata={
                "deal_id": str(deal_id),
                "document_id": str(draft.document.id),
                "trigger": trigger,
                "title": draft.title,
            },
        )
        await db.commit()
        await emit_event(
            "agent.proposal.generated",
            {
                "deal_id": str(deal_id),
                "team_id": str(team_id),
                "document_id": str(draft.document.id),
                "trigger": trigger,
            },
        )
        return draft
    except Exception:
        logger.exception("ProposalAgent failed for deal %s", deal_id)
        await db.rollback()
        await log_audit(
            db,
            action="agent.proposal.failed",
            entity_type="deal",
            entity_id=str(deal_id),
            actor_type="ai",
            team_id=team_id,
            actor_id=actor_id,
            metadata={"trigger": trigger},
        )
        await db.commit()
        return None
