"""Factory for selecting the configured email provider."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.providers.messaging.base import EmailProvider
from app.providers.messaging.console import ConsoleEmailProvider
from app.providers.messaging.stub import StubEmailProvider


def get_email_provider() -> EmailProvider:
    """Return the configured email provider implementation."""
    settings = get_settings()
    provider_name = settings.email_provider.lower()

    if provider_name == "stub":
        return StubEmailProvider()
    if provider_name == "console":
        return ConsoleEmailProvider()

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Unsupported EMAIL_PROVIDER: {settings.email_provider}",
    )
