"""Twilio-backed SMS service layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi import HTTPException, Request, Response, status
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.agents.lead_qualifier_agent import run_lead_qualifier
from app.ai.agents.proposal_agent import run_proposal_agent
from app.ai.agents.scheduler_agent import suggest_slots
from app.core.config import get_settings
from app.events import emit_event
from app.models import Contact, Deal, SMSMessage, Team
from app.schemas.crm import SMSAssignContactRequest, SMSCreateTaskRequest, SMSMessageSend, TaskCreate
from app.services.audit import log_audit
from app.services.notifications import create_notification
from app.services.sms_content import build_sms_from_email_content
from app.services.tasks import create_task


TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"
STOP_WORDS = {"stop", "unsubscribe", "cancel", "end", "quit", "stopall"}


@dataclass(slots=True)
class TwilioSendResult:
    success: bool
    provider_sid: str | None = None
    error_detail: str | None = None


def _detail_options():
    return (selectinload(SMSMessage.contact),)


def normalize_phone(value: str | None) -> str:
    if not value:
        return ""
    raw = value.strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return raw
    if raw.startswith("+"):
        return f"+{digits}"
    if len(digits) == 10:
        return f"+1{digits}"
    return f"+{digits}"


def build_thread_id(*, team_id: UUID, local_number: str, remote_number: str) -> str:
    return f"{team_id}:{normalize_phone(remote_number)}:{normalize_phone(local_number)}"


def peer_number(message: SMSMessage) -> str:
    return message.to_number if message.direction == "outbound" else message.from_number


async def list_sms_history(
    db: AsyncSession,
    *,
    team_id: UUID,
    direction: str | None = None,
    limit: int = 100,
) -> list[SMSMessage]:
    query = select(SMSMessage).options(*_detail_options()).where(SMSMessage.team_id == team_id)
    if direction:
        query = query.where(SMSMessage.direction == direction)
    result = await db.execute(query.order_by(desc(SMSMessage.created_at)).limit(limit))
    return list(result.scalars().all())


async def queue_outbound_sms(
    db: AsyncSession,
    payload: SMSMessageSend,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> SMSMessage:
    settings = get_settings()
    from_number = normalize_phone(settings.twilio_phone_number)
    to_number = normalize_phone(payload.to_number)
    redirect_to_number = normalize_phone(settings.twilio_default_to)
    sms_redirect_active = bool(redirect_to_number and redirect_to_number != to_number)
    if not from_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Twilio configuration incomplete. Missing: TWILIO_PHONE_NUMBER.",
        )
    missing_config = get_missing_twilio_config()
    if missing_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Twilio configuration incomplete. Missing: {', '.join(missing_config)}.",
        )
    if not to_number:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Destination number is required.")

    contact = await _resolve_outbound_contact(db, team_id=team_id, contact_id=payload.contact_id, to_number=to_number)
    if contact is not None and not contact.consent_sms and not sms_redirect_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This contact has opted out of SMS outreach.")

    message = SMSMessage(
        team_id=team_id,
        contact_id=contact.id if contact else None,
        direction="outbound",
        thread_id=build_thread_id(team_id=team_id, local_number=from_number, remote_number=to_number),
        from_number=from_number,
        to_number=to_number,
        body=payload.body.strip(),
        status="Queued",
        is_read=True,
    )
    db.add(message)
    await db.flush()
    await log_audit(
        db,
        action="sms.queued",
        entity_type="sms_message",
        entity_id=str(message.id),
        actor_type="user",
        actor_id=actor_id,
        team_id=team_id,
        metadata={"to_number": to_number, "contact_id": str(contact.id) if contact else None},
    )
    await db.commit()
    await db.refresh(message)
    message = await execute_sms_send_by_id(db, sms_id=message.id, team_id=team_id, actor_id=actor_id)
    await emit_event("sms.updated", {"sms_id": str(message.id), "team_id": str(team_id)})
    return message


async def execute_sms_send_by_id(
    db: AsyncSession,
    *,
    sms_id: UUID,
    team_id: UUID,
    actor_id: str | None = None,
) -> SMSMessage:
    message = await _get_sms_or_404(db, sms_id, team_id=team_id)
    result = await _send_via_twilio(to_number=message.to_number, body=message.body, from_number=message.from_number)
    message.provider_sid = result.provider_sid
    message.error_detail = result.error_detail
    message.sent_at = datetime.now(UTC) if result.success else None
    message.status = "Sent" if result.success else "Failed"
    await log_audit(
        db,
        action="sms.sent" if result.success else "sms.failed",
        entity_type="sms_message",
        entity_id=str(message.id),
        actor_type="system",
        actor_id=actor_id,
        team_id=team_id,
        metadata={"provider_sid": result.provider_sid, "error_detail": result.error_detail},
    )
    await db.commit()
    await db.refresh(message)
    await emit_event("sms.updated", {"sms_id": str(message.id), "team_id": str(team_id)})
    return message


async def mark_sms_read(db: AsyncSession, sms_id: UUID, *, team_id: UUID) -> SMSMessage:
    message = await _get_sms_or_404(db, sms_id, team_id=team_id)
    message.is_read = True
    message.read_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(message)
    await emit_event("sms.updated", {"sms_id": str(message.id), "team_id": str(team_id)})
    return message


async def assign_sms_contact(
    db: AsyncSession,
    sms_id: UUID,
    payload: SMSAssignContactRequest,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> SMSMessage:
    message = await _get_sms_or_404(db, sms_id, team_id=team_id)
    contact = await db.get(Contact, payload.contact_id)
    if contact is None or contact.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found.")
    message.contact_id = contact.id
    await log_audit(
        db,
        action="sms.contact_assigned",
        entity_type="sms_message",
        entity_id=str(message.id),
        actor_type="user",
        actor_id=actor_id,
        team_id=team_id,
        metadata={"contact_id": str(contact.id)},
    )
    await db.commit()
    await db.refresh(message)
    await emit_event("sms.updated", {"sms_id": str(message.id), "team_id": str(team_id)})
    return message


async def create_task_from_sms(
    db: AsyncSession,
    sms_id: UUID,
    payload: SMSCreateTaskRequest,
    *,
    team_id: UUID,
    actor_id: str | None = None,
) -> dict[str, str]:
    message = await _get_sms_or_404(db, sms_id, team_id=team_id)
    title = (payload.title or "").strip() or f"Follow up on SMS from {peer_number(message)}"
    task = await create_task(
        db,
        TaskCreate(
            title=title,
            description=message.body,
            due_at=None,
            priority="med",
            status="open",
            contact_id=message.contact_id,
            deal_id=None,
            account_id=None,
            assigned_user_id=None,
        ),
        team_id=team_id,
        actor_id=actor_id,
    )
    await log_audit(
        db,
        action="sms.task_created",
        entity_type="sms_message",
        entity_id=str(message.id),
        actor_type="user",
        actor_id=actor_id,
        team_id=team_id,
        metadata={"task_id": str(task.id)},
    )
    await db.commit()
    return {"status": "created", "task_id": str(task.id)}


async def handle_twilio_webhook(request: Request, db: AsyncSession) -> Response:
    form = await request.form()
    from_number = normalize_phone(str(form.get("From", "")))
    to_number = normalize_phone(str(form.get("To", "")))
    body = str(form.get("Body", "")).strip()
    provider_sid = str(form.get("MessageSid", "")).strip() or None
    if not from_number or not to_number:
        return Response(content="<Response></Response>", media_type="application/xml")

    team = await _resolve_inbound_team(db, from_number=from_number, to_number=to_number)
    if team is None:
        return Response(content="<Response></Response>", media_type="application/xml")

    contact = await _find_contact_by_phone(db, team_id=team.id, phone_number=from_number)
    message = SMSMessage(
        team_id=team.id,
        contact_id=contact.id if contact else None,
        direction="inbound",
        thread_id=build_thread_id(team_id=team.id, local_number=to_number, remote_number=from_number),
        from_number=from_number,
        to_number=to_number,
        body=body or "(empty SMS)",
        status="Received",
        provider_sid=provider_sid,
        received_at=datetime.now(UTC),
        is_read=False,
    )
    db.add(message)
    await db.flush()
    message.agent_suggestion = await _apply_inbound_automation(db, message=message, contact=contact, team_id=team.id)
    await log_audit(
        db,
        action="sms.inbound.received",
        entity_type="sms_message",
        entity_id=str(message.id),
        actor_type="system",
        team_id=team.id,
        metadata={
            "from_number": from_number,
            "to_number": to_number,
            "contact_id": str(contact.id) if contact else None,
            "agent_suggestion": message.agent_suggestion,
        },
    )
    await create_notification(
        db,
        team_id=team.id,
        type="sms.inbound",
        title="New SMS Reply",
        message=f"{from_number}: {(body or '(empty SMS)')[:120]}",
        entity_type="sms_message",
        entity_id=str(message.id),
    )
    await db.commit()
    await emit_event("sms.received", {"sms_id": str(message.id), "team_id": str(team.id)})
    return Response(content="<Response></Response>", media_type="application/xml")


async def configure_twilio_webhook() -> dict[str, str]:
    settings = get_settings()
    account_sid = settings.twilio_account_sid.get_secret_value() if settings.twilio_account_sid else ""
    auth_token = settings.twilio_auth_token.get_secret_value() if settings.twilio_auth_token else ""
    phone_number = normalize_phone(settings.twilio_phone_number)
    if not account_sid or not auth_token or not phone_number:
        return {"status": "skipped", "reason": "missing_twilio_credentials"}

    async with httpx.AsyncClient(timeout=15.0, auth=(account_sid, auth_token)) as client:
        lookup = await client.get(
            f"{TWILIO_API_BASE}/Accounts/{account_sid}/IncomingPhoneNumbers.json",
            params={"PhoneNumber": phone_number},
        )
        lookup.raise_for_status()
        incoming_numbers = lookup.json().get("incoming_phone_numbers") or []
        if not incoming_numbers:
            return {"status": "error", "reason": "phone_number_not_found"}
        phone_sid = incoming_numbers[0]["sid"]
        update = await client.post(
            f"{TWILIO_API_BASE}/Accounts/{account_sid}/IncomingPhoneNumbers/{phone_sid}.json",
            data={"SmsUrl": settings.twilio_inbound_webhook_url, "SmsMethod": "POST"},
        )
        update.raise_for_status()
        return {"status": "configured", "phone_sid": phone_sid, "webhook_url": settings.twilio_inbound_webhook_url}


async def _send_via_twilio(*, to_number: str, body: str, from_number: str) -> TwilioSendResult:
    settings = get_settings()
    account_sid = _secret_value(settings.twilio_account_sid)
    auth_token = _secret_value(settings.twilio_auth_token)
    redirect_to_number = normalize_phone(settings.twilio_default_to)
    provider_to_number = redirect_to_number or normalize_phone(to_number)
    missing_config = get_missing_twilio_config()
    if missing_config:
        return TwilioSendResult(
            success=False,
            error_detail=f"Twilio configuration incomplete. Missing: {', '.join(missing_config)}.",
        )
    async with httpx.AsyncClient(timeout=20.0, auth=(account_sid, auth_token)) as client:
        response = await client.post(
            f"{TWILIO_API_BASE}/Accounts/{account_sid}/Messages.json",
            data={"To": provider_to_number, "From": normalize_phone(from_number), "Body": body},
        )
    if response.is_success:
        data = response.json()
        return TwilioSendResult(success=True, provider_sid=data.get("sid"))
    detail = response.text
    try:
        detail = response.json().get("message") or detail
    except Exception:
        pass
    return TwilioSendResult(success=False, error_detail=detail[:500])


def get_missing_twilio_config() -> list[str]:
    settings = get_settings()
    missing: list[str] = []
    if not normalize_phone(settings.twilio_phone_number):
        missing.append("TWILIO_PHONE_NUMBER")
    if not _secret_value(settings.twilio_account_sid):
        missing.append("TWILIO_ACCOUNT_SID")
    if not _secret_value(settings.twilio_auth_token):
        missing.append("TWILIO_AUTH_TOKEN")
    return missing


def _secret_value(secret: object | None) -> str:
    if secret is None:
        return ""
    getter = getattr(secret, "get_secret_value", None)
    if callable(getter):
        return str(getter() or "").strip()
    return str(secret or "").strip()


async def _resolve_outbound_contact(
    db: AsyncSession,
    *,
    team_id: UUID,
    contact_id: UUID | None,
    to_number: str,
) -> Contact | None:
    if contact_id is not None:
        contact = await db.get(Contact, contact_id)
        if contact is None or contact.team_id != team_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found.")
        return contact
    return await _find_contact_by_phone(db, team_id=team_id, phone_number=to_number)


async def _find_contact_by_phone(db: AsyncSession, *, team_id: UUID, phone_number: str) -> Contact | None:
    result = await db.execute(select(Contact).where(Contact.team_id == team_id))
    target = normalize_phone(phone_number)
    for contact in result.scalars().all():
        if normalize_phone(contact.phone) == target:
            return contact
    return None


async def _resolve_inbound_team(db: AsyncSession, *, from_number: str, to_number: str) -> Team | None:
    result = await db.execute(select(Contact).where(Contact.phone.is_not(None)))
    for contact in result.scalars().all():
        if normalize_phone(contact.phone) == from_number:
            return await db.get(Team, contact.team_id)

    result = await db.execute(
        select(SMSMessage)
        .where(
            or_(
                (SMSMessage.from_number == from_number) & (SMSMessage.to_number == to_number),
                (SMSMessage.from_number == to_number) & (SMSMessage.to_number == from_number),
            )
        )
        .order_by(desc(SMSMessage.created_at))
        .limit(1)
    )
    prior = result.scalar_one_or_none()
    if prior is not None:
        return await db.get(Team, prior.team_id)

    result = await db.execute(select(Team).order_by(Team.created_at).limit(1))
    return result.scalar_one_or_none()


async def _get_sms_or_404(db: AsyncSession, sms_id: UUID, *, team_id: UUID) -> SMSMessage:
    result = await db.execute(
        select(SMSMessage).options(*_detail_options()).where(SMSMessage.id == sms_id, SMSMessage.team_id == team_id)
    )
    message = result.scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SMS message not found.")
    return message


async def _apply_inbound_automation(
    db: AsyncSession,
    *,
    message: SMSMessage,
    contact: Contact | None,
    team_id: UUID,
) -> str:
    body_lower = message.body.lower()
    if any(word in body_lower for word in STOP_WORDS):
        if contact is not None:
            contact.consent_sms = False
        await log_audit(
            db,
            action="agent.compliance.sms_opt_out",
            entity_type="sms_message",
            entity_id=str(message.id),
            actor_type="ai",
            team_id=team_id,
            metadata={"contact_id": str(contact.id) if contact else None},
        )
        return "ComplianceAgent marked this contact as opted out from future SMS outreach."

    if "interest" in body_lower or "interested" in body_lower:
        if contact is not None:
            await run_lead_qualifier(db, contact.id, team_id)
            return f"LeadQualifierAgent rescored {contact.first_name} {contact.last_name} after inbound interest."
        return "LeadQualifierAgent will run after this SMS is assigned to a contact."

    if any(keyword in body_lower for keyword in ("meeting", "schedule", "call", "demo")):
        if contact is not None:
            result = await suggest_slots(
                db,
                team_id=team_id,
                contact_id=contact.id,
                duration_minutes=30,
                timezone_name=contact.preferred_timezone or "UTC",
            )
            return str(result.get("message") or "SchedulerAgent found mutual slots.")
        return "SchedulerAgent can suggest slots after this SMS is assigned to a contact."

    if any(keyword in body_lower for keyword in ("price", "pricing", "quote", "cost", "proposal")):
        if contact is not None:
            deal = await _find_latest_open_deal_for_contact(db, team_id=team_id, contact_id=contact.id)
            if deal is not None:
                draft = await run_proposal_agent(
                    db,
                    deal_id=deal.id,
                    team_id=team_id,
                    actor_id="ai",
                    trigger="sms.inbound",
                    force=True,
                )
                if draft is not None:
                    return f"ProposalAgent prepared pricing content for deal {deal.name}."
            return "ProposalAgent needs an active deal before pricing can be generated."
        return "ProposalAgent can assist after this SMS is assigned to a contact with an active deal."

    return "No automation triggered. Review and reply from the Messages inbox."


async def _find_latest_open_deal_for_contact(db: AsyncSession, *, team_id: UUID, contact_id: UUID) -> Deal | None:
    result = await db.execute(
        select(Deal).where(Deal.team_id == team_id, Deal.contact_id == contact_id).order_by(desc(Deal.updated_at))
    )
    return result.scalars().first()
