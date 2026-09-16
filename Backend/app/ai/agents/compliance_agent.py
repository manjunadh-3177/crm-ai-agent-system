"""Compliance agent for pre-approval outbound checks."""

from __future__ import annotations

from app.models import Contact
from app.schemas.ai import DraftEmailResponse
from app.services.ai_approvals import check_email_compliance


def run_compliance_agent(*, contact: Contact | None, draft: DraftEmailResponse | None) -> tuple[bool, str | None]:
    """Run existing lightweight compliance checks before approval creation."""
    if contact is None:
        return False, "No linked contact found."
    if draft is None:
        return False, "No draft content available."

    reason = check_email_compliance(
        consent_email=contact.consent_email,
        to_email=contact.email,
        subject=draft.subject,
        body=draft.body,
    )
    return reason is None, reason
