"""Stub email provider for safe local development."""

from __future__ import annotations

import logging
from uuid import uuid4

from app.providers.messaging.base import EmailProvider, EmailSendResult


logger = logging.getLogger("acufy.providers.email.stub")


class StubEmailProvider(EmailProvider):
    """No-op provider that logs sends and returns fake success."""

    async def send_email(self, to_email: str, subject: str, body: str) -> EmailSendResult:
        message_id = f"stub-{uuid4()}"
        logger.info(
            "STUB EMAIL send to=%s subject=%s message_id=%s body_preview=%s",
            to_email,
            subject,
            message_id,
            body[:120].replace("\n", " "),
        )
        return EmailSendResult(
            success=True,
            message_id=message_id,
            provider="stub",
            detail="Email send simulated in stub mode.",
        )
