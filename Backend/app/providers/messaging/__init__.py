# Acufy CRM — Messaging Providers (Twilio SMS, SendGrid Email)
"""Messaging provider exports."""

from app.providers.messaging.base import EmailProvider, EmailSendResult
from app.providers.messaging.factory import get_email_provider

__all__ = ["EmailProvider", "EmailSendResult", "get_email_provider"]
