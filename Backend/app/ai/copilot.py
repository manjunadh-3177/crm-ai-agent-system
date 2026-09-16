from __future__ import annotations
import json
from uuid import UUID
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.ai.llm import chat
from app.services.analytics import compute_team_pipeline_metrics
from app.services.ai_approvals import list_pending_approvals
from app.services.audit import log_audit
from app.schemas.ai import ForecastInsightEnvelope


def _infer_intent_from_message(message: str) -> str:
    text = (message or "").strip().lower()
    if not text:
        return "help"
    if any(phrase in text for phrase in ["stalled", "stuck", "inactive deals", "inactive deal"]):
        return "list_stalled_deals"
    if any(phrase in text for phrase in ["pipeline", "pipeline summary", "pipeline value", "weighted pipeline"]):
        return "pipeline_summary"
    if any(phrase in text for phrase in ["approval", "approvals", "pending approval", "pending approvals"]):
        return "show_approvals_pending"
    if any(phrase in text for phrase in ["top deals", "top open deals", "largest deals", "biggest deals"]):
        return "top_open_deals"
    if any(phrase in text for phrase in ["follow up", "follow-up", "draft email", "draft followup", "draft follow-up"]):
        return "draft_followup"
    if any(phrase in text for phrase in ["create contact", "add contact", "new contact"]):
        return "create_contact"
    return "help"


async def route_copilot_intent(
    db: AsyncSession,
    *,
    team_id: UUID,
    user_id: str,
    message: str,
    history: list[dict[str, str]] | None = None
) -> dict[str, Any]:
    intent = _infer_intent_from_message(message)
    prompt = f"""
    You are a CRM Copilot. Route the user message to one of these intents:
    - list_stalled_deals
    - pipeline_summary
    - draft_followup (requires a contact name or ID)
    - create_contact
    - show_approvals_pending
    - top_open_deals
    - help
    
    Respond only with JSON: {{"intent": "name", "extracted_entities": {{}}}}
    User: {message}
    """

    try:
        raw_response = await chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            purpose="copilot.intent_router",
            metadata={"team_id": str(team_id), "user_id": user_id},
        )
        start = raw_response.find("{")
        end = raw_response.rfind("}") + 1
        parsing = json.loads(raw_response[start:end])
        intent = parsing.get("intent", intent) or intent
    except Exception:
        # Fall back to lightweight local intent routing so Copilot stays usable
        # even when the LLM gateway is unavailable.
        pass

    data = {}
    answer = ""
    suggestions = ["Show pipeline summary", "Any stalled deals?", "View pending approvals"]

    if intent == "pipeline_summary":
        metrics = await compute_team_pipeline_metrics(db, team_id=team_id)
        answer = f"Your total pipeline is {metrics.total_pipeline_value:,.0f} with a weighted value of {metrics.weighted_pipeline_value:,.0f}."
        data = {"metrics": metrics.model_dump(mode='json')}
    
    elif intent == "list_stalled_deals":
        metrics = await compute_team_pipeline_metrics(db, team_id=team_id)
        stalled = metrics.stalled_deals
        if not stalled:
            answer = "No stalled deals detected! Everything is moving."
        else:
            answer = f"Found {len(stalled)} stalled deals. {stalled[0].name} has been inactive for {stalled[0].stalled_days} days."
            data = {"stalled_deals": [d.model_dump(mode='json') for d in stalled]}
    
    elif intent == "show_approvals_pending":
        approvals = await list_pending_approvals(db, team_id=team_id)
        answer = f"You have {len(approvals)} approvals waiting for your review."
        data = {"approvals_count": len(approvals)}
        suggestions = ["Review approvals now", "Show top deals"]

    elif intent == "top_open_deals":
        metrics = await compute_team_pipeline_metrics(db, team_id=team_id)
        top = metrics.top_open_deals
        answer = f"Your top deal is {top[0].name} valued at {top[0].amount:,.0f}." if top else "No open deals found."
        data = {"top_deals": [d.model_dump(mode='json') for d in top]}

    else:
        answer = "I can help you manage your pipeline. Try asking about stalled deals, pipeline value, or pending approvals."
        intent = "help"

    await log_audit(
        db,
        action="copilot.query",
        entity_type="team",
        entity_id=str(team_id),
        actor_type="user",
        actor_id=user_id,
        team_id=team_id,
        metadata={"message": message, "intent": intent}
    )
    await db.commit()

    return {
        "intent": intent,
        "answer": answer,
        "data": data,
        "suggested_actions": suggestions
    }
