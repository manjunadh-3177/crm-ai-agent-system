"""Shared LangGraph orchestration for CRM multi-agent workflows."""

from __future__ import annotations

import time
from typing import Any, Literal
from uuid import UUID

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.agents.compliance_agent import run_compliance_agent
from app.ai.agents.deal_orchestrator_agent import run_deal_orchestrator
from app.ai.agents.lead_qualifier_agent import run_lead_qualifier
from app.ai.agents.opportunity_watch_agent import run_opportunity_watch
from app.ai.agents.proposal_agent import run_proposal_agent
from app.ai.agents.research_agent import research_contact
from app.ai.agents.scheduler_agent import suggest_slots
from app.events import emit_event
from app.models import AgentRun, AuditLog, Contact, Deal, Task
from app.schemas.ai import DraftEmailResponse
from app.services.agent_runs import create_agent_run
from app.services.ai_email import generate_email_draft_content, persist_draft_and_approval
from app.services.audit import log_audit

NEW_LEAD_GRAPH = "NewLeadGraph"
DEAL_RESCUE_GRAPH = "DealRescueGraph"
PROPOSAL_GRAPH = "ProposalGraph"
APPROVAL_NODE = "approval_pause"


class CRMGraphState(BaseModel):
    team_id: str
    contact_id: str | None = None
    deal_id: str | None = None
    lead_score: int | None = None
    research_notes: dict[str, Any] = Field(default_factory=dict)
    risk_flags: list[str] = Field(default_factory=list)
    draft_id: str | None = None
    approval_id: str | None = None
    next_action: str | None = None
    history: list[str] = Field(default_factory=list)
    status: str = "running"
    current_node: str = "start"
    completed_nodes: list[str] = Field(default_factory=list)
    failed_node: str | None = None
    final_result: str | None = None
    actor_id: str | None = None
    trigger: str = "event"


async def run_new_lead_graph(
    db: AsyncSession,
    *,
    contact_id: UUID,
    team_id: UUID,
    actor_id: str | None = None,
    trigger: str = "contact.created",
) -> dict[str, Any]:
    graph = StateGraph(CRMGraphState)
    graph.add_node("LeadQualifierAgent", lambda state: _with_retry("LeadQualifierAgent", state, _lead_qualifier(db)))
    graph.add_node("ResearchAgent", lambda state: _with_retry("ResearchAgent", state, _research(db)))
    graph.add_node("NurturerAgent", lambda state: _with_retry("NurturerAgent", state, _new_lead_nurturer(db)))
    graph.add_node("ComplianceAgent", lambda state: _with_retry("ComplianceAgent", state, _compliance(db)))
    graph.add_node(APPROVAL_NODE, lambda state: _with_retry(APPROVAL_NODE, state, _approval_pause(db, NEW_LEAD_GRAPH)))
    graph.set_entry_point("LeadQualifierAgent")
    graph.add_edge("LeadQualifierAgent", "ResearchAgent")
    graph.add_edge("ResearchAgent", "NurturerAgent")
    graph.add_edge("NurturerAgent", "ComplianceAgent")
    graph.add_conditional_edges(
        "ComplianceAgent",
        _route_after_compliance,
        {"approval_pause": APPROVAL_NODE, "finish": END},
    )
    graph.add_edge(APPROVAL_NODE, END)
    initial = CRMGraphState(
        team_id=str(team_id),
        contact_id=str(contact_id),
        actor_id=actor_id,
        trigger=trigger,
        history=[trigger],
    )
    return await _run_and_record(db, graph.compile(), initial, graph_name=NEW_LEAD_GRAPH, event_name=trigger)


async def run_deal_rescue_graph(
    db: AsyncSession,
    *,
    deal_id: UUID,
    team_id: UUID,
    actor_id: str | None = None,
    trigger: str = "deal.rescue",
) -> dict[str, Any]:
    graph = StateGraph(CRMGraphState)
    graph.add_node("OpportunityWatchAgent", lambda state: _with_retry("OpportunityWatchAgent", state, _opportunity_watch(db)))
    graph.add_node("DealOrchestratorAgent", lambda state: _with_retry("DealOrchestratorAgent", state, _deal_orchestrator(db)))
    graph.add_node("SchedulerAgent", lambda state: _with_retry("SchedulerAgent", state, _scheduler_task(db)))
    graph.set_entry_point("OpportunityWatchAgent")
    graph.add_edge("OpportunityWatchAgent", "DealOrchestratorAgent")
    graph.add_edge("DealOrchestratorAgent", "SchedulerAgent")
    graph.add_edge("SchedulerAgent", END)
    initial = CRMGraphState(
        team_id=str(team_id),
        deal_id=str(deal_id),
        actor_id=actor_id,
        trigger=trigger,
        history=[trigger],
    )
    return await _run_and_record(db, graph.compile(), initial, graph_name=DEAL_RESCUE_GRAPH, event_name=trigger)


async def run_proposal_graph(
    db: AsyncSession,
    *,
    deal_id: UUID,
    team_id: UUID,
    actor_id: str | None = None,
    trigger: str = "deal.stage_changed",
) -> dict[str, Any]:
    graph = StateGraph(CRMGraphState)
    graph.add_node("ProposalAgent", lambda state: _with_retry("ProposalAgent", state, _proposal(db)))
    graph.add_node("ComplianceAgent", lambda state: _with_retry("ComplianceAgent", state, _compliance(db)))
    graph.add_node(APPROVAL_NODE, lambda state: _with_retry(APPROVAL_NODE, state, _approval_pause(db, PROPOSAL_GRAPH)))
    graph.set_entry_point("ProposalAgent")
    graph.add_edge("ProposalAgent", "ComplianceAgent")
    graph.add_conditional_edges(
        "ComplianceAgent",
        _route_after_compliance,
        {"approval_pause": APPROVAL_NODE, "finish": END},
    )
    graph.add_edge(APPROVAL_NODE, END)
    initial = CRMGraphState(
        team_id=str(team_id),
        deal_id=str(deal_id),
        actor_id=actor_id,
        trigger=trigger,
        history=[trigger],
    )
    return await _run_and_record(db, graph.compile(), initial, graph_name=PROPOSAL_GRAPH, event_name=trigger)


async def resume_graph_after_approval(
    db: AsyncSession,
    *,
    approval_id: UUID,
    team_id: UUID,
    actor_id: str | None = None,
) -> None:
    """Mark a paused graph complete after its approval send path has run."""
    result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.team_id == team_id,
            AuditLog.action == "graph.approval.paused",
        )
        .order_by(desc(AuditLog.created_at))
        .limit(200)
    )
    pause_log = next(
        (
            log
            for log in result.scalars().all()
            if (log.metadata_json or {}).get("approval_id") == str(approval_id)
        ),
        None,
    )
    if pause_log is None:
        return

    metadata = pause_log.metadata_json or {}
    run_id = metadata.get("run_id")
    if run_id:
        run = await db.get(AgentRun, UUID(str(run_id)))
        if run is not None and run.team_id == team_id and run.status == "paused":
            run.status = "completed"
            run.result = "sent_after_approval"

    await log_audit(
        db,
        action="graph.approval.resumed",
        entity_type="agent_approval",
        entity_id=str(approval_id),
        actor_type="system",
        actor_id=actor_id,
        team_id=team_id,
        metadata={
            **metadata,
            "approval_id": str(approval_id),
            "status": "completed",
            "current_node": "send_email",
            "completed_nodes": [*(metadata.get("completed_nodes") or []), "send_email"],
            "final_result": "sent_after_approval",
        },
    )
    await emit_event(
        "agent_run.completed",
        {
            "run_id": run_id,
            "team_id": str(team_id),
            "graph_name": metadata.get("graph_name"),
            "status": "completed",
            "result": "sent_after_approval",
        },
    )


def _lead_qualifier(db: AsyncSession):
    async def node(state: CRMGraphState) -> CRMGraphState:
        if not state.contact_id:
            return _fail_state(state, "LeadQualifierAgent", "missing_contact")
        await run_lead_qualifier(db, UUID(state.contact_id), UUID(state.team_id))
        contact = await db.get(Contact, UUID(state.contact_id))
        return _complete_node(
            state,
            "LeadQualifierAgent",
            lead_score=contact.lead_score if contact else None,
            history=[*state.history, "LeadQualifierAgent:scored"],
        )

    return node


def _research(db: AsyncSession):
    async def node(state: CRMGraphState) -> CRMGraphState:
        if not state.contact_id:
            return _complete_node(state, "ResearchAgent", history=[*state.history, "ResearchAgent:skipped"])
        notes = await research_contact(db, UUID(state.contact_id), UUID(state.team_id))
        return _complete_node(
            state,
            "ResearchAgent",
            research_notes=notes or {},
            history=[*state.history, "ResearchAgent:completed" if notes else "ResearchAgent:fallback_no_notes"],
        )

    return node


def _new_lead_nurturer(db: AsyncSession):
    async def node(state: CRMGraphState) -> CRMGraphState:
        if not state.contact_id:
            return _fail_state(state, "NurturerAgent", "missing_contact")
        contact = await db.get(Contact, UUID(state.contact_id))
        strategy = {
            "mode": "new_lead_nurture",
            "lead_score": state.lead_score,
            "research_notes": state.research_notes,
            "goal": "Nurture the new lead and ask for one low-friction next step.",
        }
        try:
            draft = await generate_email_draft_content(
                db,
                contact_id=UUID(state.contact_id),
                team_id=UUID(state.team_id),
                metadata={"route": NEW_LEAD_GRAPH, "agent": "NurturerAgent"},
                strategy_context=strategy,
            )
        except Exception:
            first_name = (contact.first_name if contact else "").strip() or "there"
            draft = DraftEmailResponse(
                subject="Great to connect",
                body=f"Hi {first_name},\n\nGreat to connect. I wanted to share a quick note and see whether there is a useful next step we can help with.\n\nWould a short introduction call be helpful?",
                tone="professional",
            )
        db.info["orchestration_draft"] = draft
        return _complete_node(state, "NurturerAgent", history=[*state.history, "NurturerAgent:draft_ready"])

    return node


def _proposal(db: AsyncSession):
    async def node(state: CRMGraphState) -> CRMGraphState:
        if not state.deal_id:
            return _fail_state(state, "ProposalAgent", "missing_deal")
        draft = await run_proposal_agent(
            db,
            deal_id=UUID(state.deal_id),
            team_id=UUID(state.team_id),
            actor_id=state.actor_id,
            trigger=state.trigger,
            force=False,
        )
        deal = await _load_deal(db, state)
        contact_id = str(deal.contact_id) if deal and deal.contact_id else None
        subject = f"Proposal for {deal.name}" if deal else "Proposal follow-up"
        body = (
            f"Hi {deal.contact.first_name if deal and deal.contact else 'there'},\n\n"
            f"I prepared a proposal draft for {deal.name if deal else 'our conversation'} and would be glad to walk through it with you.\n\n"
            "Would you like to review it together this week?"
        )
        db.info["orchestration_draft"] = DraftEmailResponse(subject=subject, body=body, tone="professional")
        return _complete_node(
            state,
            "ProposalAgent",
            contact_id=contact_id,
            draft_id=str(draft.document.id) if draft else None,
            history=[*state.history, "ProposalAgent:proposal_ready" if draft else "ProposalAgent:existing_or_skipped"],
        )

    return node


def _compliance(db: AsyncSession):
    async def node(state: CRMGraphState) -> CRMGraphState:
        draft: DraftEmailResponse | None = db.info.get("orchestration_draft")
        contact = await db.get(Contact, UUID(state.contact_id)) if state.contact_id else None
        passed, reason = run_compliance_agent(contact=contact, draft=draft)
        await log_audit(
            db,
            action="agent.compliance.passed" if passed else "agent.compliance.blocked",
            entity_type="contact" if state.contact_id else "deal",
            entity_id=state.contact_id or state.deal_id,
            actor_type="ai",
            actor_id=state.actor_id,
            team_id=UUID(state.team_id),
            metadata={"reason": reason, "graph": state.trigger},
        )
        await db.commit()
        risk_flags = state.risk_flags if passed else [*state.risk_flags, reason or "compliance_blocked"]
        return _complete_node(
            state,
            "ComplianceAgent",
            risk_flags=risk_flags,
            next_action="approval_pause" if passed else "blocked",
            status="running" if passed else "completed",
            final_result=state.final_result if passed else "blocked_pre_approval",
            history=[*state.history, "ComplianceAgent:passed" if passed else f"ComplianceAgent:blocked:{reason}"],
        )

    return node


def _approval_pause(db: AsyncSession, graph_name: str):
    async def node(state: CRMGraphState) -> CRMGraphState:
        draft: DraftEmailResponse | None = db.info.get("orchestration_draft")
        if not state.contact_id or draft is None:
            return _complete_node(
                state,
                APPROVAL_NODE,
                status="completed",
                final_result="no_sendable_draft",
                history=[*state.history, "Approval:skipped"],
            )
        email_draft, approval = await persist_draft_and_approval(
            db,
            contact_id=UUID(state.contact_id),
            team_id=UUID(state.team_id),
            deal_id=UUID(state.deal_id) if state.deal_id else None,
            response=draft,
        )
        await db.commit()
        await emit_event(
            "approval.created",
            {
                "approval_id": str(approval.id),
                "team_id": str(approval.team_id),
                "contact_id": str(approval.contact_id),
                "deal_id": str(approval.deal_id) if approval.deal_id else None,
                "subject": email_draft.subject,
                "type": approval.type,
                "status": approval.status,
            },
        )
        return _complete_node(
            state,
            APPROVAL_NODE,
            draft_id=str(email_draft.id),
            approval_id=str(approval.id),
            status="paused",
            current_node=APPROVAL_NODE,
            next_action="resume send_email",
            final_result="awaiting_approval",
            history=[*state.history, f"{graph_name}:paused_for_approval:{approval.id}"],
        )

    return node


def _opportunity_watch(db: AsyncSession):
    async def node(state: CRMGraphState) -> CRMGraphState:
        result = await run_opportunity_watch(
            db,
            team_id=UUID(state.team_id),
            actor_id=state.actor_id,
            deal_id=UUID(state.deal_id) if state.deal_id else None,
            trigger=state.trigger,
        )
        flags = state.risk_flags
        if int(result.get("signals_created") or result.get("created") or 0) > 0:
            flags = [*flags, "opportunity_watch_signal"]
        return _complete_node(state, "OpportunityWatchAgent", risk_flags=flags, history=[*state.history, "OpportunityWatchAgent:scanned"])

    return node


def _deal_orchestrator(db: AsyncSession):
    async def node(state: CRMGraphState) -> CRMGraphState:
        if not state.deal_id:
            return _fail_state(state, "DealOrchestratorAgent", "missing_deal")
        await run_deal_orchestrator(db, UUID(state.deal_id), UUID(state.team_id))
        deal = await db.get(Deal, UUID(state.deal_id))
        flags = state.risk_flags
        if deal and deal.deal_health in {"at_risk", "stalled"}:
            flags = [*flags, deal.deal_health]
        return _complete_node(state, "DealOrchestratorAgent", risk_flags=flags, history=[*state.history, "DealOrchestratorAgent:reviewed"])

    return node


def _scheduler_task(db: AsyncSession):
    async def node(state: CRMGraphState) -> CRMGraphState:
        deal = await _load_deal(db, state)
        slots = await suggest_slots(
            db,
            team_id=UUID(state.team_id),
            actor_id=state.actor_id,
            contact_id=deal.contact_id if deal else None,
            deal_id=UUID(state.deal_id) if state.deal_id else None,
        )
        first_slot = (slots.get("slots") or [{}])[0]
        task = Task(
            team_id=UUID(state.team_id),
            title=f"Rescue next step: {deal.name if deal else 'deal'}",
            description=f"Suggested next meeting slot: {first_slot.get('label') or 'review availability'}",
            priority="high",
            status="open",
            deal_id=UUID(state.deal_id) if state.deal_id else None,
            contact_id=deal.contact_id if deal else None,
            account_id=deal.account_id if deal else None,
        )
        db.add(task)
        await db.flush()
        await log_audit(
            db,
            action="task.created",
            entity_type="task",
            entity_id=str(task.id),
            actor_type="ai",
            actor_id=state.actor_id,
            team_id=UUID(state.team_id),
            metadata={"source": DEAL_RESCUE_GRAPH, "deal_id": state.deal_id, "slot": first_slot},
        )
        await db.commit()
        return _complete_node(
            state,
            "SchedulerAgent",
            next_action="task_created",
            status="completed",
            final_result="task_created",
            history=[*state.history, f"SchedulerAgent:task_created:{task.id}"],
        )

    return node


async def _run_and_record(
    db: AsyncSession,
    graph: Any,
    initial: CRMGraphState,
    *,
    graph_name: str,
    event_name: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        raw_state = await graph.ainvoke(initial)
        final_state = raw_state if isinstance(raw_state, CRMGraphState) else CRMGraphState(**raw_state)
    except Exception as exc:
        final_state = _fail_state(initial, initial.current_node or "graph", str(exc))

    duration_ms = int((time.perf_counter() - started) * 1000)
    result = final_state.final_result or ("failed" if final_state.status == "failed" else final_state.next_action or "completed")
    run = await create_agent_run(
        db,
        team_id=UUID(final_state.team_id),
        graph_name=graph_name,
        event_name=event_name,
        deal_id=UUID(final_state.deal_id) if final_state.deal_id else None,
        status_value=final_state.status,
        result=result[:100],
        duration_ms=duration_ms,
    )
    metadata = {
        "run_id": str(run.id),
        "graph_name": graph_name,
        "current_node": final_state.current_node,
        "completed_nodes": final_state.completed_nodes,
        "failed_node": final_state.failed_node,
        "duration_ms": duration_ms,
        "final_result": result,
        "approval_id": final_state.approval_id,
        "draft_id": final_state.draft_id,
        "next_action": final_state.next_action,
        "history": final_state.history,
        "risk_flags": final_state.risk_flags,
    }
    await log_audit(
        db,
        action="graph.approval.paused" if final_state.status == "paused" else f"graph.{graph_name}.completed",
        entity_type="agent_run",
        entity_id=str(run.id),
        actor_type="system",
        actor_id=final_state.actor_id,
        team_id=UUID(final_state.team_id),
        metadata=metadata,
    )
    await db.commit()
    await emit_event(
        "agent_run.created",
        {
            "run_id": str(run.id),
            "team_id": final_state.team_id,
            "graph_name": graph_name,
            "status": final_state.status,
            "result": result,
            "duration_ms": duration_ms,
        },
    )
    return {"run_id": str(run.id), "status": final_state.status, "result": result, **metadata}


async def _with_retry(node_name: str, state: CRMGraphState, func: Any) -> CRMGraphState:
    try:
        return await func(state)
    except Exception as exc:
        try:
            return await func(state)
        except Exception as retry_exc:
            return _fail_state(state, node_name, str(retry_exc or exc))


def _route_after_compliance(state: CRMGraphState) -> Literal["approval_pause", "finish"]:
    return "approval_pause" if state.next_action == "approval_pause" and state.status != "completed" else "finish"


def _complete_node(state: CRMGraphState, node_name: str, **updates: Any) -> CRMGraphState:
    completed = [*state.completed_nodes]
    if node_name not in completed:
        completed.append(node_name)
    return state.model_copy(update={"current_node": node_name, "completed_nodes": completed, **updates})


def _fail_state(state: CRMGraphState, node_name: str, reason: str) -> CRMGraphState:
    return state.model_copy(
        update={
            "current_node": node_name,
            "failed_node": node_name,
            "status": "failed",
            "final_result": "failed",
            "history": [*state.history, f"{node_name}:failed:{reason}"],
        }
    )


async def _load_deal(db: AsyncSession, state: CRMGraphState) -> Deal | None:
    if not state.deal_id:
        return None
    result = await db.execute(
        select(Deal)
        .options(selectinload(Deal.contact), selectinload(Deal.account), selectinload(Deal.stage))
        .where(Deal.id == UUID(state.deal_id), Deal.team_id == UUID(state.team_id))
    )
    return result.scalar_one_or_none()
