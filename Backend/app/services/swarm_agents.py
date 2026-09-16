"""Manual Swarm Console agent runners."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.agents.compliance_agent import run_compliance_agent
from app.ai.agents.deal_orchestrator_agent import analyze_deal_health
from app.ai.agents.lead_qualifier_agent import score_contact
from app.ai.agents.nurturer_agent import run_nurturer_scan
from app.ai.agents.opportunity_watch_agent import run_opportunity_watch
from app.ai.agents.proposal_agent import run_proposal_agent
from app.ai.agents.research_agent import research_account, research_contact
from app.ai.agents.scheduler_agent import suggest_slots
from app.events import emit_event
from app.models import Account, AgentApproval, AuditLog, Contact, Deal, DealStage, Document, Task
from app.schemas.ai import DraftEmailResponse
from app.services.agent_runs import create_agent_run
from app.services.audit import log_audit

ManualRunner = Callable[[AsyncSession, UUID, str | None], Awaitable[dict[str, Any]]]


async def run_swarm_agent(
    db: AsyncSession,
    *,
    agent_name: str,
    team_id: UUID,
    actor_id: str | None,
) -> dict[str, Any]:
    """Run one tenant-scoped CRM agent and persist a uniform run record."""
    runners: dict[str, ManualRunner] = {
        "LeadQualifierAgent": _run_lead_qualifier,
        "ResearchAgent": _run_research,
        "NurturerAgent": _run_nurturer,
        "SchedulerAgent": _run_scheduler,
        "DealOrchestratorAgent": _run_deal_orchestrator,
        "ComplianceAgent": _run_compliance,
        "OpportunityWatchAgent": _run_opportunity_watch,
        "ProposalAgent": _run_proposal,
    }
    runner = runners.get(agent_name)
    if runner is None:
        raise ValueError("Unknown swarm agent.")

    started = perf_counter()
    status_value = "completed"
    try:
        result = await runner(db, team_id, actor_id)
    except Exception as exc:
        await db.rollback()
        status_value = "failed"
        result = {
            "summary": f"{agent_name} failed: {exc}",
            "records_affected": 0,
            "message": str(exc),
            "result": "failed",
        }

    duration_ms = int((perf_counter() - started) * 1000)
    summary = str(result.get("summary") or result.get("message") or "Agent run completed.")
    records_affected = int(result.get("records_affected") or 0)
    run_result = str(result.get("result") or ("no_action" if records_affected == 0 else "completed"))

    run = await create_agent_run(
        db,
        team_id=team_id,
        graph_name=agent_name,
        event_name="manual",
        deal_id=result.get("deal_id"),
        status_value=status_value,
        result=run_result[:100],
        duration_ms=duration_ms,
    )
    action_suffix = "manual_run_failed" if status_value == "failed" else "manual_run"
    await log_audit(
        db,
        action=f"agent.{_agent_key(agent_name)}.{action_suffix}",
        entity_type="agent",
        entity_id=str(run.id),
        actor_type="ai",
        actor_id=actor_id,
        team_id=team_id,
        metadata={
            "agent_name": agent_name,
            "run_id": str(run.id),
            "summary": summary,
            "records_affected": records_affected,
            "status": status_value,
            **(result.get("metadata") or {}),
        },
    )
    await db.commit()
    await emit_event(
        "agent_run.completed",
        {
            "team_id": str(team_id),
            "run_id": str(run.id),
            "agent_name": agent_name,
            "summary": summary,
            "records_affected": records_affected,
            "status": status_value,
        },
    )
    return {
        "status": status_value,
        "summary": summary,
        "records_affected": records_affected,
        "message": result.get("message") or summary,
        "run_id": str(run.id),
    }


async def _run_lead_qualifier(db: AsyncSession, team_id: UUID, actor_id: str | None) -> dict[str, Any]:
    result = await db.execute(select(Contact).where(Contact.team_id == team_id).order_by(Contact.updated_at.desc()))
    contacts = list(result.scalars().all())
    counts = {"Hot": 0, "Warm": 0, "Cold": 0}
    reasons: list[str] = []
    for contact in contacts:
        score, tier, reason = score_contact(contact)
        contact.lead_score = score
        contact.lead_tier = tier
        contact.lead_reason = reason
        counts[tier] += 1
        if len(reasons) < 3:
            name = f"{contact.first_name} {contact.last_name}".strip()
            reasons.append(f"{name}: {tier} ({score}) - {reason}")

    if not contacts:
        summary = "No leads found to score."
    else:
        summary = f"{counts['Hot']} hot / {counts['Warm']} warm / {counts['Cold']} cold leads scored."
        if reasons:
            summary = f"{summary} Reasons: {'; '.join(reasons)}"
    return {
        "summary": summary,
        "records_affected": len(contacts),
        "metadata": {"hot": counts["Hot"], "warm": counts["Warm"], "cold": counts["Cold"], "reasons": reasons},
    }


async def _run_research(db: AsyncSession, team_id: UUID, actor_id: str | None) -> dict[str, Any]:
    del actor_id
    researched = await _recent_researched_entity_ids(db, team_id=team_id)
    contact_result = await db.execute(
        select(Contact).where(Contact.team_id == team_id).order_by(Contact.updated_at.desc()).limit(5)
    )
    account_result = await db.execute(
        select(Account).where(Account.team_id == team_id).order_by(Account.updated_at.desc()).limit(5)
    )
    targets: list[tuple[str, UUID]] = [
        ("contact", contact.id) for contact in contact_result.scalars().all() if f"contact:{contact.id}" not in researched
    ]
    targets.extend(
        ("account", account.id) for account in account_result.scalars().all() if f"account:{account.id}" not in researched
    )

    added = 0
    summaries: list[str] = []
    for entity_type, entity_id in targets[:5]:
        output = await (research_contact(db, entity_id, team_id) if entity_type == "contact" else research_account(db, entity_id, team_id))
        if output:
            added += 1
            summaries.append(str(output.get("research_summary") or output.get("outreach_angle") or entity_type))

    summary = "No contacts/accounts were enriched." if added == 0 else f"{added} summaries/notes added."
    if summaries:
        summary = f"{summary} {'; '.join(summaries[:3])}"
    return {"summary": summary, "records_affected": added, "metadata": {"summaries": summaries[:5]}}


async def _run_nurturer(db: AsyncSession, team_id: UUID, actor_id: str | None) -> dict[str, Any]:
    result = await run_nurturer_scan(db, team_id=team_id, actor_id=actor_id)
    created = int(result.get("created") or 0)
    summary = "No stale deals found." if created == 0 else f"{created} drafts created."
    return {"summary": summary, "records_affected": created, "metadata": result}


async def _run_scheduler(db: AsyncSession, team_id: UUID, actor_id: str | None) -> dict[str, Any]:
    result = await suggest_slots(db, team_id=team_id, actor_id=actor_id)
    slots = result.get("slots") or []
    summary = "No available meeting slots found." if len(slots) == 0 else f"{len(slots)} suggestions created."
    return {"summary": summary, "records_affected": len(slots), "metadata": {"slots": slots}}


async def _run_deal_orchestrator(db: AsyncSession, team_id: UUID, actor_id: str | None) -> dict[str, Any]:
    result = await db.execute(
        select(Deal)
        .options(selectinload(Deal.stage))
        .where(Deal.team_id == team_id)
        .order_by(Deal.updated_at.desc())
    )
    deals = list(result.scalars().all())
    attention: list[str] = []
    for deal in deals:
        if deal.stage and deal.stage.is_closed:
            continue
        health, reason = analyze_deal_health(deal)
        deal.deal_health = health
        deal.deal_reason = reason
        if health in {"at_risk", "stalled"}:
            attention.append(f"{deal.name}: {health} - {reason}")
            await _ensure_attention_task(db, deal=deal, actor_id=actor_id, reason=reason)

    count = len(attention)
    summary = "No stale deals found." if count == 0 else f"{count} deals need attention."
    if attention:
        summary = f"{summary} {'; '.join(attention[:3])}"
    return {"summary": summary, "records_affected": count, "metadata": {"attention": attention[:10]}}


async def _run_compliance(db: AsyncSession, team_id: UUID, actor_id: str | None) -> dict[str, Any]:
    result = await db.execute(
        select(AgentApproval)
        .options(selectinload(AgentApproval.contact), selectinload(AgentApproval.draft))
        .where(AgentApproval.team_id == team_id, AgentApproval.status == "pending")
        .order_by(AgentApproval.created_at.desc())
        .limit(100)
    )
    approvals = list(result.scalars().all())
    passed = 0
    blocked = 0
    reasons: list[str] = []
    for approval in approvals:
        draft = DraftEmailResponse(subject=approval.draft.subject, body=approval.draft.body, tone="professional")
        ok, reason = run_compliance_agent(contact=approval.contact, draft=draft)
        passed += 1 if ok else 0
        blocked += 0 if ok else 1
        action = "agent.compliance.passed" if ok else "agent.compliance.blocked"
        await log_audit(
            db,
            action=action,
            entity_type="agent_approval",
            entity_id=str(approval.id),
            actor_type="ai",
            actor_id=actor_id,
            team_id=team_id,
            metadata={"approval_id": str(approval.id), "reason": reason},
        )
        if reason:
            reasons.append(reason)

    summary = f"{passed} passed / {blocked} blocked."
    if not approvals:
        summary = "No pending drafts found."
    elif reasons:
        summary = f"{summary} Blocked reasons: {'; '.join(reasons[:3])}"
    return {"summary": summary, "records_affected": len(approvals), "metadata": {"passed": passed, "blocked": blocked}}


async def _run_opportunity_watch(db: AsyncSession, team_id: UUID, actor_id: str | None) -> dict[str, Any]:
    result = await run_opportunity_watch(db, team_id=team_id, actor_id=actor_id, trigger="manual")
    created = int(result.get("signals_created") or result.get("created") or 0)
    summary = f"Found {created} opportunities." if created else "Found 0 opportunities."
    return {"summary": summary, "records_affected": created, "metadata": result}


async def _run_proposal(db: AsyncSession, team_id: UUID, actor_id: str | None) -> dict[str, Any]:
    result = await db.execute(
        select(Deal)
        .join(DealStage, Deal.stage_id == DealStage.id)
        .where(
            Deal.team_id == team_id,
            DealStage.is_closed.is_(False),
            func.lower(DealStage.name).like("%proposal%"),
        )
        .order_by(Deal.updated_at.desc())
        .limit(20)
    )
    deals = list(result.scalars().all())
    created = 0
    titles: list[str] = []
    for deal in deals:
        existing = await db.scalar(
            select(Document.id)
            .where(
                Document.team_id == team_id,
                Document.deal_id == deal.id,
                Document.document_type == "proposal",
                Document.status == "draft",
            )
            .limit(1)
        )
        if existing is not None:
            continue
        draft = await run_proposal_agent(
            db,
            deal_id=deal.id,
            team_id=team_id,
            actor_id=actor_id,
            trigger="manual",
            force=False,
        )
        if draft is not None:
            created += 1
            titles.append(draft.title)

    summary = "No Proposal-stage deals found." if not deals else f"{created} proposals created."
    if titles:
        summary = f"{summary} {'; '.join(titles[:3])}"
    return {"summary": summary, "records_affected": created, "metadata": {"titles": titles[:10]}}


async def _recent_researched_entity_ids(db: AsyncSession, *, team_id: UUID) -> set[str]:
    cutoff = datetime.now(UTC) - timedelta(days=14)
    result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.team_id == team_id,
            AuditLog.action.in_(["agent.research.completed", "agent.research_completed"]),
            AuditLog.created_at >= cutoff,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(200)
    )
    return {f"{log.entity_type}:{log.entity_id}" for log in result.scalars().all() if log.entity_id}


async def _ensure_attention_task(db: AsyncSession, *, deal: Deal, actor_id: str | None, reason: str) -> None:
    existing = await db.scalar(
        select(Task.id)
        .where(
            Task.team_id == deal.team_id,
            Task.deal_id == deal.id,
            Task.status == "open",
            or_(Task.title == f"Follow up deal needing attention: {deal.name}", Task.title == f"Follow up stalled deal: {deal.name}"),
        )
        .limit(1)
    )
    if existing is not None:
        return
    task = Task(
        team_id=deal.team_id,
        title=f"Follow up deal needing attention: {deal.name}",
        description=f"Next best action: reconnect with the buyer and confirm next step.\n\nReason: {reason}",
        priority="high" if deal.deal_health == "stalled" else "med",
        status="open",
        deal_id=deal.id,
        contact_id=deal.contact_id,
        account_id=deal.account_id,
    )
    db.add(task)
    await db.flush()
    await log_audit(
        db,
        action="task.created",
        entity_type="task",
        entity_id=str(task.id),
        actor_type="ai",
        actor_id=actor_id,
        team_id=deal.team_id,
        metadata={"deal_id": str(deal.id), "source": "DealOrchestratorAgent", "reason": reason},
    )


def _agent_key(agent_name: str) -> str:
    mapping = {
        "LeadQualifierAgent": "lead_qualifier",
        "ResearchAgent": "research",
        "NurturerAgent": "nurturer",
        "SchedulerAgent": "scheduler",
        "DealOrchestratorAgent": "deal_orchestrator",
        "ComplianceAgent": "compliance",
        "OpportunityWatchAgent": "opportunity_watch",
        "ProposalAgent": "proposal",
    }
    return mapping[agent_name]
