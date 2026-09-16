"""Lightweight structured memory derived from CRM history."""

from __future__ import annotations

import re
import time
from collections import Counter
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AgentApproval, AgentRun, AuditLog, Contact, Deal, EmailDraft
from app.schemas.ai import ContactMemoryResponse

_CACHE_TTL_SECONDS = 60
_memory_cache: dict[str, tuple[float, ContactMemoryResponse]] = {}
_TOPIC_STOP_WORDS = {
    "a",
    "an",
    "and",
    "checking",
    "follow",
    "followup",
    "following",
    "for",
    "hello",
    "hi",
    "in",
    "next",
    "on",
    "proposal",
    "quick",
    "regarding",
    "the",
    "up",
    "with",
    "your",
}


async def get_contact_memory(db: AsyncSession, contact_id: UUID, *, team_id: UUID) -> ContactMemoryResponse:
    """Return a compact structured memory summary for a contact."""
    cache_key = f"{team_id}:{contact_id}"
    cached = _memory_cache.get(cache_key)
    now = time.monotonic()
    if cached is not None and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    contact = await db.get(Contact, contact_id)
    if contact is None or contact.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found.",
        )

    drafts_result = await db.execute(
        select(EmailDraft)
        .where(EmailDraft.contact_id == contact.id, EmailDraft.team_id == team_id)
        .order_by(EmailDraft.created_at.desc())
        .limit(15)
    )
    drafts = list(drafts_result.scalars().all())

    approvals_result = await db.execute(
        select(AgentApproval)
        .options(selectinload(AgentApproval.draft))
        .where(AgentApproval.contact_id == contact.id, AgentApproval.team_id == team_id)
        .order_by(AgentApproval.created_at.desc())
        .limit(15)
    )
    approvals = list(approvals_result.scalars().all())

    deals_result = await db.execute(
        select(Deal)
        .options(selectinload(Deal.stage))
        .where(Deal.contact_id == contact.id, Deal.team_id == team_id)
        .order_by(Deal.updated_at.desc())
    )
    deals = list(deals_result.scalars().all())
    deal_ids = [deal.id for deal in deals]
    deal_id_strings = [str(deal_id) for deal_id in deal_ids]

    audit_logs: list[AuditLog] = []
    if deal_id_strings:
        audit_result = await db.execute(
            select(AuditLog)
            .where(
                or_(
                    (AuditLog.entity_type == "contact") & (AuditLog.entity_id == str(contact.id)),
                    (AuditLog.entity_type == "deal") & (AuditLog.entity_id.in_(deal_id_strings)),
                ),
                AuditLog.team_id == team_id,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(25)
        )
        audit_logs = list(audit_result.scalars().all())
    else:
        audit_result = await db.execute(
            select(AuditLog)
            .where(
                (AuditLog.entity_type == "contact") & (AuditLog.entity_id == str(contact.id)),
                AuditLog.team_id == team_id,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(25)
        )
        audit_logs = list(audit_result.scalars().all())

    agent_runs: list[AgentRun] = []
    if deal_ids:
        run_result = await db.execute(
            select(AgentRun)
            .where(AgentRun.deal_id.in_(deal_ids), AgentRun.team_id == team_id)
            .order_by(AgentRun.created_at.desc())
            .limit(15)
        )
        agent_runs = list(run_result.scalars().all())

    memory = ContactMemoryResponse(
        relationship_status=_build_relationship_status(deals, approvals),
        last_contacted_at=_build_last_contacted_at(drafts, approvals, audit_logs),
        common_topics=_build_common_topics(drafts, deals, audit_logs, agent_runs),
        responsiveness=_build_responsiveness(approvals, agent_runs),
        recommended_tone=_build_recommended_tone(deals, approvals, agent_runs),
    )
    _memory_cache[cache_key] = (now, memory)
    return memory


def _build_relationship_status(deals: list[Deal], approvals: list[AgentApproval]) -> str:
    if not deals and not approvals:
        return "new relationship"

    latest_stage = (deals[0].stage.name if deals and deals[0].stage else "").lower()
    if latest_stage == "won":
        return "closed won"
    if latest_stage == "lost":
        return "closed lost"
    if latest_stage in {"proposal", "negotiation"}:
        return "active opportunity"
    if latest_stage in {"lead", "qualified", "meeting"}:
        return "developing conversation"
    return "engaged contact"


def _build_last_contacted_at(
    drafts: list[EmailDraft],
    approvals: list[AgentApproval],
    audit_logs: list[AuditLog],
) -> datetime | None:
    timestamps: list[datetime] = []
    timestamps.extend(draft.created_at for draft in drafts)
    for approval in approvals:
        if approval.executed_at is not None:
            timestamps.append(approval.executed_at)
        elif approval.decided_at is not None:
            timestamps.append(approval.decided_at)
        else:
            timestamps.append(approval.created_at)
    timestamps.extend(log.created_at for log in audit_logs[:10])
    return max(timestamps) if timestamps else None


def _build_common_topics(
    drafts: list[EmailDraft],
    deals: list[Deal],
    audit_logs: list[AuditLog],
    agent_runs: list[AgentRun],
) -> list[str]:
    tokens: Counter[str] = Counter()

    for draft in drafts[:10]:
        for token in _tokenize_topic_source(draft.subject):
            tokens[token] += 2

    for deal in deals[:5]:
        if deal.stage and deal.stage.name:
            tokens[deal.stage.name.lower()] += 1
        for token in _tokenize_topic_source(deal.name):
            tokens[token] += 1

    for log in audit_logs[:10]:
        metadata = log.metadata_json or {}
        recommended_angle = metadata.get("recommended_angle")
        if isinstance(recommended_angle, str) and recommended_angle:
            tokens[recommended_angle.replace("_", " ")] += 2

    for run in agent_runs[:5]:
        tokens[run.graph_name.replace("_", " ")] += 1

    topics = [topic for topic, _ in tokens.most_common(4)]
    return topics or ["general follow-up"]


def _build_responsiveness(approvals: list[AgentApproval], agent_runs: list[AgentRun]) -> str:
    sent_or_approved = sum(
        1 for approval in approvals if approval.execution_status == "sent" or approval.status == "approved"
    )
    blocked_or_rejected = sum(
        1
        for approval in approvals
        if approval.status == "rejected" or approval.execution_status == "blocked_compliance"
    )
    draft_runs = sum(1 for run in agent_runs if run.result == "draft_created")

    if sent_or_approved >= 3:
        return "high"
    if sent_or_approved >= 1 or draft_runs >= 2:
        return "medium"
    if blocked_or_rejected >= 2:
        return "low"
    if approvals and all(approval.status == "pending" for approval in approvals[:3]):
        return "awaiting response"
    return "unknown"


def _build_recommended_tone(
    deals: list[Deal],
    approvals: list[AgentApproval],
    agent_runs: list[AgentRun],
) -> str:
    relationship_status = _build_relationship_status(deals, approvals)
    responsiveness = _build_responsiveness(approvals, agent_runs)

    if relationship_status == "closed lost":
        return "respectful and brief"
    if responsiveness == "high":
        return "warm and confident"
    if responsiveness in {"low", "awaiting response"}:
        return "concise and low-pressure"
    return "professional and helpful"


def _tokenize_topic_source(text: str | None) -> list[str]:
    if not text:
        return []
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return [word for word in words if word not in _TOPIC_STOP_WORDS]
