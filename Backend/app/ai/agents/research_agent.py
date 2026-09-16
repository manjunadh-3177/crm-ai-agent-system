"""Research Agent for enriching Contacts and Accounts with AI insights."""

import json
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import LLMProviderError, completion
from app.events import emit_event
from app.models.account import Account
from app.models.contact import Contact
from app.models.note import Note
from app.services.audit import log_audit

logger = logging.getLogger(__name__)


def run_research_agent(*, deal, event_name: str, memory_summary=None) -> dict:
    """Return lightweight research guidance for the swarm graph."""
    account_name = getattr(getattr(deal, "account", None), "name", None) or "the account"
    stage_name = getattr(getattr(deal, "stage", None), "name", None) or "current stage"
    relationship = getattr(memory_summary, "relationship_status", None) if memory_summary else None
    outreach_angle = (
        f"Reference the active {stage_name} conversation with {account_name} and suggest a concrete next step."
    )
    if relationship and relationship != "unknown":
        outreach_angle = f"Use a {relationship} relationship tone and suggest a concrete next step for {account_name}."
    return {
        "recommended_angle": outreach_angle,
        "event_name": event_name,
        "stage_name": stage_name,
        "account_name": account_name,
    }


def _build_contact_prompt(contact: Contact, account_name: str | None) -> str:
    """Build a concise research prompt from contact fields."""
    parts = [f"Name: {contact.first_name} {contact.last_name}"]
    if contact.email:
        parts.append(f"Email: {contact.email}")
    if contact.job_title:
        parts.append(f"Title: {contact.job_title}")
    if contact.phone:
        parts.append(f"Phone: {contact.phone}")
    if account_name:
        parts.append(f"Company: {account_name}")
    if contact.description:
        parts.append(f"Bio: {contact.description}")

    context = "\n".join(parts)
    return f"""Analyze this B2B sales contact and provide research insights.

{context}

Respond ONLY with valid JSON (no markdown, no backticks):
{{
  "research_summary": "Two short sentences about this contact's likely role and value.",
  "industry": "Best guess industry or 'Unknown'",
  "company_size_guess": "small | mid | enterprise | unknown",
  "outreach_angle": "One sentence suggesting how to approach this contact.",
  "confidence_score": 0-100
}}"""


def _build_account_prompt(account: Account) -> str:
    """Build a concise research prompt from account fields."""
    parts = [f"Company: {account.name}"]
    if account.domain:
        parts.append(f"Website: {account.domain}")
    if account.industry:
        parts.append(f"Industry: {account.industry}")

    context = "\n".join(parts)
    return f"""Analyze this B2B company/account and provide research insights for a sales team.

{context}

Respond ONLY with valid JSON (no markdown, no backticks):
{{
  "research_summary": "Two short sentences about this company and its market position.",
  "industry": "Confirmed or best guess industry",
  "company_size_guess": "small | mid | enterprise | unknown",
  "outreach_angle": "One sentence suggesting how to approach this company.",
  "confidence_score": 0-100
}}"""


def _parse_research_json(raw: str) -> dict | None:
    """Safely parse LLM response into research dict."""
    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        result = json.loads(cleaned)
        # Validate required fields exist
        required = ["research_summary", "industry", "company_size_guess", "outreach_angle", "confidence_score"]
        for field in required:
            if field not in result:
                result[field] = "Unknown" if field != "confidence_score" else 0
        # Clamp confidence
        result["confidence_score"] = max(0, min(100, int(result.get("confidence_score", 0))))
        return result
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(f"Failed to parse research JSON: {exc}")
        return None


async def research_contact(
    db: AsyncSession,
    contact_id: UUID,
    team_id: UUID,
) -> dict | None:
    """Run AI research on a contact and persist results as a note."""
    try:
        contact = await db.get(Contact, contact_id)
        if not contact or contact.team_id != team_id:
            return None

        # Resolve account name if linked
        account_name: str | None = None
        if contact.account_id:
            account = await db.get(Account, contact.account_id)
            if account:
                account_name = account.name

        # Check minimum data
        if not contact.email and not contact.first_name:
            return None

        prompt = _build_contact_prompt(contact, account_name)
        raw = await completion(
            prompt,
            system_prompt="You are a B2B sales research analyst. Return only valid JSON.",
            purpose="research_agent.contact",
            temperature=0.3,
        )

        result = _parse_research_json(raw)
        if not result:
            return None

        # Persist as a note on the contact
        note_body = (
            f"🔬 **Research Insights**\n"
            f"Summary: {result['research_summary']}\n"
            f"Industry: {result['industry']}\n"
            f"Company Size: {result['company_size_guess']}\n"
            f"Outreach Angle: {result['outreach_angle']}\n"
            f"Confidence: {result['confidence_score']}%"
        )

        note = Note(
            team_id=team_id,
            entity_type="contact",
            entity_id=str(contact_id),
            body=note_body,
        )
        db.add(note)
        await db.flush()

        await log_audit(
            db,
            action="agent.research_completed",
            entity_type="contact",
            entity_id=str(contact_id),
            actor_type="ai",
            team_id=team_id,
            metadata=result,
        )

        await db.commit()
        await emit_event("contact.updated", {"id": str(contact_id), "team_id": str(team_id)})

        return result

    except LLMProviderError as exc:
        logger.warning(f"Research agent LLM failure for contact {contact_id}: {exc}")
        return None
    except Exception as exc:
        logger.error(f"Research agent error for contact {contact_id}: {exc}")
        await db.rollback()
        return None


async def research_account(
    db: AsyncSession,
    account_id: UUID,
    team_id: UUID,
) -> dict | None:
    """Run AI research on an account and persist results as a note."""
    try:
        account = await db.get(Account, account_id)
        if not account or account.team_id != team_id:
            return None

        if not account.name:
            return None

        prompt = _build_account_prompt(account)
        raw = await completion(
            prompt,
            system_prompt="You are a B2B sales research analyst. Return only valid JSON.",
            purpose="research_agent.account",
            temperature=0.3,
        )

        result = _parse_research_json(raw)
        if not result:
            return None

        # Persist as a note on the account
        note_body = (
            f"🔬 **Research Insights**\n"
            f"Summary: {result['research_summary']}\n"
            f"Industry: {result['industry']}\n"
            f"Company Size: {result['company_size_guess']}\n"
            f"Outreach Angle: {result['outreach_angle']}\n"
            f"Confidence: {result['confidence_score']}%"
        )

        note = Note(
            team_id=team_id,
            entity_type="account",
            entity_id=str(account_id),
            body=note_body,
        )
        db.add(note)
        await db.flush()

        await log_audit(
            db,
            action="agent.research_completed",
            entity_type="account",
            entity_id=str(account_id),
            actor_type="ai",
            team_id=team_id,
            metadata=result,
        )

        await db.commit()
        await emit_event("account.updated", {"id": str(account_id), "team_id": str(team_id)})

        return result

    except LLMProviderError as exc:
        logger.warning(f"Research agent LLM failure for account {account_id}: {exc}")
        return None
    except Exception as exc:
        logger.error(f"Research agent error for account {account_id}: {exc}")
        await db.rollback()
        return None
