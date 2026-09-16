"""Approval queue services for AI-generated drafts."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import logging
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.jobs import _get_worker_runtime_health, enqueue_background_job
from app.models import AgentApproval, EmailMessage
from app.events import emit_event
from app.providers.messaging import get_email_provider
from app.providers.messaging.base import EmailSendResult
from app.providers.messaging.stub import StubEmailProvider
from app.schemas.ai import AgentApprovalDecisionResponse, AgentApprovalListItem
from app.services.audit import log_audit
from app.services.notifications import create_notification
from app.services.sms_content import build_sms_from_email_content


logger = logging.getLogger("acufy.services.ai_approvals")

UNSUBSCRIBE_FOOTER = "\n\n---\nTo stop emails, click Unsubscribe: {unsubscribe_url}"
UNSUBSCRIBE_BASE_URL = "http://127.0.0.1:5173/unsubscribe"
STALE_SEND_TIMEOUT = timedelta(minutes=5)


def build_unsubscribe_token(*, team_id: UUID, contact_id: UUID) -> str:
    """Create a compact unsubscribe token for approval-bound outbound drafts."""
    raw = f"{team_id}:{contact_id}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def build_unsubscribe_url(*, team_id: UUID, contact_id: UUID) -> str:
    return f"{UNSUBSCRIBE_BASE_URL}?token={build_unsubscribe_token(team_id=team_id, contact_id=contact_id)}"


def append_unsubscribe_footer(body: str, *, team_id: UUID, contact_id: UUID) -> str:
    """Ensure every outbound draft has the required tokenized unsubscribe link."""
    cleaned = body.strip()
    if has_unsubscribe_link(cleaned):
        return cleaned
    footer = UNSUBSCRIBE_FOOTER.format(unsubscribe_url=build_unsubscribe_url(team_id=team_id, contact_id=contact_id))
    return f"{cleaned}{footer}"


def has_unsubscribe_link(body: str) -> bool:
    lowered = body.lower()
    return "unsubscribe" in lowered and "token=" in lowered and ("http://" in lowered or "https://" in lowered)


def _approval_query() -> Select[tuple[AgentApproval]]:
    return (
        select(AgentApproval)
        .options(
            selectinload(AgentApproval.contact),
            selectinload(AgentApproval.draft),
            selectinload(AgentApproval.deal),
        )
        .order_by(AgentApproval.created_at.desc())
    )


async def list_pending_approvals(db: AsyncSession, *, team_id: UUID) -> list[AgentApprovalListItem]:
    result = await db.execute(
        _approval_query().where(AgentApproval.status == "pending", AgentApproval.team_id == team_id)
    )
    return [_to_list_item(a) for a in result.scalars().all()]


async def list_approval_history(db: AsyncSession, *, team_id: UUID) -> list[AgentApprovalListItem]:
    await mark_stale_email_sends_failed(db, team_id=team_id)
    result = await db.execute(
        _approval_query().where(AgentApproval.status != "pending", AgentApproval.team_id == team_id)
    )
    return [_to_list_item(a) for a in result.scalars().all()]


async def approve_approval(
    db: AsyncSession,
    *,
    approval_id: UUID,
    team_id: UUID,
    actor_id: str | None = None,
    notes: str | None = None,
) -> AgentApprovalDecisionResponse:
    """Mark an approval as approved and send immediately. No compliance blocks after this point."""
    approval = await _load_approval_for_update(db, approval_id, team_id=team_id)

    # Snapshot relationship values NOW before any commit expires the ORM object
    contact_team_id = approval.contact.team_id
    approval_type = approval.type
    approval_deal_id = approval.deal_id

    # 1. Mark approved and queued before the worker sees it
    approval.status = "approved"
    approval.execution_status = "queued"
    approval.execution_detail = "Queued for email delivery."
    approval.decided_at = datetime.now(timezone.utc)
    approval.decision_notes = notes

    await log_audit(
        db,
        action="approval.approved",
        entity_type="agent_approval",
        entity_id=str(approval.id),
        actor_type="user",
        team_id=contact_team_id,
        actor_id=actor_id,
        metadata={
            "notes": notes,
            "type": approval_type,
            "deal_id": str(approval_deal_id) if approval_deal_id else None,
        },
    )

    # 2. COMMIT approved status BEFORE anything else so worker always sees it
    await db.commit()
    await db.refresh(approval)

    if approval_type == "email":
        worker_health = await _get_worker_runtime_health()
        worker_online = worker_health.get("workers") == "online"
        queue_result = await enqueue_background_job("send_email_job", str(approval.id), str(team_id), actor_id)
        if not queue_result.get("queued") or not worker_online:
            logger.info(
                "approval.approved - inline fallback approval_id=%s queued=%s worker_online=%s reason=%s",
                approval.id,
                queue_result.get("queued"),
                worker_online,
                queue_result.get("reason"),
            )
            await execute_email_approval(db, approval, actor_id=actor_id)
            from app.ai.graphs.crm_orchestration import resume_graph_after_approval

            await resume_graph_after_approval(
                db,
                approval_id=approval.id,
                team_id=team_id,
                actor_id=actor_id,
            )
            await db.commit()
            await db.refresh(approval)
        await emit_event(
            "approval.updated",
            {
                "approval_id": str(approval.id),
                "team_id": str(approval.team_id),
                "contact_id": str(approval.contact_id),
                "deal_id": str(approval.deal_id) if approval.deal_id else None,
                "status": approval.status,
                "execution_status": approval.execution_status,
            },
        )
        from app.services.automations import run_trigger
        await run_trigger(
            db,
            "approval.approved",
            {
                "id": str(approval.id),
                "type": approval_type,
                "deal_id": str(approval_deal_id) if approval_deal_id else None,
            },
            team_id,
        )
        return _to_decision_response(approval)
        logger.info(
            "approval.approved — executing email send inline approval_id=%s actor=%s",
            approval.id,
            actor_id,
        )
        # Always execute synchronously inline. This is the most reliable path.
        # The queue is only used as a fire-and-forget fallback for non-critical jobs.
        await execute_email_approval(db, approval, actor_id=actor_id)
        from app.ai.graphs.crm_orchestration import resume_graph_after_approval

        await resume_graph_after_approval(
            db,
            approval_id=approval.id,
            team_id=team_id,
            actor_id=actor_id,
        )
        await db.commit()
        await db.refresh(approval)
    else:
        # Non-email: decision already committed above
        pass

    await emit_event(
        "approval.updated",
        {
            "approval_id": str(approval.id),
            "team_id": str(approval.team_id),
            "contact_id": str(approval.contact_id),
            "deal_id": str(approval.deal_id) if approval.deal_id else None,
            "status": approval.status,
            "execution_status": approval.execution_status,
        },
    )

    from app.services.automations import run_trigger
    await run_trigger(
        db,
        "approval.approved",
        {
            "id": str(approval.id),
            "type": approval_type,
            "deal_id": str(approval_deal_id) if approval_deal_id else None,
        },
        team_id,
    )

    return _to_decision_response(approval)


async def execute_email_approval_by_id(
    db: AsyncSession,
    *,
    approval_id: UUID,
    team_id: UUID,
    actor_id: str | None = None,
) -> dict[str, str | bool | None]:
    """Execute a previously approved email approval by id (used by ARQ worker)."""
    result = await db.execute(
        _approval_query().where(AgentApproval.id == approval_id, AgentApproval.team_id == team_id)
    )
    approval = result.scalar_one_or_none()
    if approval is None:
        logger.error("execute_email_approval_by_id: approval not found id=%s", approval_id)
        return {"success": False, "reason": "approval_not_found"}
    if approval.status != "approved":
        logger.warning(
            "execute_email_approval_by_id: approval status=%s (not approved), skipping id=%s",
            approval.status,
            approval_id,
        )
        return {"success": False, "reason": f"approval_status_is_{approval.status}"}
    if approval.execution_status == "sent":
        logger.info("execute_email_approval_by_id: already sent id=%s", approval_id)
        return {"success": True, "reason": "already_sent", "message_id": approval.provider_message_id}
    if approval.type != "email":
        return {"success": False, "reason": "unsupported_approval_type"}

    await execute_email_approval(db, approval, actor_id=actor_id)
    from app.ai.graphs.crm_orchestration import resume_graph_after_approval

    await resume_graph_after_approval(
        db,
        approval_id=approval.id,
        team_id=team_id,
        actor_id=actor_id,
    )
    await db.flush()
    return {
        "success": approval.execution_status == "sent",
        "message_id": approval.provider_message_id,
        "status": approval.execution_status,
    }


async def execute_email_approval(
    db: AsyncSession,
    approval: AgentApproval,
    *,
    actor_id: str | None = None,
) -> None:
    """
    Send the approved email. No compliance blocking here — human approval is final authority.
    Recipient is ALWAYS forced to EMAIL_REDIRECT_TO when redirect is enabled.
    """
    settings = get_settings()
    approval.execution_status = "sending"
    approval.execution_detail = "Sending email through provider."
    await db.flush()

    contact_email = approval.contact.email
    subject = approval.draft.subject

    body = append_unsubscribe_footer(
        approval.draft.body,
        team_id=approval.team_id,
        contact_id=approval.contact_id,
    )

    # Determine recipient — redirect always wins in dev/redirect mode
    if settings.email_redirect_enabled and settings.email_redirect_to:
        to_email = settings.email_redirect_to.strip()
        redirect_detail = f"Redirected from {contact_email} to {to_email} (dev redirect active)."
        logger.info(
            "execute_email_approval: redirect active approval_id=%s original=%s target=%s",
            approval.id,
            contact_email,
            to_email,
        )
    elif contact_email:
        to_email = contact_email
        redirect_detail = ""
        logger.info(
            "execute_email_approval: sending to contact approval_id=%s to=%s",
            approval.id,
            to_email,
        )
    else:
        approval.execution_status = "failed"
        approval.execution_detail = "No recipient: contact has no email and redirect is disabled."
        logger.error("execute_email_approval: no recipient approval_id=%s", approval.id)
        return

    logger.info(
        "execute_email_approval: calling provider=%s to=%s subject=%s approval_id=%s",
        settings.email_provider,
        to_email,
        subject,
        approval.id,
    )

    try:
        result = await _send_approved_email(to_email=to_email, subject=subject, body=body)
    except Exception as exc:
        logger.exception("execute_email_approval: provider exception approval_id=%s", approval.id)
        approval.executed_at = datetime.now(timezone.utc)
        approval.execution_status = "failed"
        approval.execution_detail = f"Provider exception: {exc}"
        await log_audit(
            db,
            action="email.failed",
            entity_type="agent_approval",
            entity_id=str(approval.id),
            actor_type="system",
            actor_id=actor_id,
            team_id=approval.team_id,
            metadata={"deal_id": str(approval.deal_id) if approval.deal_id else None, "detail": str(exc)},
        )
        await emit_event(
            "approval.updated",
            {
                "approval_id": str(approval.id),
                "team_id": str(approval.team_id),
                "contact_id": str(approval.contact_id),
                "deal_id": str(approval.deal_id) if approval.deal_id else None,
                "status": approval.status,
                "execution_status": approval.execution_status,
            },
        )
        return

    approval.executed_at = datetime.now(timezone.utc)
    approval.execution_status = "sent" if result.success else "failed"
    approval.provider_message_id = result.message_id
    approval.execution_detail = " | ".join(
        p for p in [redirect_detail, result.detail] if p
    ).strip()

    if result.success:
        logger.info(
            "execute_email_approval: SUCCESS approval_id=%s provider=%s message_id=%s",
            approval.id,
            result.provider,
            result.message_id,
        )
    else:
        logger.error(
            "execute_email_approval: FAILED approval_id=%s provider=%s error=%s",
            approval.id,
            result.provider,
            result.detail,
        )

    email_msg = EmailMessage(
        team_id=approval.team_id,
        contact_id=approval.contact_id,
        deal_id=approval.deal_id,
        approval_id=approval.id,
        direction="outbound",
        recipient_email=to_email,
        subject=subject,
        body=body,
        provider_message_id=result.message_id,
        status="sent" if result.success else "failed",
        error_detail=result.detail if not result.success else None,
    )
    db.add(email_msg)

    if not result.success:
        contact_name = f"{approval.contact.first_name} {approval.contact.last_name}".strip()
        await create_notification(
            db,
            team_id=approval.team_id,
            type="email.failed",
            title="Email Send Failed",
            message=f"Email to {contact_name} ({to_email}) failed: {result.detail or 'Unknown error'}",
            entity_type="agent_approval",
            entity_id=str(approval.id),
        )

    await log_audit(
        db,
        action="email.executed" if result.success else "email.failed",
        entity_type="agent_approval",
        entity_id=str(approval.id),
        actor_type="system",
        actor_id=actor_id,
        team_id=approval.contact.team_id,
        metadata={
            "deal_id": str(approval.deal_id) if approval.deal_id else None,
            "provider_message_id": result.message_id,
            "provider": result.provider,
            "to_email": to_email,
            "detail": result.detail,
        },
    )

    await emit_event(
        "approval.updated",
        {
            "approval_id": str(approval.id),
            "team_id": str(approval.team_id),
            "contact_id": str(approval.contact_id),
            "deal_id": str(approval.deal_id) if approval.deal_id else None,
            "status": approval.status,
            "execution_status": approval.execution_status,
        },
    )


async def reject_approval(
    db: AsyncSession,
    *,
    approval_id: UUID,
    team_id: UUID,
    actor_id: str | None = None,
    notes: str | None = None,
) -> AgentApprovalDecisionResponse:
    """Mark an approval as rejected."""
    approval = await _load_approval_for_update(db, approval_id, team_id=team_id)
    approval.status = "rejected"
    approval.decided_at = datetime.now(timezone.utc)
    approval.decision_notes = notes
    await log_audit(
        db,
        action="approval.rejected",
        entity_type="agent_approval",
        entity_id=str(approval.id),
        actor_type="user",
        team_id=approval.contact.team_id,
        actor_id=actor_id,
        metadata={
            "notes": notes,
            "type": approval.type,
            "deal_id": str(approval.deal_id) if approval.deal_id else None,
        },
    )
    await db.commit()
    await db.refresh(approval)
    await emit_event(
        "approval.updated",
        {
            "approval_id": str(approval.id),
            "team_id": str(approval.team_id),
            "contact_id": str(approval.contact_id),
            "deal_id": str(approval.deal_id) if approval.deal_id else None,
            "status": approval.status,
            "execution_status": approval.execution_status,
        },
    )
    return _to_decision_response(approval)


async def retry_email_approval(
    db: AsyncSession,
    *,
    approval_id: UUID,
    team_id: UUID,
    actor_id: str | None = None,
) -> AgentApprovalDecisionResponse:
    """Retry an approved email that failed, was cancelled, or got stuck."""
    result = await db.execute(_approval_query().where(AgentApproval.id == approval_id, AgentApproval.team_id == team_id))
    approval = result.scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found.")
    if approval.status != "approved" or approval.type != "email":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only approved email approvals can be retried.")
    if approval.execution_status == "sent":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email has already been sent.")

    previous_detail = approval.execution_detail
    approval.execution_status = "queued"
    approval.execution_detail = "Retry queued for email delivery."
    approval.executed_at = None
    approval.provider_message_id = None
    await log_audit(
        db,
        action="email.retry_queued",
        entity_type="agent_approval",
        entity_id=str(approval.id),
        actor_type="user",
        actor_id=actor_id,
        team_id=team_id,
        metadata={"previous_detail": previous_detail},
    )
    await db.commit()

    worker_health = await _get_worker_runtime_health()
    worker_online = worker_health.get("workers") == "online"
    queue_result = await enqueue_background_job("send_email_job", str(approval.id), str(team_id), actor_id)
    if not queue_result.get("queued") or not worker_online:
        await execute_email_approval(db, approval, actor_id=actor_id)
        await db.commit()
    await db.refresh(approval)
    return _to_decision_response(approval)


async def cancel_email_approval_queue(
    db: AsyncSession,
    *,
    approval_id: UUID,
    team_id: UUID,
    actor_id: str | None = None,
) -> AgentApprovalDecisionResponse:
    """Cancel a queued/sending approval by marking delivery definitively cancelled."""
    result = await db.execute(_approval_query().where(AgentApproval.id == approval_id, AgentApproval.team_id == team_id))
    approval = result.scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found.")
    if approval.status != "approved" or approval.execution_status not in {"queued", "sending", None}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only queued or sending emails can be cancelled.")
    approval.execution_status = "cancelled"
    approval.executed_at = datetime.now(timezone.utc)
    approval.execution_detail = "Delivery cancelled by user before completion."
    await log_audit(
        db,
        action="email.queue_cancelled",
        entity_type="agent_approval",
        entity_id=str(approval.id),
        actor_type="user",
        actor_id=actor_id,
        team_id=team_id,
        metadata={"approval_id": str(approval.id)},
    )
    await db.commit()
    await db.refresh(approval)
    await emit_event(
        "approval.updated",
        {
            "approval_id": str(approval.id),
            "team_id": str(approval.team_id),
            "contact_id": str(approval.contact_id),
            "deal_id": str(approval.deal_id) if approval.deal_id else None,
            "status": approval.status,
            "execution_status": approval.execution_status,
        },
    )
    return _to_decision_response(approval)


async def mark_stale_email_sends_failed(db: AsyncSession, *, team_id: UUID) -> int:
    """Fail approved email sends that have been queued/sending for too long."""
    cutoff = datetime.now(timezone.utc) - STALE_SEND_TIMEOUT
    result = await db.execute(
        select(AgentApproval).where(
            AgentApproval.team_id == team_id,
            AgentApproval.status == "approved",
            AgentApproval.type == "email",
            or_(AgentApproval.execution_status.is_(None), AgentApproval.execution_status.in_(["queued", "sending"])),
            AgentApproval.decided_at < cutoff,
        )
    )
    approvals = list(result.scalars().all())
    for approval in approvals:
        approval.execution_status = "failed"
        approval.executed_at = datetime.now(timezone.utc)
        approval.execution_detail = "Timed out after 5 minutes without worker completion. Retry send is available."
        await log_audit(
            db,
            action="email.failed",
            entity_type="agent_approval",
            entity_id=str(approval.id),
            actor_type="system",
            team_id=team_id,
            metadata={"approval_id": str(approval.id), "reason": "send_timeout"},
        )
    if approvals:
        await db.commit()
    return len(approvals)


async def _load_approval_for_update(db: AsyncSession, approval_id: UUID, *, team_id: UUID) -> AgentApproval:
    result = await db.execute(
        _approval_query().where(AgentApproval.id == approval_id, AgentApproval.team_id == team_id)
    )
    approval = result.scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found.")
    if approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approval has already been decided (status={approval.status}).",
        )
    return approval


def _to_list_item(approval: AgentApproval) -> AgentApprovalListItem:
    contact_name = f"{approval.contact.first_name} {approval.contact.last_name}".strip()
    return AgentApprovalListItem(
        id=approval.id,
        type=approval.type,
        status=approval.status,
        contact_id=approval.contact_id,
        deal_id=approval.deal_id,
        draft_id=approval.draft_id,
        created_at=approval.created_at,
        decided_at=approval.decided_at,
        decision_notes=approval.decision_notes,
        executed_at=approval.executed_at,
        execution_status=approval.execution_status,
        provider_message_id=approval.provider_message_id,
        execution_detail=approval.execution_detail,
        contact_name=contact_name,
        subject=approval.draft.subject,
        body=approval.draft.body,
        sms_body=build_sms_from_email_content(
            subject=approval.draft.subject,
            body=approval.draft.body,
            contact_first_name=approval.contact.first_name,
        ) if approval.contact.phone else None,
    )


def _to_decision_response(approval: AgentApproval) -> AgentApprovalDecisionResponse:
    return AgentApprovalDecisionResponse(
        id=approval.id,
        status=approval.status,
        decided_at=approval.decided_at,
        decision_notes=approval.decision_notes,
        executed_at=approval.executed_at,
        execution_status=approval.execution_status,
        provider_message_id=approval.provider_message_id,
        execution_detail=approval.execution_detail,
    )


def check_email_compliance(
    *,
    consent_email: bool,
    to_email: str | None,
    subject: str,
    body: str,
) -> str | None:
    """Pre-approval compliance check — informational only, never blocks post-approval delivery."""
    if not consent_email:
        return "Contact does not have email consent."
    if not to_email:
        return "Contact is missing an email address."
    if not subject.strip():
        return "Draft subject is empty."
    if len(body.strip()) < 10:
        return "Draft body is too short for outbound email."
    if not has_unsubscribe_link(body):
        return "Missing unsubscribe link"
    return None


async def _send_approved_email(
    *,
    to_email: str,
    subject: str,
    body: str,
) -> EmailSendResult:
    settings = get_settings()
    provider_name = settings.email_provider.strip().lower()
    from_email = (settings.email_from or "onboarding@resend.dev").strip() or "onboarding@resend.dev"

    logger.info(
        "_send_approved_email: provider=%s from=%s to=%s",
        provider_name,
        from_email,
        to_email,
    )

    if provider_name == "resend":
        resend_api_key = (
            settings.resend_api_key.get_secret_value().strip()
            if settings.resend_api_key is not None
            else None
        )
        if resend_api_key:
            return await _send_via_resend(
                api_key=resend_api_key,
                from_email=from_email,
                to_email=to_email,
                subject=subject,
                body=body,
            )

        logger.error(
            "_send_approved_email: EMAIL_PROVIDER=resend but RESEND_API_KEY is missing or empty"
        )
        return EmailSendResult(
            success=False,
            message_id="",
            provider="resend",
            detail="RESEND_API_KEY is not configured.",
        )

    # Other providers
    provider = get_email_provider()
    return await provider.send_email(to_email=to_email, subject=subject, body=body)


async def _send_via_resend(
    *,
    api_key: str,
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
) -> EmailSendResult:
    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "html": body,
        "text": body,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    logger.info(
        "_send_via_resend: POST https://api.resend.com/emails from=%s to=%s subject=%s",
        from_email,
        to_email,
        subject,
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers=headers,
                json=payload,
            )
    except httpx.TimeoutException as exc:
        logger.error("_send_via_resend: TIMEOUT error=%s", exc)
        return EmailSendResult(success=False, message_id="", provider="resend", detail=f"Resend timeout: {exc}")
    except Exception as exc:
        logger.error("_send_via_resend: REQUEST EXCEPTION error=%s", exc)
        return EmailSendResult(success=False, message_id="", provider="resend", detail=f"Resend request failed: {exc}")

    logger.info("_send_via_resend: HTTP status=%s body=%s", response.status_code, response.text)

    if response.status_code >= 400:
        return EmailSendResult(
            success=False,
            message_id="",
            provider="resend",
            detail=f"Resend API error {response.status_code}: {response.text}",
        )

    data = response.json()
    message_id = str(data.get("id", ""))
    logger.info("_send_via_resend: SUCCESS message_id=%s", message_id)
    return EmailSendResult(
        success=True,
        message_id=message_id,
        provider="resend",
        detail=f"Delivered via Resend to {to_email}. Message ID: {message_id}",
    )
