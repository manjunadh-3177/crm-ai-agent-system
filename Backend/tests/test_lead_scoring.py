"""Tests for the deterministic lead-scoring rules used by the qualifier agent."""

from types import SimpleNamespace

from app.ai.agents.lead_qualifier_agent import score_contact


def _contact(**overrides):
    defaults = {
        "email": None,
        "phone": None,
        "account_id": None,
        "job_title": None,
        "description": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_score_contact_with_no_data_is_cold() -> None:
    score, tier, reason = score_contact(_contact())
    assert score == 0
    assert tier == "Cold"
    assert reason == "Insufficient data"


def test_score_contact_with_email_only() -> None:
    score, tier, reason = score_contact(_contact(email="lead@example.com"))
    assert score == 30
    assert tier == "Cold"
    assert "Email provided (+30)" in reason


def test_score_contact_becomes_warm_at_50() -> None:
    score, tier, _ = score_contact(_contact(email="lead@example.com", phone="555-0100"))
    assert score == 50
    assert tier == "Warm"


def test_score_contact_becomes_hot_at_80() -> None:
    score, tier, _ = score_contact(
        _contact(email="lead@example.com", phone="555-0100", account_id="acct-1", job_title="VP Sales")
    )
    assert score == 85
    assert tier == "Hot"


def test_score_contact_caps_at_100() -> None:
    score, tier, _ = score_contact(
        _contact(
            email="lead@example.com",
            phone="555-0100",
            account_id="acct-1",
            job_title="VP Sales",
            description="Enterprise buyer, budget confirmed.",
        )
    )
    assert score == 100
    assert tier == "Hot"


def test_score_contact_reason_lists_only_matched_criteria() -> None:
    _, _, reason = score_contact(_contact(email="lead@example.com", job_title="Founder"))
    assert "Email provided (+30)" in reason
    assert "Job Title provided (+15)" in reason
    assert "Phone provided" not in reason
    assert "Linked to Account" not in reason
