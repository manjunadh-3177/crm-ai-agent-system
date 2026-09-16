"""Nurturer agent for inactive open deals."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.events import emit_event
from app.models import AgentApproval, AuditLog, Contact, Deal, DealStage, Note
from app.schemas.ai import DraftEmailResponse
from app.services.ai_email import generate_email_draft_content, persist_draft_and_approval
from app.services.audit import log_audit
from app.services.notifications import create_notification


INACTIVE_AFTER_DAYS = 7
RECENT_NURTURE_WINDOW_DAYS = 7


async def run_nurturer_scan(
    db: AsyncSession,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Create nurture approvals for inactive open deals."""
    deals = await _load_open_deals(db, team_id=team_id)
    audit_logs = await _load_recent_audit_logs(db, team_id=team_id)
    notes = await _load_recent_notes(db, team_id=team_id)
    now = datetime.now(UTC)

    created = 0
    skipped = 0
    created_approval_ids: list[str] = []

    for deal in deals:
        result = await _maybe_create_nurture(
            db,
            deal=deal,
            audit_logs=audit_logs,
            notes=notes,
            actor_id=actor_id,
            now=now,
            manual=False,
        )
        if result["status"] == "created":
            created += 1
            created_approval_ids.append(result["approval_id"])
        else:
            skipped += 1

    await db.commit()
    return {
        "status": "completed",
        "created": created,
        "skipped": skipped,
        "approval_ids": created_approval_ids,
    }


async def generate_nurture_now(
    db: AsyncSession,
    *,
    team_id: UUID,
    actor_id: str | None = None,
    deal_id: UUID | None = None,
    contact_id: UUID | None = None,
) -> dict[str, Any]:
    """Manually generate a nurture suggestion for a deal/contact."""
    if deal_id is None and contact_id is None:
        return {"status": "skipped", "reason": "missing_target"}

    deal = await _resolve_target_deal(
        db,
        team_id=team_id,
        deal_id=deal_id,
        contact_id=contact_id,
    )
    if deal is None:
        return {"status": "skipped", "reason": "deal_not_found"}

    result = await _maybe_create_nurture(
        db,
        deal=deal,
        audit_logs=await _load_recent_audit_logs(db, team_id=team_id),
        notes=await _load_recent_notes(db, team_id=team_id),
        actor_id=actor_id,
        now=datetime.now(UTC),
        manual=True,
    )
    await db.commit()
    return result


async def get_nurture_status(db: AsyncSession, *, team_id: UUID) -> dict[str, Any]:
    """Return current pending nurture approval status for the team."""
    approvals_result = await db.execute(
        select(AgentApproval)
        .options(selectinload(AgentApproval.draft))
        .where(AgentApproval.team_id == team_id, AgentApproval.status == "pending")
        .order_by(desc(AgentApproval.created_at))
    )
    pending_approvals = list(approvals_result.scalars().all())

    logs_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.team_id == team_id, AuditLog.action == "agent.nurturer_triggered")
        .order_by(desc(AuditLog.created_at))
        .limit(200)
    )
    nurture_logs = list(logs_result.scalars().all())

    nurture_log_by_approval_id: dict[str, dict[str, Any]] = {}
    for log in nurture_logs:
        metadata = log.metadata_json or {}
        approval_id = metadata.get("approval_id")
        if approval_id and approval_id not in nurture_log_by_approval_id:
            nurture_log_by_approval_id[str(approval_id)] = metadata

    pending_nurtures: list[dict[str, Any]] = []
    pending_contact_ids: list[str] = []
    pending_deal_ids: list[str] = []

    for approval in pending_approvals:
        metadata = nurture_log_by_approval_id.get(str(approval.id))
        if metadata is None:
            continue

        contact_id = str(approval.contact_id)
        deal_id = str(approval.deal_id) if approval.deal_id else None
        pending_nurtures.append(
            {
                "approval_id": str(approval.id),
                "contact_id": contact_id,
                "deal_id": deal_id,
                "created_at": approval.created_at.isoformat(),
            }
        )
        if contact_id not in pending_contact_ids:
            pending_contact_ids.append(contact_id)
        if deal_id and deal_id not in pending_deal_ids:
            pending_deal_ids.append(deal_id)

    return {
        "pending_count": len(pending_nurtures),
        "pending_contact_ids": pending_contact_ids,
        "pending_deal_ids": pending_deal_ids,
        "pending_items": pending_nurtures,
    }


async def _maybe_create_nurture(
    db: AsyncSession,
    *,
    deal: Deal,
    audit_logs: list[AuditLog],
    notes: list[Note],
    actor_id: str | None,
    now: datetime,
    manual: bool,
) -> dict[str, Any]:
    if deal.stage is None or deal.stage.is_closed or deal.contact is None:
        return {"status": "skipped", "reason": "deal_not_eligible"}

    last_activity_at = _get_last_activity_at(deal=deal, audit_logs=audit_logs, notes=notes)
    if not manual and last_activity_at > now - timedelta(days=INACTIVE_AFTER_DAYS):
        return {"status": "skipped", "reason": "recent_activity"}

    if _recent_nurture_exists(deal=deal, audit_logs=audit_logs, now=now):
        return {"status": "skipped", "reason": "recent_nurture_exists"}

    research_context = _get_research_context(deal=deal, notes=notes)
    draft = await generate_email_draft_content(
        db,
        contact_id=deal.contact_id,
        team_id=deal.team_id,
        deal_id=deal.id,
        metadata={
            "route": "nurturer_agent",
            "team_id": str(deal.team_id),
            "user_id": actor_id,
            "deal_id": str(deal.id),
            "contact_id": str(deal.contact_id),
            "account_id": str(deal.account_id) if deal.account_id else None,
            "nurture_manual": manual,
        },
        strategy_context={
            "mode": "nurture_follow_up",
            "contact_name": f"{deal.contact.first_name} {deal.contact.last_name}".strip(),
            "company_name": deal.account.name if deal.account else None,
            "deal_stage": deal.stage.name,
            "last_activity_date": last_activity_at.date().isoformat(),
            "last_activity_days_ago": max((now - last_activity_at).days, 0),
            "research_summary": research_context.get("research_summary"),
            "outreach_angle": research_context.get("outreach_angle"),
        },
    )
    draft = _normalize_nurture_draft(draft, deal=deal, last_activity_at=last_activity_at)
    _, approval = await persist_draft_and_approval(
        db,
        contact_id=deal.contact_id,
        team_id=deal.team_id,
        deal_id=deal.id,
        response=draft,
    )
    await log_audit(
        db,
        action="agent.nurturer_triggered",
        entity_type="deal",
        entity_id=str(deal.id),
        actor_type="ai",
        actor_id=actor_id,
        team_id=deal.team_id,
        metadata={
            "approval_id": str(approval.id),
            "contact_id": str(deal.contact_id),
            "deal_id": str(deal.id),
            "account_id": str(deal.account_id) if deal.account_id else None,
            "stage": deal.stage.name,
            "last_activity_at": last_activity_at.isoformat(),
            "manual": manual,
        },
    )
    await emit_event(
        "approval.created",
        {
            "approval_id": str(approval.id),
            "team_id": str(approval.team_id),
            "contact_id": str(approval.contact_id),
            "deal_id": str(approval.deal_id) if approval.deal_id else None,
            "subject": draft.subject,
            "type": approval.type,
            "status": approval.status,
        },
    )

    # Generate notification
    await create_notification(
        db,
        team_id=deal.team_id,
        type="nurture.suggested",
        title="Nurture Suggestion",
        message=f"AI suggested a follow-up for deal '{deal.name}' with contact '{deal.contact.first_name} {deal.contact.last_name}'.",
        entity_type="agent_approval",
        entity_id=str(approval.id),
    )

    return {"status": "created", "approval_id": str(approval.id)}


async def _load_open_deals(db: AsyncSession, *, team_id: UUID) -> list[Deal]:
    result = await db.execute(
        select(Deal)
        .join(DealStage, Deal.stage_id == DealStage.id)
        .options(
            selectinload(Deal.stage),
            selectinload(Deal.contact),
            selectinload(Deal.account),
        )
        .where(Deal.team_id == team_id, DealStage.is_closed.is_(False))
        .order_by(desc(Deal.updated_at))
    )
    return list(result.scalars().all())


async def _resolve_target_deal(
    db: AsyncSession,
    *,
    team_id: UUID,
    deal_id: UUID | None,
    contact_id: UUID | None,
) -> Deal | None:
    if deal_id is not None:
        result = await db.execute(
            select(Deal)
            .join(DealStage, Deal.stage_id == DealStage.id)
            .options(
                selectinload(Deal.stage),
                selectinload(Deal.contact),
                selectinload(Deal.account),
            )
            .where(Deal.id == deal_id, Deal.team_id == team_id, DealStage.is_closed.is_(False))
        )
        return result.scalar_one_or_none()

    result = await db.execute(
        select(Deal)
        .join(DealStage, Deal.stage_id == DealStage.id)
        .options(
            selectinload(Deal.stage),
            selectinload(Deal.contact),
            selectinload(Deal.account),
        )
        .where(
            Deal.team_id == team_id,
            Deal.contact_id == contact_id,
            DealStage.is_closed.is_(False),
        )
        .order_by(desc(Deal.updated_at))
    )
    return result.scalars().first()


async def _load_recent_audit_logs(db: AsyncSession, *, team_id: UUID) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.team_id == team_id)
        .order_by(desc(AuditLog.created_at))
        .limit(500)
    )
    return list(result.scalars().all())


async def _load_recent_notes(db: AsyncSession, *, team_id: UUID) -> list[Note]:
    result = await db.execute(
        select(Note)
        .where(Note.team_id == team_id)
        .order_by(desc(Note.created_at))
        .limit(200)
    )
    return list(result.scalars().all())


def _get_last_activity_at(*, deal: Deal, audit_logs: list[AuditLog], notes: list[Note]) -> datetime:
    timestamps = [deal.updated_at]
    deal_id = str(deal.id)
    contact_id = str(deal.contact_id) if deal.contact_id else None

    for log in audit_logs:
        metadata = log.metadata_json or {}
        if (
            (log.entity_type == "deal" and log.entity_id == deal_id)
            or metadata.get("deal_id") == deal_id
            or (contact_id and log.entity_type == "contact" and log.entity_id == contact_id)
            or (contact_id and metadata.get("contact_id") == contact_id)
        ):
            timestamps.append(log.created_at)

    for note in notes:
        if (note.entity_type == "deal" and str(note.entity_id) == deal_id) or (
            contact_id and note.entity_type == "contact" and str(note.entity_id) == contact_id
        ):
            timestamps.append(note.created_at)

    return max(timestamps)


def _recent_nurture_exists(*, deal: Deal, audit_logs: list[AuditLog], now: datetime) -> bool:
    cutoff = now - timedelta(days=RECENT_NURTURE_WINDOW_DAYS)
    deal_id = str(deal.id)
    contact_id = str(deal.contact_id) if deal.contact_id else None

    for log in audit_logs:
        if log.action != "agent.nurturer_triggered" or log.created_at < cutoff:
            continue
        metadata = log.metadata_json or {}
        if metadata.get("deal_id") == deal_id:
            return True
        if contact_id and metadata.get("contact_id") == contact_id:
            return True
    return False


def _get_research_context(*, deal: Deal, notes: list[Note]) -> dict[str, str | None]:
    note_candidates: list[Note] = []
    if deal.contact_id:
        note_candidates.extend(
            note
            for note in notes
            if note.entity_type == "contact" and str(note.entity_id) == str(deal.contact_id)
        )
    if deal.account_id:
        note_candidates.extend(
            note
            for note in notes
            if note.entity_type == "account" and str(note.entity_id) == str(deal.account_id)
        )

    for note in note_candidates:
        if "Research Insights" not in note.body:
            continue
        return {
            "research_summary": _extract_note_line(note.body, "Summary:"),
            "outreach_angle": _extract_note_line(note.body, "Outreach Angle:"),
        }

    return {"research_summary": None, "outreach_angle": None}


def _extract_note_line(body: str, prefix: str) -> str | None:
    for line in body.splitlines():
        cleaned = line.strip().lstrip("* ").strip()
        if cleaned.startswith(prefix):
            return cleaned.replace(prefix, "", 1).strip() or None
    return None


def _normalize_nurture_draft(
    draft: DraftEmailResponse,
    *,
    deal: Deal,
    last_activity_at: datetime,
) -> DraftEmailResponse:
    company = deal.account.name if deal.account else "your team"
    fallback_subject = f"Quick follow-up on {deal.name}"
    subject = draft.subject.strip() or fallback_subject
    body = draft.body.strip()
    if "unsubscribe" not in body.lower():
        body = (
            f"{body}\n\n"
            "If this is not a priority right now, feel free to reply later or unsubscribe from future follow-ups."
        ).strip()
    if len(body) < 40:
        body = (
            f"Hi {deal.contact.first_name},\n\n"
            f"I wanted to follow up on our {deal.stage.name.lower()} conversation with {company}. "
            f"It has been a little while since our last update on {last_activity_at.date().isoformat()}, "
            "so I wanted to check whether this is still a priority.\n\n"
            "If this is not a priority right now, feel free to reply later or unsubscribe from future follow-ups."
        )
    return DraftEmailResponse(subject=subject, body=body, tone="professional")
