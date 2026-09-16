"""Proposal generation service."""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import chat
from app.models import Document
from app.schemas.crm import ProposalDraftResponse
from app.services.audit import log_audit
from app.services.deals import get_deal_or_404


async def generate_deal_proposal(
    db: AsyncSession,
    *,
    deal_id: UUID,
    team_id: UUID,
    actor_id: str | None = None,
) -> ProposalDraftResponse:
    """Generate a proposal draft and persist document metadata."""
    deal = await get_deal_or_404(
        db,
        deal_id,
        team_id=team_id,
        include_detail=True,
    )
    team = deal.team
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")

    line_items = [
        {
            "product_name": item.product.name,
            "sku": item.product.sku,
            "description": item.product.description,
            "quantity": float(item.quantity),
            "unit_price": float(item.unit_price),
            "subtotal": float(item.subtotal),
            "currency": item.currency,
        }
        for item in deal.line_items
    ]
    total = sum((item.subtotal for item in deal.line_items), start=Decimal("0.00"))
    signature = f"Best regards,\n{team.name}"
    context = {
        "team": {"name": team.name, "timezone": team.timezone, "signature": signature},
        "deal": {
            "id": str(deal.id),
            "name": deal.name,
            "amount": float(deal.amount) if deal.amount is not None else None,
            "currency": deal.currency,
            "stage": deal.stage.name,
            "probability": deal.probability,
            "expected_close_date": deal.expected_close_date.isoformat() if deal.expected_close_date else None,
        },
        "account": {
            "name": deal.account.name if deal.account else None,
            "domain": deal.account.domain if deal.account else None,
            "industry": deal.account.industry if deal.account else None,
        },
        "contact": {
            "name": f"{deal.contact.first_name} {deal.contact.last_name}" if deal.contact else None,
            "email": deal.contact.email if deal.contact else None,
            "phone": deal.contact.phone if deal.contact else None,
        },
        "line_items": line_items,
        "line_item_total": float(total),
    }

    title = f"{deal.name} Proposal"
    content = await _generate_proposal_content(context, fallback_title=title)

    document = Document(
        team_id=team_id,
        deal_id=deal.id,
        contact_id=deal.contact_id,
        account_id=deal.account_id,
        title=content["title"],
        document_type="proposal",
        content_format="markdown",
        status="draft",
    )
    db.add(document)
    await db.flush()
    await log_audit(
        db,
        action="proposal.generated",
        entity_type="document",
        entity_id=str(document.id),
        actor_type="ai",
        team_id=team_id,
        actor_id=actor_id,
        metadata={
            "deal_id": str(deal.id),
            "line_item_count": len(line_items),
            "title": content["title"],
        },
    )
    await db.commit()
    await db.refresh(document)
    return ProposalDraftResponse(
        document=document,
        title=content["title"],
        content=content["body"],
        content_format="markdown",
    )


async def _generate_proposal_content(context: dict[str, object], *, fallback_title: str) -> dict[str, str]:
    try:
        raw = await chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You create concise sales proposals. "
                        "Return only valid JSON with keys title and body. "
                        "The body must be markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Create a short proposal draft using this CRM context. "
                        "Include a short overview, scope table/list, commercial summary, next steps, and signature.\n"
                        f"{json.dumps(context, indent=2)}"
                    ),
                },
            ],
            temperature=0.1,
            metadata={"route": "/api/v1/deals/{deal_id}/proposal"},
        )
        parsed = json.loads(raw)
        title = str(parsed.get("title") or fallback_title).strip() or fallback_title
        body = str(parsed.get("body") or "").strip()
        if body:
            return {"title": title, "body": body}
    except Exception:
        pass

    return {"title": fallback_title, "body": _build_fallback_proposal(context)}


def _build_fallback_proposal(context: dict[str, object]) -> str:
    deal = context["deal"]
    contact = context["contact"]
    account = context["account"]
    team = context["team"]
    line_items = context["line_items"]
    lines = [
        f"# {deal['name']} Proposal",
        "",
        "## Overview",
        (
            f"This proposal outlines the recommended commercial package for "
            f"{account['name'] or contact['name'] or 'the prospect'}."
        ),
        "",
        "## Proposed Scope",
    ]
    if line_items:
        for item in line_items:
            lines.append(
                f"- {item['product_name']} ({item['quantity']} x {item['unit_price']} {item['currency']}) = {item['subtotal']} {item['currency']}"
            )
    else:
        lines.append("- Proposal scope to be finalized from the active deal details.")
    lines.extend(
        [
            "",
            "## Commercial Summary",
            f"- Stage: {deal['stage']}",
            f"- Expected close date: {deal['expected_close_date'] or 'TBD'}",
            f"- Current estimated value: {deal['amount'] or context['line_item_total']} {deal['currency']}",
            "",
            "## Next Steps",
            "- Review scope and pricing with stakeholders.",
            "- Confirm any open commercial or implementation questions.",
            "- Approve the proposal so the team can prepare the final version.",
            "",
            team["signature"],
        ]
    )
    return "\n".join(lines)
