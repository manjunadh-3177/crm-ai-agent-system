"""Tests for pre-send compliance checks on AI-generated email drafts."""

from app.ai.agents.compliance_agent import run_compliance_agent
from app.schemas.ai import DraftEmailResponse
from app.services.ai_approvals import (
    append_unsubscribe_footer,
    build_unsubscribe_url,
    check_email_compliance,
    has_unsubscribe_link,
)


VALID_BODY_WITH_LINK = (
    "Hi there, following up on our conversation.\n\n"
    "---\nTo stop emails, click Unsubscribe: http://127.0.0.1:5173/unsubscribe?token=abc123"
)


def test_check_email_compliance_blocks_missing_consent() -> None:
    reason = check_email_compliance(
        consent_email=False,
        to_email="lead@example.com",
        subject="Hello",
        body=VALID_BODY_WITH_LINK,
    )
    assert reason == "Contact does not have email consent."


def test_check_email_compliance_blocks_missing_email() -> None:
    reason = check_email_compliance(
        consent_email=True,
        to_email=None,
        subject="Hello",
        body=VALID_BODY_WITH_LINK,
    )
    assert reason == "Contact is missing an email address."


def test_check_email_compliance_blocks_empty_subject() -> None:
    reason = check_email_compliance(
        consent_email=True,
        to_email="lead@example.com",
        subject="   ",
        body=VALID_BODY_WITH_LINK,
    )
    assert reason == "Draft subject is empty."


def test_check_email_compliance_blocks_short_body() -> None:
    reason = check_email_compliance(
        consent_email=True,
        to_email="lead@example.com",
        subject="Hello",
        body="Hi",
    )
    assert reason == "Draft body is too short for outbound email."


def test_check_email_compliance_blocks_missing_unsubscribe_link() -> None:
    reason = check_email_compliance(
        consent_email=True,
        to_email="lead@example.com",
        subject="Hello",
        body="This is a long enough body but has no unsubscribe link at all.",
    )
    assert reason == "Missing unsubscribe link"


def test_check_email_compliance_passes_valid_draft() -> None:
    reason = check_email_compliance(
        consent_email=True,
        to_email="lead@example.com",
        subject="Hello",
        body=VALID_BODY_WITH_LINK,
    )
    assert reason is None


def test_has_unsubscribe_link_requires_token_and_url() -> None:
    assert has_unsubscribe_link(VALID_BODY_WITH_LINK) is True
    assert has_unsubscribe_link("Unsubscribe here: http://example.com/unsubscribe") is False
    assert has_unsubscribe_link("No mention of opting out.") is False


def test_append_unsubscribe_footer_adds_link_once() -> None:
    from uuid import uuid4

    team_id = uuid4()
    contact_id = uuid4()
    body = "Hi, just checking in."

    with_footer = append_unsubscribe_footer(body, team_id=team_id, contact_id=contact_id)
    assert has_unsubscribe_link(with_footer)
    assert build_unsubscribe_url(team_id=team_id, contact_id=contact_id) in with_footer

    # Calling it again on an already-footed body must not duplicate the footer.
    twice = append_unsubscribe_footer(with_footer, team_id=team_id, contact_id=contact_id)
    assert twice.count("Unsubscribe") == 1


def test_run_compliance_agent_fails_without_contact() -> None:
    passed, reason = run_compliance_agent(
        contact=None,
        draft=DraftEmailResponse(subject="Hi", body=VALID_BODY_WITH_LINK, tone="professional"),
    )
    assert passed is False
    assert reason == "No linked contact found."


def test_run_compliance_agent_fails_without_draft() -> None:
    class _FakeContact:
        consent_email = True
        email = "lead@example.com"

    passed, reason = run_compliance_agent(contact=_FakeContact(), draft=None)  # type: ignore[arg-type]
    assert passed is False
    assert reason == "No draft content available."
