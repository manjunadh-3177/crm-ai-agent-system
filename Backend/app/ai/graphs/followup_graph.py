"""LangGraph workflow for follow-up outreach orchestration."""

from __future__ import annotations

import time
from typing import Any, Literal
from uuid import UUID

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.llm import start_trace_scope
from app.ai.agents.compliance_agent import run_compliance_agent
from app.models import Deal
from app.events import emit_event
from app.schemas.ai import DraftEmailResponse
from app.services.agent_runs import create_agent_run
from app.services.ai_email import generate_email_draft_content, persist_draft_and_approval
from app.services.audit import log_audit


GRAPH_NAME = "followup_graph"


class FollowUpGraphState(BaseModel):
    team_id: str | None = None
    user_id: str | None = None
    event_name: str
    event_payload: dict[str, Any]
    deal_id: str | None = None
    contact_id: str | None = None
    stage_name: str | None = None
    decision: str | None = None
    draft_created: bool = False
    approval_id: str | None = None
    status: str = "running"
    result: str = "started"
    logs: list[str] = Field(default_factory=list)
    outreach_type: str | None = None
    draft_subject: str | None = None
    draft_body: str | None = None


async def run_followup_graph(
    db: AsyncSession,
    *,
    event_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Run the follow-up graph and persist a lightweight run record."""
    started_at = time.perf_counter()
    deal_id_value = payload.get("deal_id")
    trace_scope = start_trace_scope(
        GRAPH_NAME,
        metadata={
            "team_id": str(payload.get("team_id")) if payload.get("team_id") else None,
            "user_id": str(payload.get("user_id")) if payload.get("user_id") else None,
            "deal_id": str(deal_id_value) if deal_id_value else None,
            "contact_id": str(payload.get("contact_id")) if payload.get("contact_id") else None,
            "event_name": event_name,
        },
        input_payload={"event_name": event_name, "payload": payload},
    )
    initial_state = FollowUpGraphState(
        event_name=event_name,
        event_payload=payload,
        deal_id=str(deal_id_value) if deal_id_value else None,
        team_id=str(payload.get("team_id")) if payload.get("team_id") else None,
        logs=[f"event_received:{event_name}"],
    )

    await log_audit(
        db,
        action="graph.followup.started",
        entity_type="deal",
        entity_id=initial_state.deal_id,
        actor_type="system",
        team_id=UUID(initial_state.team_id) if initial_state.team_id else None,
        metadata={
            "event_name": event_name,
            "deal_id": initial_state.deal_id,
        },
    )
    await db.commit()

    graph = _build_graph(db)

    try:
        final_state: FollowUpGraphState = await graph.ainvoke(initial_state)
        duration_ms = int((time.perf_counter() - started_at) * 1000)

        run = await create_agent_run(
            db,
            team_id=UUID(final_state.team_id) if final_state.team_id else UUID(str(payload["team_id"])),
            graph_name=GRAPH_NAME,
            event_name=event_name,
            deal_id=UUID(final_state.deal_id) if final_state.deal_id else None,
            status_value=final_state.status,
            result=final_state.result,
            duration_ms=duration_ms,
        )

        completion_action = (
            "graph.followup.no_action"
            if final_state.result == "no_action_needed"
            else "graph.followup.completed"
        )
        await log_audit(
            db,
            action=completion_action,
            entity_type="agent_run",
            entity_id=str(run.id),
            actor_type="system",
            team_id=UUID(final_state.team_id) if final_state.team_id else None,
            metadata={
                "event_name": event_name,
                "deal_id": final_state.deal_id,
                "contact_id": final_state.contact_id,
                "stage_name": final_state.stage_name,
                "status": final_state.status,
                "result": final_state.result,
                "approval_id": final_state.approval_id,
                "logs": final_state.logs,
            },
        )
        await db.commit()
        run_payload = {
            "run_id": str(run.id),
            "team_id": final_state.team_id or str(payload.get("team_id")),
            "graph_name": GRAPH_NAME,
            "event_name": event_name,
            "deal_id": final_state.deal_id,
            "status": final_state.status,
            "result": final_state.result,
            "duration_ms": duration_ms,
        }
        await emit_event("agent_run.created", run_payload)
        await emit_event("agent_run.completed", run_payload)
        response_payload = {
            "run_id": str(run.id),
            "graph_name": GRAPH_NAME,
            "status": final_state.status,
            "result": final_state.result,
            "approval_id": final_state.approval_id,
            "duration_ms": duration_ms,
            "logs": final_state.logs,
        }
        trace_scope.finish(
            output=response_payload,
            metadata={
                "run_id": str(run.id),
                "approval_id": final_state.approval_id,
                "contact_id": final_state.contact_id,
            },
            status_message="success",
        )
        return response_payload
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        run = await create_agent_run(
            db,
            team_id=UUID(str(payload["team_id"])),
            graph_name=GRAPH_NAME,
            event_name=event_name,
            deal_id=UUID(initial_state.deal_id) if initial_state.deal_id else None,
            status_value="failed",
            result="graph_crashed",
            duration_ms=duration_ms,
        )
        await log_audit(
            db,
            action="graph.followup.failed",
            entity_type="agent_run",
            entity_id=str(run.id),
            actor_type="system",
            team_id=UUID(str(payload["team_id"])) if payload.get("team_id") else None,
            metadata={
                "event_name": event_name,
                "deal_id": initial_state.deal_id,
                "error": str(exc),
            },
        )
        await db.commit()
        run_payload = {
            "run_id": str(run.id),
            "team_id": str(payload.get("team_id")),
            "graph_name": GRAPH_NAME,
            "event_name": event_name,
            "deal_id": initial_state.deal_id,
            "status": "failed",
            "result": "graph_crashed",
            "duration_ms": duration_ms,
        }
        await emit_event("agent_run.created", run_payload)
        await emit_event("agent_run.completed", run_payload)
        response_payload = {
            "run_id": str(run.id),
            "graph_name": GRAPH_NAME,
            "status": "failed",
            "result": "graph_crashed",
            "approval_id": None,
            "duration_ms": duration_ms,
            "logs": [*initial_state.logs, f"graph_crashed:{exc}"],
        }
        trace_scope.finish(
            output=response_payload,
            metadata={"run_id": str(run.id)},
            status_message="failure",
        )
        return response_payload


def _build_graph(db: AsyncSession):
    graph = StateGraph(FollowUpGraphState)
    graph.add_node("load_context", lambda state: _load_context(db, state))
    graph.add_node("decide_action", _decide_action)
    graph.add_node("draft_email", lambda state: _draft_email(db, state))
    graph.add_node("compliance_gate", lambda state: _compliance_gate(db, state))
    graph.add_node("create_approval", lambda state: _create_approval(db, state))
    graph.add_node("no_action", _no_action)
    graph.add_node("finish", _finish)

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "decide_action")
    graph.add_conditional_edges(
        "decide_action",
        _route_after_decide,
        {
            "draft_email": "draft_email",
            "no_action": "no_action",
        },
    )
    graph.add_edge("draft_email", "compliance_gate")
    graph.add_conditional_edges(
        "compliance_gate",
        _route_after_compliance,
        {
            "create_approval": "create_approval",
            "no_action": "no_action",
        },
    )
    graph.add_edge("create_approval", "finish")
    graph.add_edge("no_action", "finish")
    graph.add_edge("finish", END)
    return graph.compile()


async def _load_context(db: AsyncSession, state: FollowUpGraphState) -> FollowUpGraphState:
    if state.deal_id is None:
        return state.model_copy(
            update={
                "decision": "no_action",
                "status": "completed",
                "result": "no_action_needed",
                "logs": [*state.logs, "load_context:missing_deal_id"],
            }
        )

    filters = [Deal.id == UUID(state.deal_id)]
    if state.team_id:
        filters.append(Deal.team_id == UUID(state.team_id))

    result = await db.execute(
        select(Deal)
        .options(
            selectinload(Deal.stage),
            selectinload(Deal.contact),
            selectinload(Deal.account),
            selectinload(Deal.owner),
        )
        .where(*filters)
    )
    deal = result.scalar_one_or_none()
    if deal is None:
        return state.model_copy(
            update={
                "decision": "no_action",
                "status": "completed",
                "result": "no_action_needed",
                "logs": [*state.logs, "load_context:deal_not_found"],
            }
        )

    return state.model_copy(
        update={
            "team_id": str(deal.team_id),
            "user_id": str(deal.owner_user_id) if deal.owner_user_id else None,
            "contact_id": str(deal.contact_id) if deal.contact_id else None,
            "stage_name": deal.stage.name if deal.stage else None,
            "logs": [
                *state.logs,
                f"load_context:deal={deal.id}",
                f"load_context:stage={deal.stage.name if deal.stage else 'unknown'}",
            ],
        }
    )


def _decide_action(state: FollowUpGraphState) -> FollowUpGraphState:
    stage_name = (state.stage_name or "").strip().lower()

    if state.contact_id is None:
        return state.model_copy(
            update={
                "decision": "no_action",
                "result": "no_action_needed",
                "logs": [*state.logs, "decide_action:no_linked_contact"],
            }
        )

    if stage_name in {"won", "lost"}:
        return state.model_copy(
            update={
                "decision": "no_action",
                "result": "no_action_needed",
                "logs": [*state.logs, f"decide_action:{stage_name}_no_action"],
            }
        )

    if state.event_name == "deal.created" and stage_name == "lead":
        return state.model_copy(
            update={
                "decision": "intro_outreach",
                "outreach_type": "intro_follow_up",
                "logs": [*state.logs, "decide_action:intro_outreach"],
            }
        )

    if state.event_name == "deal.stage_changed" and stage_name == "proposal":
        return state.model_copy(
            update={
                "decision": "proposal_follow_up",
                "outreach_type": "proposal_follow_up",
                "logs": [*state.logs, "decide_action:proposal_follow_up"],
            }
        )

    if state.event_name == "deal.stage_changed" and stage_name == "negotiation":
        return state.model_copy(
            update={
                "decision": "urgency_follow_up",
                "outreach_type": "urgency_follow_up",
                "logs": [*state.logs, "decide_action:urgency_follow_up"],
            }
        )

    return state.model_copy(
        update={
            "decision": "no_action",
            "result": "no_action_needed",
            "logs": [*state.logs, "decide_action:stage_not_actionable"],
        }
    )


def _route_after_decide(state: FollowUpGraphState) -> Literal["draft_email", "no_action"]:
    if state.decision in {"intro_outreach", "proposal_follow_up", "urgency_follow_up"}:
        return "draft_email"
    return "no_action"


async def _draft_email(db: AsyncSession, state: FollowUpGraphState) -> FollowUpGraphState:
    if state.contact_id is None or state.deal_id is None:
        return state.model_copy(
            update={
                "decision": "no_action",
                "result": "no_action_needed",
                "logs": [*state.logs, "draft_email:missing_contact_or_deal"],
            }
        )

    draft_response = await generate_email_draft_content(
        db,
        contact_id=UUID(state.contact_id),
        team_id=UUID(state.team_id),
        deal_id=UUID(state.deal_id),
        metadata={
            "route": "followup_graph",
            "team_id": state.team_id,
            "user_id": state.user_id,
            "deal_id": state.deal_id,
            "contact_id": state.contact_id,
            "event_name": state.event_name,
            "outreach_type": state.outreach_type,
        },
    )

    return state.model_copy(
        update={
            "draft_subject": draft_response.subject,
            "draft_body": draft_response.body,
            "logs": [*state.logs, "draft_email:generated"],
        }
    )


async def _compliance_gate(db: AsyncSession, state: FollowUpGraphState) -> FollowUpGraphState:
    if state.contact_id is None:
        return state.model_copy(
            update={
                "decision": "no_action",
                "result": "no_action_needed",
                "logs": [*state.logs, "compliance_gate:no_linked_contact"],
            }
        )

    result = await db.execute(
        select(Deal)
        .options(selectinload(Deal.contact))
        .where(Deal.id == UUID(state.deal_id), Deal.team_id == UUID(state.team_id))
    )
    deal = result.scalar_one_or_none()
    contact = deal.contact if deal else None

    if contact is None:
        return state.model_copy(
            update={
                "decision": "no_action",
                "result": "no_action_needed",
                "logs": [*state.logs, "compliance_gate:contact_not_found"],
            }
        )

    draft = DraftEmailResponse(
        subject=state.draft_subject or "",
        body=state.draft_body or "",
        tone="professional",
    )
    passed, reason = run_compliance_agent(contact=contact, draft=draft)
    if not passed:
        return state.model_copy(
            update={
                "decision": "no_action",
                "result": "blocked_pre_approval",
                "logs": [*state.logs, f"compliance_gate:{reason}"],
            }
        )

    return state.model_copy(update={"logs": [*state.logs, "compliance_gate:passed"]})


def _route_after_compliance(state: FollowUpGraphState) -> Literal["create_approval", "no_action"]:
    if state.result == "blocked_pre_approval":
        return "no_action"
    return "create_approval"


async def _create_approval(db: AsyncSession, state: FollowUpGraphState) -> FollowUpGraphState:
    if state.contact_id is None or state.deal_id is None or state.team_id is None:
        return state.model_copy(
            update={
                "decision": "no_action",
                "result": "no_action_needed",
                "logs": [*state.logs, "create_approval:missing_required_ids"],
            }
        )

    response = DraftEmailResponse(
        subject=state.draft_subject or "",
        body=state.draft_body or "",
        tone="professional",
    )
    _, approval = await persist_draft_and_approval(
        db,
        contact_id=UUID(state.contact_id),
        team_id=UUID(state.team_id),
        deal_id=UUID(state.deal_id),
        response=response,
    )
    await db.commit()
    await emit_event(
        "approval.created",
        {
            "approval_id": str(approval.id),
            "team_id": state.team_id,
            "contact_id": state.contact_id,
            "deal_id": state.deal_id,
            "subject": response.subject,
            "type": approval.type,
            "status": approval.status,
        },
    )

    return state.model_copy(
        update={
            "draft_created": True,
            "approval_id": str(approval.id),
            "status": "completed",
            "result": "draft_created",
            "logs": [*state.logs, f"create_approval:{approval.id}"],
        }
    )


def _no_action(state: FollowUpGraphState) -> FollowUpGraphState:
    return state.model_copy(
        update={
            "status": "completed",
            "result": state.result or "no_action_needed",
            "logs": [*state.logs, "no_action:complete"],
        }
    )


def _finish(state: FollowUpGraphState) -> FollowUpGraphState:
    if state.draft_created:
        return state.model_copy(update={"status": "completed", "result": "draft_created"})
    return state.model_copy(update={"status": "completed"})
