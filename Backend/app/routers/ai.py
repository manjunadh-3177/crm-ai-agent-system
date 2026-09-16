"""AI utility routes."""

from uuid import UUID

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.forecast_agent import generate_forecast
from app.ai.agents.nurturer_agent import generate_nurture_now, get_nurture_status, run_nurturer_scan
from app.ai.agents.scheduler_agent import book_slot, suggest_slots
from app.ai.llm import chat
from app.ai.memory import get_contact_memory
from app.core.auth import AuthContext, get_auth_context, requires_role
from app.core.db import get_db
from app.schemas.ai import (
    AgentApprovalDecisionResponse,
    AgentApprovalListItem,
    AITestRequest,
    AITestResponse,
    ApprovalDecisionRequest,
    ContactMemoryResponse,
    DraftEmailRequest,
    DraftEmailResponse,
    DraftEmailUpdateRequest,
    ForecastInsightEnvelope,
    LeadSummaryRequest,
    LeadSummaryResponse,
    NurtureGenerateRequest,
    NurtureGenerateResponse,
    NurtureStatusResponse,
    SchedulerBookRequest,
    SchedulerSuggestRequest,
    SchedulerSuggestResponse,
)
from app.schemas.crm import MeetingRead
from app.services.ai_approvals import (
    approve_approval,
    cancel_email_approval_queue,
    list_approval_history,
    list_pending_approvals,
    reject_approval,
    retry_email_approval,
)
from app.services.ai_email import generate_email_draft, update_email_draft_for_approval
from app.services.ai_summary import generate_lead_summary

router = APIRouter(tags=["ai"])


@router.post("/ai/test", response_model=AITestResponse)
async def ai_test(payload: AITestRequest) -> AITestResponse:
    """Run a simple prompt through the configured LLM gateway."""
    text = await chat(
        messages=[{"role": "user", "content": payload.prompt}],
        metadata={"route": "/ai/test"},
    )
    return AITestResponse(response=text)


@router.post("/ai/lead-summary", response_model=LeadSummaryResponse)
async def ai_lead_summary(
    payload: LeadSummaryRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> LeadSummaryResponse:
    """Generate a lead summary using CRM data."""
    return await generate_lead_summary(
        db,
        contact_id=payload.contact_id,
        team_id=auth.team_id,
        deal_id=payload.deal_id,
    )


@router.post("/ai/draft-email", response_model=DraftEmailResponse)
async def ai_draft_email(
    payload: DraftEmailRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> DraftEmailResponse:
    """Generate and store a draft email using CRM data."""
    return await generate_email_draft(
        db,
        contact_id=payload.contact_id,
        team_id=auth.team_id,
        deal_id=payload.deal_id,
    )


@router.patch("/ai/approvals/{approval_id}/draft", response_model=DraftEmailResponse)
async def ai_update_approval_draft(
    approval_id: UUID,
    payload: DraftEmailUpdateRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> DraftEmailResponse:
    """Update the draft attached to a pending approval."""
    return await update_email_draft_for_approval(
        db,
        approval_id=approval_id,
        team_id=auth.team_id,
        payload=payload,
        actor_id=auth.user_id,
    )


@router.get("/ai/memory/{contact_id}", response_model=ContactMemoryResponse)
async def ai_contact_memory(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> ContactMemoryResponse:
    """Return structured memory for a contact."""
    return await get_contact_memory(db, contact_id, team_id=auth.team_id)


@router.get("/ai/forecast", response_model=ForecastInsightEnvelope)
async def ai_forecast(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(requires_role("admin", "manager")),
) -> ForecastInsightEnvelope:
    """Return team-scoped forecasting insights for managers."""
    return await generate_forecast(
        db,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )


@router.get("/ai/nurture/status", response_model=NurtureStatusResponse)
async def ai_nurture_status(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> NurtureStatusResponse:
    """Return current pending nurture approval status."""
    return NurtureStatusResponse(**await get_nurture_status(db, team_id=auth.team_id))


@router.post("/ai/nurture/run", response_model=NurtureGenerateResponse)
async def ai_run_nurturer(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> NurtureGenerateResponse:
    """Scan for inactive open deals and create nurture approvals."""
    if not auth.team_id:
        return NurtureGenerateResponse(
            status="skipped",
            approval_id=None,
            reason="Missing team context for scan.",
        )

    queue_result = await enqueue_background_job(
        "nurture_scan_job",
        str(auth.team_id),
        auth.user_id,
    )
    if queue_result.get("queued"):
        return NurtureGenerateResponse(
            status="queued",
            approval_id=queue_result["job_id"],
            reason="Nurture scan queued in background.",
        )

    try:
        result = await run_nurturer_scan(
            db,
            team_id=auth.team_id,
            actor_id=auth.user_id,
        )
        return NurtureGenerateResponse(
            status=result["status"],
            approval_id=result["approval_ids"][0] if result["approval_ids"] else None,
            reason=None if result["status"] == "completed" else result.get("reason"),
        )
    except Exception as e:
        print(f"Nurturer scan failure: {e}")
        return NurtureGenerateResponse(
            status="error",
            approval_id=None,
            reason=f"Scan failed: {str(e)}",
        )


@router.post("/ai/nurture/generate", response_model=NurtureGenerateResponse)
async def ai_generate_nurture(
    payload: NurtureGenerateRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> NurtureGenerateResponse:
    """Generate one nurture follow-up suggestion now."""
    result = await generate_nurture_now(
        db,
        team_id=auth.team_id,
        actor_id=auth.user_id,
        deal_id=payload.deal_id,
        contact_id=payload.contact_id,
    )
    return NurtureGenerateResponse(
        status=result["status"],
        approval_id=result.get("approval_id"),
        reason=result.get("reason"),
    )


@router.post("/ai/scheduler/suggest", response_model=SchedulerSuggestResponse)
async def ai_scheduler_suggest(
    payload: SchedulerSuggestRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> SchedulerSuggestResponse:
    """Suggest practical meeting slots for the next 7 days."""
    result = await suggest_slots(
        db,
        team_id=auth.team_id,
        actor_id=auth.user_id,
        contact_id=payload.contact_id,
        deal_id=payload.deal_id,
        duration_minutes=payload.duration_minutes,
        timezone_name=payload.timezone,
    )
    return SchedulerSuggestResponse(**result)


@router.post("/ai/scheduler/book", response_model=MeetingRead)
async def ai_scheduler_book(
    payload: SchedulerBookRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> MeetingRead:
    """Book a selected scheduler slot using the existing meeting service."""
    return await book_slot(
        db,
        team_id=auth.team_id,
        actor_id=auth.user_id,
        contact_id=payload.contact_id,
        deal_id=payload.deal_id,
        starts_at=payload.starts_at,
        duration_minutes=payload.duration_minutes,
        timezone_name=payload.timezone,
    )


@router.get("/ai/approvals", response_model=list[AgentApprovalListItem])
async def ai_list_approvals(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[AgentApprovalListItem]:
    """List pending approvals for human review."""
    return await list_pending_approvals(db, team_id=auth.team_id)


@router.get("/ai/approvals/history", response_model=list[AgentApprovalListItem])
async def ai_list_approval_history(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[AgentApprovalListItem]:
    """List decided approvals including execution details."""
    return await list_approval_history(db, team_id=auth.team_id)


@router.post("/ai/approvals/{approval_id}/approve", response_model=AgentApprovalDecisionResponse)
async def ai_approve(
    approval_id: UUID,
    payload: ApprovalDecisionRequest | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> AgentApprovalDecisionResponse:
    """Approve a pending draft."""
    return await approve_approval(
        db,
        approval_id=approval_id,
        team_id=auth.team_id,
        actor_id=auth.user_id,
        notes=payload.notes if payload else None,
    )


@router.post("/ai/approvals/{approval_id}/reject", response_model=AgentApprovalDecisionResponse)
async def ai_reject(
    approval_id: UUID,
    payload: ApprovalDecisionRequest | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> AgentApprovalDecisionResponse:
    """Reject a pending draft."""
    return await reject_approval(
        db,
        approval_id=approval_id,
        team_id=auth.team_id,
        actor_id=auth.user_id,
        notes=payload.notes if payload else None,
    )


@router.post("/ai/approvals/{approval_id}/retry-send", response_model=AgentApprovalDecisionResponse)
async def ai_retry_send(
    approval_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> AgentApprovalDecisionResponse:
    """Retry delivery for an approved email approval."""
    return await retry_email_approval(
        db,
        approval_id=approval_id,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )


@router.post("/ai/approvals/{approval_id}/cancel-send", response_model=AgentApprovalDecisionResponse)
async def ai_cancel_send(
    approval_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> AgentApprovalDecisionResponse:
    """Cancel a queued or sending email approval."""
    return await cancel_email_approval_queue(
        db,
        approval_id=approval_id,
        team_id=auth.team_id,
        actor_id=auth.user_id,
    )


@router.post("/ai/research/contact/{contact_id}")
async def ai_research_contact(
    contact_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> dict:
    """Run AI research enrichment on a contact."""
    from app.ai.agents.research_agent import research_contact
    result = await research_contact(db, contact_id, team_id=auth.team_id)
    if result is None:
        return {"status": "skipped", "reason": "Insufficient data or LLM unavailable"}
    return {"status": "completed", **result}


@router.post("/ai/research/account/{account_id}")
async def ai_research_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> dict:
    """Run AI research enrichment on an account."""
    from app.ai.agents.research_agent import research_account
    result = await research_account(db, account_id, team_id=auth.team_id)
    if result is None:
        return {"status": "skipped", "reason": "Insufficient data or LLM unavailable"}
    return {"status": "completed", **result}
