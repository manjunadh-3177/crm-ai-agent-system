"""AI email drafting service using real CRM data."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.agents.compliance_agent import run_compliance_agent
from app.ai.llm import chat, start_trace_scope
from app.events import emit_event
from app.models import Account, AgentApproval, Contact, EmailDraft
from app.schemas.ai import DraftEmailResponse, DraftEmailUpdateRequest
from app.services.ai_approvals import append_unsubscribe_footer
from app.services.ai_summary import (
    build_contact_context,
    load_contact_deal_context,
    parse_json_response,
)
from app.services.audit import log_audit
from app.services.notifications import create_notification

AUTO_CONTACT_DRAFT_WINDOW_HOURS = 24


async def generate_email_draft(
    db: AsyncSession,
    *,
    contact_id: UUID,
    team_id: UUID,
    deal_id: UUID | None = None,
) -> DraftEmailResponse:
    """Generate and store an email draft from CRM records."""
    response, _, _ = await create_email_draft(
        db,
        contact_id=contact_id,
        team_id=team_id,
        deal_id=deal_id,
    )
    return response


async def create_email_draft(
    db: AsyncSession,
    *,
    contact_id: UUID,
    team_id: UUID,
    deal_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[DraftEmailResponse, EmailDraft, AgentApproval]:
    """Generate and store an email draft plus pending approval."""
    response = await generate_email_draft_content(
        db,
        contact_id=contact_id,
        team_id=team_id,
        deal_id=deal_id,
        metadata=metadata,
    )
    contact, _, current_deal = await load_contact_deal_context(
        db,
        contact_id=contact_id,
        team_id=team_id,
        deal_id=deal_id,
    )
    draft, approval = await persist_draft_and_approval(
        db,
        contact_id=contact.id,
        team_id=contact.team_id,
        deal_id=current_deal.id if current_deal else None,
        response=response,
    )
    await db.commit()
    await emit_event(
        "approval.created",
        {
            "approval_id": str(approval.id),
            "team_id": str(approval.team_id),
            "contact_id": str(approval.contact_id),
            "deal_id": str(approval.deal_id) if approval.deal_id else None,
            "subject": response.subject,
            "type": approval.type,
            "status": approval.status,
        },
    )

    return response, draft, approval


async def generate_email_draft_content(
    db: AsyncSession,
    *,
    contact_id: UUID,
    team_id: UUID,
    deal_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
    strategy_context: dict[str, Any] | None = None,
) -> DraftEmailResponse:
    """Generate normalized email draft content without persisting."""
    trace_scope = start_trace_scope(
        "email_draft",
        metadata={
            "team_id": str(team_id),
            "contact_id": str(contact_id),
            "deal_id": str(deal_id) if deal_id else None,
            **(metadata or {}),
        },
        input_payload={"contact_id": str(contact_id), "deal_id": str(deal_id) if deal_id else None},
    )
    contact, related_deals, current_deal = await load_contact_deal_context(
        db,
        contact_id=contact_id,
        team_id=team_id,
        deal_id=deal_id,
    )

    crm_context = build_contact_context(contact, related_deals, current_deal)
    prompt = _build_draft_email_prompt(crm_context, strategy_context=strategy_context)

    try:
        raw_text = await chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional sales assistant. "
                        "CRITICAL: You must respond ONLY with a valid JSON object. "
                        "Do not include any conversational text, markdown formatting (except JSON block), or thoughts. "
                        "Required JSON structure: "
                        '{"subject": "string", "body": "string", "tone": "professional"}'
                    ),
                },
                {"role": "user", "content": f"{prompt}\n\nRemember: Return ONLY the JSON object."},
            ],
            purpose="email_draft",
            temperature=0.1,
            metadata={
                "route": "/ai/draft-email",
                "team_id": str(team_id),
                "contact_id": str(contact.id),
                "deal_id": str(current_deal.id) if current_deal else None,
                **(metadata or {}),
            },
        )

        response = parse_json_response(raw_text, DraftEmailResponse)
        if response.tone != "professional":
            response = DraftEmailResponse(
                subject=response.subject,
                body=response.body,
                tone="professional",
            )
        response = DraftEmailResponse(
            subject=response.subject,
            body=append_unsubscribe_footer(response.body, team_id=team_id, contact_id=contact.id),
            tone=response.tone,
        )
        trace_scope.finish(output=response.model_dump(mode="json"), status_message="success")
        return response
    except Exception as exc:
        trace_scope.finish(output={"error": str(exc)}, status_message="failure")
        raise


async def persist_draft_and_approval(
    db: AsyncSession,
    *,
    contact_id: UUID,
    team_id: UUID,
    response: DraftEmailResponse,
    deal_id: UUID | None = None,
) -> tuple[EmailDraft, AgentApproval]:
    """Persist an email draft and its pending approval."""
    compliant_response = DraftEmailResponse(
        subject=response.subject.strip(),
        body=append_unsubscribe_footer(response.body, team_id=team_id, contact_id=contact_id),
        tone=response.tone,
    )
    contact = await db.get(Contact, contact_id)
    if contact is None or contact.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found.")
    passed, reason = run_compliance_agent(contact=contact, draft=compliant_response)
    if not passed:
        await log_audit(
            db,
            action="agent.compliance.blocked",
            entity_type="contact",
            entity_id=str(contact_id),
            actor_type="ai",
            team_id=team_id,
            metadata={"reason": reason, "subject": compliant_response.subject},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason or "Compliance blocked draft.")
    draft = EmailDraft(
        team_id=team_id,
        contact_id=contact_id,
        deal_id=deal_id,
        subject=compliant_response.subject,
        body=compliant_response.body,
    )
    db.add(draft)
    await db.flush()
    await log_audit(
        db,
        action="draft.created",
        entity_type="email_draft",
        entity_id=str(draft.id),
        actor_type="ai",
        team_id=team_id,
        metadata={
            "contact_id": str(contact_id),
            "deal_id": str(deal_id) if deal_id else None,
            "subject": compliant_response.subject,
        },
    )

    approval = AgentApproval(
        type="email",
        team_id=team_id,
        contact_id=contact_id,
        deal_id=deal_id,
        draft_id=draft.id,
        status="pending",
    )
    db.add(approval)
    await db.flush()
    await log_audit(
        db,
        action="approval.created",
        entity_type="agent_approval",
        entity_id=str(approval.id),
        actor_type="ai",
        team_id=team_id,
        metadata={
            "contact_id": str(contact_id),
            "deal_id": str(deal_id) if deal_id else None,
            "draft_id": str(draft.id),
            "type": "email",
        },
    )

    # Generate notification
    await create_notification(
        db,
        team_id=team_id,
        type="approval.pending",
        title="New Approval Required",
        message=f"A new {approval.type} draft is pending your approval.",
        entity_type="agent_approval",
        entity_id=str(approval.id),
    )

    return draft, approval


async def update_email_draft_for_approval(
    db: AsyncSession,
    *,
    approval_id: UUID,
    team_id: UUID,
    payload: DraftEmailUpdateRequest,
    actor_id: str | None = None,
) -> DraftEmailResponse:
    """Update an existing pending approval draft."""
    approval = await db.get(AgentApproval, approval_id)
    if approval is None or approval.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found.")
    if approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending approval drafts can be edited.",
        )

    draft = await db.get(EmailDraft, approval.draft_id)
    if draft is None or draft.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found.")

    draft.subject = payload.subject.strip()
    draft.body = append_unsubscribe_footer(payload.body, team_id=team_id, contact_id=approval.contact_id)
    await log_audit(
        db,
        action="draft.updated",
        entity_type="email_draft",
        entity_id=str(draft.id),
        actor_type="user",
        team_id=team_id,
        actor_id=actor_id,
        metadata={"approval_id": str(approval.id)},
    )
    await db.commit()
    await db.refresh(draft)
    return DraftEmailResponse(subject=draft.subject, body=draft.body, tone="professional")


async def create_auto_contact_draft(
    db: AsyncSession,
    *,
    contact_id: UUID,
    team_id: UUID,
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Create a welcome/outreach approval for a new contact."""
    duplicate = await _find_recent_contact_draft(db, contact_id=contact_id, team_id=team_id)
    if duplicate is not None:
        return {"status": "skipped", "reason": "recent_draft_exists", "approval_id": str(duplicate.id)}

    contact = await db.get(Contact, contact_id)
    if contact is None or contact.team_id != team_id:
        return {"status": "skipped", "reason": "contact_not_found"}

    account: Account | None = None
    if contact.account_id:
        maybe_account = await db.get(Account, contact.account_id)
        if maybe_account is not None and maybe_account.team_id == team_id:
            account = maybe_account

    strategy_context = {
        "mode": "new_contact_welcome",
        "contact_name": f"{contact.first_name} {contact.last_name}".strip(),
        "company_name": account.name if account else None,
        "contact_email": contact.email,
        "goal": "Introduce the team, acknowledge the new contact, and invite a light next step.",
    }

    try:
        response = await generate_email_draft_content(
            db,
            contact_id=contact_id,
            team_id=team_id,
            metadata={
                "route": "auto_contact_draft",
                "team_id": str(team_id),
                "contact_id": str(contact_id),
                "user_id": actor_id,
            },
            strategy_context=strategy_context,
        )
    except Exception:
        response = _build_auto_contact_fallback(contact=contact, account=account)

    draft, approval = await persist_draft_and_approval(
        db,
        contact_id=contact_id,
        team_id=team_id,
        deal_id=None,
        response=_normalize_auto_contact_draft(response, contact=contact, account=account),
    )
    await log_audit(
        db,
        action="agent.auto_contact_draft_created",
        entity_type="contact",
        entity_id=str(contact_id),
        actor_type="ai",
        actor_id=actor_id,
        team_id=team_id,
        metadata={
            "approval_id": str(approval.id),
            "draft_id": str(draft.id),
            "contact_id": str(contact_id),
            "account_id": str(account.id) if account else None,
        },
    )
    await db.commit()
    await emit_event(
        "approval.created",
        {
            "approval_id": str(approval.id),
            "team_id": str(approval.team_id),
            "contact_id": str(approval.contact_id),
            "deal_id": None,
            "subject": draft.subject,
            "type": approval.type,
            "status": approval.status,
        },
    )
    return {"status": "created", "approval_id": str(approval.id)}


def _build_draft_email_prompt(
    context: dict,
    *,
    strategy_context: dict[str, Any] | None = None,
) -> str:
    """Build a concise deterministic prompt for email drafting."""
    return _build_draft_email_prompt_with_strategy(context, strategy_context=strategy_context)


async def _find_recent_contact_draft(
    db: AsyncSession,
    *,
    contact_id: UUID,
    team_id: UUID,
) -> AgentApproval | None:
    cutoff = datetime.now(UTC) - timedelta(hours=AUTO_CONTACT_DRAFT_WINDOW_HOURS)
    result = await db.execute(
        select(AgentApproval)
        .options(selectinload(AgentApproval.draft))
        .where(
            AgentApproval.team_id == team_id,
            AgentApproval.contact_id == contact_id,
            AgentApproval.type == "email",
            AgentApproval.created_at >= cutoff,
        )
        .order_by(AgentApproval.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _build_auto_contact_fallback(*, contact: Contact, account: Account | None) -> DraftEmailResponse:
    contact_name = f"{contact.first_name} {contact.last_name}".strip()
    company_name = account.name if account else "your team"
    first_name = contact.first_name.strip() or contact_name or "there"
    return DraftEmailResponse(
        subject="Great to connect",
        body=(
            f"Hi {first_name},\n\n"
            f"Great to connect. I wanted to introduce myself and say welcome from the Acufy CRM team"
            f"{f' working with {company_name}' if account else ''}.\n\n"
            "If helpful, I’d be glad to share a quick introduction and answer any questions about next steps.\n\n"
            "If you’d prefer not to receive future emails, reply with unsubscribe."
        ),
        tone="professional",
    )


def _normalize_auto_contact_draft(
    response: DraftEmailResponse,
    *,
    contact: Contact,
    account: Account | None,
) -> DraftEmailResponse:
    subject = response.subject.strip() or "Welcome to Acufy"
    body = response.body.strip()
    if "unsubscribe" not in body.lower():
        body = (
            f"{body}\n\n"
            "If you’d prefer not to receive future emails, reply with unsubscribe."
        ).strip()
    if len(body) < 60:
        return _build_auto_contact_fallback(contact=contact, account=account)
    return DraftEmailResponse(subject=subject, body=body, tone="professional")


def _build_draft_email_prompt_with_strategy(
    context: dict,
    *,
    strategy_context: dict[str, Any] | None,
) -> str:
    guidance_block = ""
    if strategy_context:
        guidance_block = f"\nAdditional guidance:\n{json.dumps(strategy_context, indent=2)}\n"

    return (
        "Using this CRM data, draft a short follow-up email.\n"
        "Requirements:\n"
        "- Tone must be professional\n"
        "- Subject should be concise\n"
        "- Body should be 1 short greeting, 2-3 short body paragraphs, and one clear next step\n"
        "- Keep it under 180 words\n"
        "- Output MUST be a valid JSON object with keys: subject, body, tone\n"
        f"{guidance_block}\n"
        f"CRM data:\n{json.dumps(context, indent=2)}\n\n"
        "JSON Response:"
    )
