"""SMS API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthContext, get_auth_context
from app.core.db import get_db
from app.schemas.crm import SMSAssignContactRequest, SMSCreateTaskRequest, SMSMessageRead, SMSMessageSend
from app.services.sms import (
    assign_sms_contact,
    create_task_from_sms,
    handle_twilio_webhook,
    list_sms_history,
    mark_sms_read,
    queue_outbound_sms,
)


router = APIRouter(tags=["sms"])


@router.post("/sms/send", response_model=SMSMessageRead, status_code=status.HTTP_201_CREATED)
async def post_sms_send(
    payload: SMSMessageSend,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> SMSMessageRead:
    """Queue an outbound SMS send."""
    return await queue_outbound_sms(db, payload, team_id=auth.team_id, actor_id=auth.user_id)


@router.get("/sms/history", response_model=list[SMSMessageRead])
async def get_sms_history(
    direction: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[SMSMessageRead]:
    """Return SMS history for the current tenant."""
    return await list_sms_history(db, team_id=auth.team_id, direction=direction, limit=limit)


@router.post("/sms/{sms_id}/mark-read", response_model=SMSMessageRead)
async def post_sms_mark_read(
    sms_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> SMSMessageRead:
    """Mark a message as read."""
    return await mark_sms_read(db, sms_id, team_id=auth.team_id)


@router.post("/sms/{sms_id}/assign-contact", response_model=SMSMessageRead)
async def post_sms_assign_contact(
    sms_id: UUID,
    payload: SMSAssignContactRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> SMSMessageRead:
    """Assign a message to a contact."""
    return await assign_sms_contact(db, sms_id, payload, team_id=auth.team_id, actor_id=auth.user_id)


@router.post("/sms/{sms_id}/create-task")
async def post_sms_create_task(
    sms_id: UUID,
    payload: SMSCreateTaskRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> dict:
    """Create a follow-up task from an SMS."""
    return await create_task_from_sms(db, sms_id, payload, team_id=auth.team_id, actor_id=auth.user_id)


@router.post("/twilio/webhook")
async def post_twilio_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Receive inbound SMS from Twilio."""
    return await handle_twilio_webhook(request, db)
