"""Messaging provider abstractions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class EmailSendResult:
    """Normalized outbound email send result."""

    success: bool
    message_id: str
    provider: str
    detail: str


class EmailProvider(Protocol):
    """Protocol for outbound email delivery providers."""

    async def send_email(self, to_email: str, subject: str, body: str) -> EmailSendResult:
        """Send an email and return a normalized result."""
