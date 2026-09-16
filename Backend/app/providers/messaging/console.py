"""Console email provider for readable local output."""

from __future__ import annotations

from uuid import uuid4

from app.providers.messaging.base import EmailProvider, EmailSendResult


class ConsoleEmailProvider(EmailProvider):
    """Print a formatted email to stdout and return a fake success result."""

    async def send_email(self, to_email: str, subject: str, body: str) -> EmailSendResult:
        message_id = f"console-{uuid4()}"
        print("=" * 72)
        print("ACUFY CONSOLE EMAIL")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Message ID: {message_id}")
        print("-" * 72)
        print(body)
        print("=" * 72)
        return EmailSendResult(
            success=True,
            message_id=message_id,
            provider="console",
            detail="Email printed to console.",
        )
