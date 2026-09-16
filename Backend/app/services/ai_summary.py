"""AI summary service using real CRM data."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.llm import chat, start_trace_scope
from app.models import Contact, Deal
from app.schemas.ai import LeadSummaryResponse


async def generate_lead_summary(
    db: AsyncSession,
    *,
    contact_id: UUID,
    team_id: UUID,
    deal_id: UUID | None = None,
) -> LeadSummaryResponse:
    """Generate an AI lead summary from CRM records."""
    trace_scope = start_trace_scope(
        "ai_summary",
        metadata={
            "team_id": str(team_id),
            "contact_id": str(contact_id),
            "deal_id": str(deal_id) if deal_id else None,
        },
        input_payload={"contact_id": str(contact_id), "deal_id": str(deal_id) if deal_id else None},
    )
    contact, related_deals, current_deal = await load_contact_deal_context(
        db,
        contact_id=contact_id,
        team_id=team_id,
        deal_id=deal_id,
    )

    crm_context = build_contact_context(contact, related_deals, current_deal)
    prompt = build_lead_summary_prompt(crm_context)

    try:
        raw_text = await chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise sales CRM assistant. "
                        "CRITICAL: You must respond ONLY with a valid JSON object. "
                        "Do not include any conversational text, markdown formatting, or thoughts. "
                        "Required JSON structure: "
                        '{"summary": "string", "recommended_next_action": "string", "priority": "low|medium|high"}'
                    ),
                },
                {"role": "user", "content": f"{prompt}\n\nRemember: Return ONLY the JSON object."},
            ],
            purpose="lead_summary",
            temperature=0.1,
            metadata={
                "route": "/ai/lead-summary",
                "team_id": str(team_id),
                "contact_id": str(contact.id),
                "deal_id": str(current_deal.id) if current_deal else None,
            },
        )
        response = parse_json_response(raw_text, LeadSummaryResponse, {"low", "medium", "high"})
        trace_scope.finish(output=response.model_dump(mode="json"), status_message="success")
        return response
    except Exception as exc:
        trace_scope.finish(output={"error": str(exc)}, status_message="failure")
        raise


async def load_contact_deal_context(
    db: AsyncSession,
    *,
    contact_id: UUID,
    team_id: UUID,
    deal_id: UUID | None = None,
) -> tuple[Contact, list[Deal], Deal | None]:
    """Load a contact plus related deal context."""
    contact = await db.get(Contact, contact_id)
    if contact is None or contact.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found.",
        )

    if deal_id is not None:
        selected_result = await db.execute(
            select(Deal)
            .options(selectinload(Deal.stage), selectinload(Deal.owner))
            .where(Deal.id == deal_id, Deal.team_id == team_id)
        )
        selected_deal = selected_result.scalar_one_or_none()
        if selected_deal is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deal not found.",
            )
        if selected_deal.contact_id != contact.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Deal does not belong to the provided contact.",
            )
    else:
        selected_deal = None

    deals_result = await db.execute(
        select(Deal)
        .options(selectinload(Deal.stage), selectinload(Deal.owner))
        .where(Deal.contact_id == contact.id, Deal.team_id == team_id)
        .order_by(Deal.created_at.desc())
    )
    related_deals = list(deals_result.scalars().all())
    current_deal = selected_deal or (related_deals[0] if related_deals else None)
    return contact, related_deals, current_deal


def build_contact_context(contact: Contact, related_deals: list[Deal], current_deal: Deal | None) -> dict[str, Any]:
    """Build a compact CRM context for prompting."""
    return {
        "contact": {
            "id": str(contact.id),
            "name": f"{contact.first_name} {contact.last_name}",
            "email": contact.email,
            "phone": contact.phone,
            "consent_sms": contact.consent_sms,
            "consent_email": contact.consent_email,
        },
        "current_deal": None
        if current_deal is None
        else {
            "id": str(current_deal.id),
            "name": current_deal.name,
            "amount": float(current_deal.amount) if current_deal.amount is not None else None,
            "currency": current_deal.currency,
            "probability": current_deal.probability,
            "expected_close_date": (
                current_deal.expected_close_date.isoformat()
                if current_deal.expected_close_date is not None
                else None
            ),
            "stage": current_deal.stage.name if current_deal.stage else None,
            "owner": current_deal.owner.full_name if current_deal.owner else None,
        },
        "related_deals": [
            {
                "id": str(deal.id),
                "name": deal.name,
                "amount": float(deal.amount) if deal.amount is not None else None,
                "currency": deal.currency,
                "probability": deal.probability,
                "stage": deal.stage.name if deal.stage else None,
                "expected_close_date": (
                    deal.expected_close_date.isoformat() if deal.expected_close_date is not None else None
                ),
            }
            for deal in related_deals[:5]
        ],
    }


def build_lead_summary_prompt(context: dict[str, Any]) -> str:
    """Build a concise deterministic prompt."""
    return (
        "Using this CRM data, produce a concise lead summary and next action.\n"
        "Keep the summary to 2-3 sentences.\n"
        "Set priority based on urgency/opportunity.\n"
        "Output MUST be a valid JSON object with keys: summary, recommended_next_action, priority\n\n"
        f"CRM data:\n{json.dumps(context, indent=2)}\n\n"
        "JSON Response:"
    )


import ast
import re


def parse_json_response(raw_text: str, schema: type, allowed_priorities: set[str] | None = None):
    """Parse and validate a JSON-only model response with multiple fallbacks."""
    # 1. Clean markdown code blocks if present
    cleaned_text = raw_text.strip()
    if cleaned_text.startswith("```"):
        # Remove ```json or just ```
        cleaned_text = re.sub(r"^```(?:json)?\n?", "", cleaned_text)
        cleaned_text = re.sub(r"\n?```$", "", cleaned_text)
        cleaned_text = cleaned_text.strip()

    # 2. Try standard JSON
    try:
        data = json.loads(cleaned_text)
    except json.JSONDecodeError:
        # 3. Try Python literal eval (handles single quotes)
        try:
            data = ast.literal_eval(cleaned_text)
            if not isinstance(data, dict):
                raise ValueError("Not a dictionary")
        except (ValueError, SyntaxError):
            # 4. Regex fallback for subject/body/summary if it's a mess
            data = {}

            # Look for "subject": "..." or 'subject': '...'
            subject_match = re.search(r"['\"]subject['\"]\s*:\s*['\"](.*?)['\"](?:\s*,|\s*})", cleaned_text, re.DOTALL | re.IGNORECASE)
            if subject_match:
                data["subject"] = subject_match.group(1)

            # Look for "body": "..." or 'body': '...'
            body_match = re.search(r"['\"]body['\"]\s*:\s*['\"](.*?)['\"](?:\s*,|\s*})", cleaned_text, re.DOTALL | re.IGNORECASE)
            if body_match:
                data["body"] = body_match.group(1)

            # Look for "summary": "..." or 'summary': '...'
            summary_match = re.search(r"['\"]summary['\"]\s*:\s*['\"](.*?)['\"](?:\s*,|\s*})", cleaned_text, re.DOTALL | re.IGNORECASE)
            if summary_match:
                data["summary"] = summary_match.group(1)

            # Look for "recommended_next_action"
            action_match = re.search(r"['\"]recommended_next_action['\"]\s*:\s*['\"](.*?)['\"](?:\s*,|\s*})", cleaned_text, re.DOTALL | re.IGNORECASE)
            if action_match:
                data["recommended_next_action"] = action_match.group(1)

            # Look for "priority"
            priority_match = re.search(r"['\"]priority['\"]\s*:\s*['\"](.*?)['\"](?:\s*,|\s*})", cleaned_text, re.DOTALL | re.IGNORECASE)
            if priority_match:
                data["priority"] = priority_match.group(1).lower()

            if not data:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"AI returned unparseable response: {raw_text}",
                )

    # 5. Final structure validation
    try:
        # Fill in missing defaults for tone if schema expects it
        if "tone" not in data and "tone" in schema.model_fields:
            data["tone"] = "professional"

        response = schema(**data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI returned invalid structure: {data}",
        ) from exc

    if allowed_priorities is not None and getattr(response, "priority", None) not in allowed_priorities:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI returned an unsupported priority value.",
        )

    return response
