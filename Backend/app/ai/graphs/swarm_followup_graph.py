"""LangGraph multi-agent follow-up workflow."""

from __future__ import annotations

import time
from typing import Any, Literal
from uuid import UUID

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.agents.compliance_agent import run_compliance_agent
from app.ai.agents.draft_agent import run_draft_agent
from app.ai.agents.research_agent import run_research_agent
from app.ai.llm import start_trace_scope
from app.ai.memory import get_contact_memory
from app.events import emit_event
from app.models import Deal
from app.schemas.ai import ContactMemoryResponse, DraftEmailResponse
from app.services.agent_runs import create_agent_run
from app.services.ai_email import persist_draft_and_approval
from app.services.audit import log_audit


GRAPH_NAME = "swarm_followup"


class SwarmFollowUpState(BaseModel):
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
    research_insights: dict[str, Any] = Field(default_factory=dict)
    memory_summary: ContactMemoryResponse | None = None
    draft: DraftEmailResponse | None = None
    compliance_passed: bool = False
    compliance_reason: str | None = None


async def run_swarm_followup_graph(
    db: AsyncSession,
    *,
    event_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Run the swarm follow-up graph and persist the run record."""
    started_at = time.perf_counter()
    trace_scope = start_trace_scope(
        GRAPH_NAME,
        metadata={
            "team_id": str(payload.get("team_id")) if payload.get("team_id") else None,
            "user_id": str(payload.get("user_id")) if payload.get("user_id") else None,
            "deal_id": str(payload.get("deal_id")) if payload.get("deal_id") else None,
            "contact_id": str(payload.get("contact_id")) if payload.get("contact_id") else None,
            "event_name": event_name,
        },
        input_payload={"event_name": event_name, "payload": payload},
    )
    initial_state = SwarmFollowUpState(
        event_name=event_name,
        event_payload=payload,
        deal_id=str(payload.get("deal_id")) if payload.get("deal_id") else None,
        team_id=str(payload.get("team_id")) if payload.get("team_id") else None,
        logs=[f"event_received:{event_name}"],
    )

    graph = _build_graph(db)

    try:
        final_state: SwarmFollowUpState = await graph.ainvoke(initial_state)
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
        await log_audit(
            db,
            action="graph.swarm.completed",
            entity_type="agent_run",
            entity_id=str(run.id),
            actor_type="system",
            team_id=UUID(final_state.team_id) if final_state.team_id else None,
            metadata={
                "event_name": event_name,
                "graph_name": GRAPH_NAME,
                "deal_id": final_state.deal_id,
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
            action="graph.swarm.failed",
            entity_type="agent_run",
            entity_id=str(run.id),
            actor_type="system",
            team_id=UUID(str(payload["team_id"])) if payload.get("team_id") else None,
            metadata={
                "event_name": event_name,
                "graph_name": GRAPH_NAME,
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
    graph = StateGraph(SwarmFollowUpState)
    graph.add_node("load_context", lambda state: _load_context(db, state))
    graph.add_node("research_agent", lambda state: _research_node(db, state))
    graph.add_node("draft_agent", lambda state: _draft_node(db, state))
    graph.add_node("compliance_agent", lambda state: _compliance_node(db, state))
    graph.add_node("create_approval", lambda state: _create_approval(db, state))
    graph.add_node("finish", _finish)

    graph.set_entry_point("load_context")
    graph.add_conditional_edges(
        "load_context",
        _route_after_load,
        {
            "research_agent": "research_agent",
            "finish": "finish",
        },
    )
    graph.add_edge("research_agent", "draft_agent")
    graph.add_edge("draft_agent", "compliance_agent")
    graph.add_conditional_edges(
        "compliance_agent",
        _route_after_compliance,
        {
            "create_approval": "create_approval",
            "finish": "finish",
        },
    )
    graph.add_edge("create_approval", "finish")
    graph.add_edge("finish", END)
    return graph.compile()


async def _load_context(db: AsyncSession, state: SwarmFollowUpState) -> SwarmFollowUpState:
    deal = await _load_deal(db, state.deal_id, state.team_id)
    if deal is None:
        return state.model_copy(
            update={
                "status": "completed",
                "result": "no_action_needed",
                "logs": [*state.logs, "load_context:deal_missing_or_invalid"],
            }
        )

    stage_name = deal.stage.name if deal.stage else None
    stage_key = (stage_name or "").lower()
    should_act = (
        (state.event_name == "deal.created" and stage_key == "lead")
        or (state.event_name == "deal.stage_changed" and stage_key in {"proposal", "negotiation"})
    )

    if not deal.contact_id or stage_key in {"won", "lost"} or not should_act:
        return state.model_copy(
            update={
                "team_id": str(deal.team_id),
                "user_id": str(deal.owner_user_id) if deal.owner_user_id else None,
                "contact_id": str(deal.contact_id) if deal.contact_id else None,
                "stage_name": stage_name,
                "status": "completed",
                "result": "no_action_needed",
                "logs": [*state.logs, f"load_context:no_action:{stage_name or 'unknown'}"],
            }
        )

    return state.model_copy(
        update={
            "team_id": str(deal.team_id),
            "user_id": str(deal.owner_user_id) if deal.owner_user_id else None,
            "contact_id": str(deal.contact_id),
            "stage_name": stage_name,
            "logs": [*state.logs, f"load_context:ready:{deal.id}"],
        }
    )


def _route_after_load(state: SwarmFollowUpState) -> Literal["research_agent", "finish"]:
    if state.result == "no_action_needed":
        return "finish"
    return "research_agent"


async def _research_node(db: AsyncSession, state: SwarmFollowUpState) -> SwarmFollowUpState:
    deal = await _load_deal(db, state.deal_id, state.team_id)
    if deal is None:
        return state.model_copy(
            update={
                "status": "completed",
                "result": "no_action_needed",
                "logs": [*state.logs, "research_agent:deal_not_found"],
            }
        )

    memory_summary = await get_contact_memory(db, deal.contact_id, team_id=deal.team_id)
    insights = run_research_agent(
        deal=deal,
        event_name=state.event_name,
        memory_summary=memory_summary,
    )
    await log_audit(
        db,
        action="agent.research.completed",
        entity_type="deal",
        entity_id=str(deal.id),
        actor_type="ai",
        team_id=deal.team_id,
        metadata=insights,
    )
    await db.commit()

    return state.model_copy(
        update={
            "research_insights": insights,
            "memory_summary": memory_summary,
            "logs": [*state.logs, f"research_agent:{insights.get('recommended_angle')}"],
        }
    )


async def _draft_node(db: AsyncSession, state: SwarmFollowUpState) -> SwarmFollowUpState:
    if state.contact_id is None or state.deal_id is None:
        return state.model_copy(
            update={
                "status": "completed",
                "result": "no_action_needed",
                "logs": [*state.logs, "draft_agent:missing_contact_or_deal"],
            }
        )

    draft = await run_draft_agent(
        db,
        contact_id=UUID(state.contact_id),
        team_id=UUID(state.team_id),
        deal_id=UUID(state.deal_id),
        event_name=state.event_name,
        research_insights=state.research_insights,
        memory_summary=state.memory_summary,
    )
    await log_audit(
        db,
        action="agent.draft.completed",
        entity_type="deal",
        entity_id=state.deal_id,
        actor_type="ai",
        team_id=UUID(state.team_id) if state.team_id else None,
        metadata={
            "subject": draft.subject,
            "recommended_angle": state.research_insights.get("recommended_angle"),
        },
    )
    await db.commit()

    return state.model_copy(
        update={
            "draft": draft,
            "logs": [*state.logs, "draft_agent:generated"],
        }
    )


async def _compliance_node(db: AsyncSession, state: SwarmFollowUpState) -> SwarmFollowUpState:
    deal = await _load_deal(db, state.deal_id, state.team_id)
    contact = deal.contact if deal else None
    passed, reason = run_compliance_agent(contact=contact, draft=state.draft)

    await log_audit(
        db,
        action="agent.compliance.passed" if passed else "agent.compliance.blocked",
        entity_type="deal",
        entity_id=state.deal_id,
        actor_type="system",
        team_id=UUID(state.team_id) if state.team_id else None,
        metadata={"reason": reason},
    )
    await db.commit()

    return state.model_copy(
        update={
            "compliance_passed": passed,
            "compliance_reason": reason,
            "result": "blocked_pre_approval" if not passed else state.result,
            "logs": [
                *state.logs,
                "compliance_agent:passed" if passed else f"compliance_agent:blocked:{reason}",
            ],
        }
    )


def _route_after_compliance(state: SwarmFollowUpState) -> Literal["create_approval", "finish"]:
    if state.compliance_passed:
        return "create_approval"
    return "finish"


async def _create_approval(db: AsyncSession, state: SwarmFollowUpState) -> SwarmFollowUpState:
    if state.contact_id is None or state.deal_id is None or state.team_id is None or state.draft is None:
        return state.model_copy(
            update={
                "status": "completed",
                "result": "no_action_needed",
                "logs": [*state.logs, "create_approval:missing_context"],
            }
        )

    _, approval = await persist_draft_and_approval(
        db,
        contact_id=UUID(state.contact_id),
        team_id=UUID(state.team_id),
        deal_id=UUID(state.deal_id),
        response=state.draft,
    )
    await db.commit()
    await emit_event(
        "approval.created",
        {
            "approval_id": str(approval.id),
            "team_id": state.team_id,
            "contact_id": state.contact_id,
            "deal_id": state.deal_id,
            "subject": state.draft.subject,
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


def _finish(state: SwarmFollowUpState) -> SwarmFollowUpState:
    return state.model_copy(update={"status": "completed"})


async def _load_deal(db: AsyncSession, deal_id: str | None, team_id: str | None) -> Deal | None:
    if deal_id is None:
        return None

    filters = [Deal.id == UUID(deal_id)]
    if team_id:
        filters.append(Deal.team_id == UUID(team_id))

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
    return result.scalar_one_or_none()
