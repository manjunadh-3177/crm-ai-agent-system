"""Forecasting and pipeline analytics agent."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import chat, start_trace_scope
from app.schemas.ai import ForecastInsightEnvelope, ForecastInsightResponse
from app.services.ai_summary import parse_json_response
from app.services.analytics import compute_team_pipeline_metrics, list_recent_team_activity
from app.services.audit import log_audit


def _build_fallback_insights(metrics: ForecastInsightEnvelope) -> ForecastInsightResponse:
    stalled_count = len(metrics.metrics.stalled_deals)
    top_stage = metrics.metrics.deals_by_stage[0].stage if metrics.metrics.deals_by_stage else "no active stages"
    risks: list[str] = []
    opportunities: list[str] = []
    recommendations: list[str] = []

    if stalled_count:
        risks.append(f"{stalled_count} deals appear stalled with no recent movement.")
        recommendations.append("Review stalled deals first and decide whether to revive, re-stage, or close them.")

    if metrics.metrics.close_this_month_estimate > 0:
        opportunities.append(
            f"Current weighted deals expected to close this month total about {metrics.metrics.close_this_month_estimate:,.0f}."
        )
        recommendations.append("Focus manager coaching on the highest-value deals expected to close this month.")

    if metrics.metrics.won_this_month.count > metrics.metrics.lost_this_month.count:
        opportunities.append("Won deals are currently outpacing losses this month.")

    if not risks:
        risks.append("No material risk spikes were detected from current pipeline math.")
    if not opportunities:
        opportunities.append("Pipeline coverage is present, but more late-stage momentum would improve confidence.")
    if not recommendations:
        recommendations.append("Rebalance rep attention toward proposal and negotiation-stage deals.")

    return ForecastInsightResponse(
        summary=(
            f"The team currently has {sum(stage.count for stage in metrics.metrics.deals_by_stage)} tracked deals "
            f"with {metrics.metrics.total_pipeline_value:,.0f} in open pipeline and {top_stage} as the most visible stage."
        ),
        risks=risks,
        opportunities=opportunities,
        recommended_actions=recommendations,
    )


async def generate_forecast(
    db: AsyncSession,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> ForecastInsightEnvelope:
    """Generate manager forecasting insights from real team-scoped CRM data."""
    trace_scope = start_trace_scope(
        "forecast_agent",
        metadata={"team_id": str(team_id), "user_id": actor_id},
        input_payload={"team_id": str(team_id)},
    )
    metrics = await compute_team_pipeline_metrics(db, team_id=team_id)
    recent_activity = await list_recent_team_activity(db, team_id=team_id)

    envelope = ForecastInsightEnvelope(
        metrics=metrics,
        summary="",
        risks=[],
        opportunities=[],
        recommended_actions=[],
    )

    prompt = (
        "You are a sales forecasting assistant for a CRM manager.\n"
        "Use the provided deterministic metrics only.\n"
        "Do not invent numbers.\n"
        "Provide a concise manager-facing JSON response with keys:\n"
        "summary, risks, opportunities, recommended_actions.\n"
        "Each list should contain 1 to 4 concise strings.\n\n"
        f"Metrics:\n{json.dumps(metrics.model_dump(mode='json'), indent=2)}\n\n"
        f"Recent activity:\n{json.dumps(recent_activity, indent=2)}"
    )

    try:
        raw = await chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional sales analyst. "
                        "CRITICAL: You must respond ONLY with a valid JSON object. "
                        "Do not include conversational text or markdown. "
                        "Required JSON structure: "
                        '{"summary": "string", "risks": ["string"], "opportunities": ["string"], "recommended_actions": ["string"]}'
                    ),
                },
                {"role": "user", "content": f"{prompt}\n\nRemember: Return ONLY the JSON object."},
            ],
            purpose="forecast",
            temperature=0.1,
            metadata={"route": "/ai/forecast", "team_id": str(team_id), "user_id": actor_id},
        )
        insights = parse_json_response(raw, ForecastInsightResponse)
    except Exception:
        insights = _build_fallback_insights(envelope)

    result = ForecastInsightEnvelope(
        metrics=metrics,
        summary=insights.summary,
        risks=insights.risks,
        opportunities=insights.opportunities,
        recommended_actions=insights.recommended_actions,
    )

    await log_audit(
        db,
        action="agent.forecast.generated",
        entity_type="team",
        entity_id=str(team_id),
        actor_type="ai",
        actor_id=actor_id,
        team_id=team_id,
        metadata={
            "total_pipeline_value": metrics.total_pipeline_value,
            "weighted_pipeline_value": metrics.weighted_pipeline_value,
            "stalled_deals": len(metrics.stalled_deals),
            "won_this_month": metrics.won_this_month.count,
            "lost_this_month": metrics.lost_this_month.count,
        },
    )
    await db.commit()
    trace_scope.finish(output=result.model_dump(mode="json"), status_message="success")
    return result
