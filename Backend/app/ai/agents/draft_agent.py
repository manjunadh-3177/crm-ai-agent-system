"""Draft agent for follow-up swarm email generation."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import start_operation_span
from app.schemas.ai import ContactMemoryResponse, DraftEmailResponse
from app.services.ai_email import generate_email_draft_content


async def run_draft_agent(
    db: AsyncSession,
    *,
    contact_id: UUID,
    team_id: UUID,
    deal_id: UUID,
    event_name: str,
    research_insights: dict[str, Any],
    memory_summary: ContactMemoryResponse | None = None,
) -> DraftEmailResponse:
    """Generate a follow-up draft using existing draft services plus research guidance."""
    span = start_operation_span(
        "draft_agent",
        metadata={
            "team_id": str(team_id),
            "contact_id": str(contact_id),
            "deal_id": str(deal_id),
            "event_name": event_name,
            "recommended_angle": research_insights.get("recommended_angle"),
        },
        input_payload={"research_insights": research_insights},
    )
    try:
        draft = await generate_email_draft_content(
            db,
            contact_id=contact_id,
            team_id=team_id,
            deal_id=deal_id,
            metadata={
                "route": "swarm_followup_graph",
                "event_name": event_name,
                "recommended_angle": research_insights.get("recommended_angle"),
                "purpose": "swarm_draft_agent",
                "team_id": str(team_id),
                "contact_id": str(contact_id),
                "deal_id": str(deal_id),
            },
            strategy_context={
                "urgency": research_insights.get("urgency"),
                "engagement_level": research_insights.get("engagement_level"),
                "recommended_angle": research_insights.get("recommended_angle"),
                "deal_amount_band": research_insights.get("deal_amount_band"),
                "relationship_status": (
                    memory_summary.relationship_status if memory_summary is not None else None
                ),
                "responsiveness": memory_summary.responsiveness if memory_summary is not None else None,
                "recommended_tone": (
                    memory_summary.recommended_tone if memory_summary is not None else None
                ),
                "common_topics": memory_summary.common_topics if memory_summary is not None else [],
            },
        )
        span.finish(output=draft.model_dump(mode="json"), status_message="success")
        return draft
    except Exception as exc:
        span.finish(output={"error": str(exc)}, status_message="failure")
        raise
