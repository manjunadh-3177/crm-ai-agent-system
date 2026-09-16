"""Schemas for AI gateway endpoints."""

from datetime import date
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AITestRequest(BaseModel):
    """Request body for the AI test endpoint."""

    prompt: str = Field(min_length=1)


class AITestResponse(BaseModel):
    """Normalized response from the AI test endpoint."""

    response: str


class LeadSummaryRequest(BaseModel):
    """Request body for the lead summary endpoint."""

    contact_id: UUID
    deal_id: UUID | None = None


class LeadSummaryResponse(BaseModel):
    """Normalized AI summary response."""

    summary: str
    recommended_next_action: str
    priority: str


class DraftEmailRequest(BaseModel):
    """Request body for email draft generation."""

    contact_id: UUID
    deal_id: UUID | None = None


class DraftEmailResponse(BaseModel):
    """Normalized email draft response."""

    subject: str
    body: str
    tone: str


class DraftEmailUpdateRequest(BaseModel):
    """Manual edits to an existing email draft."""

    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)


class ContactMemoryResponse(BaseModel):
    """Structured memory summary for a contact."""

    relationship_status: str
    last_contacted_at: datetime | None = None
    common_topics: list[str]
    responsiveness: str
    recommended_tone: str


class ForecastStageMetric(BaseModel):
    """Count of deals in a given stage."""

    stage: str
    count: int


class ForecastDealItem(BaseModel):
    """Compact deal item used in analytics responses."""

    id: UUID
    name: str
    amount: float | None = None
    currency: str
    probability: int | None = None
    stage: str
    owner: str | None = None
    expected_close_date: date | None = None
    last_activity_at: datetime | None = None
    stalled_days: int | None = None


class ForecastWinLossMetric(BaseModel):
    """Count and value for won/lost period metrics."""

    count: int
    total_value: float


class ForecastMetricsResponse(BaseModel):
    """Deterministic team pipeline analytics."""

    deals_by_stage: list[ForecastStageMetric]
    total_pipeline_value: float
    weighted_pipeline_value: float
    avg_deal_size: float
    stalled_deals: list[ForecastDealItem]
    won_this_month: ForecastWinLossMetric
    lost_this_month: ForecastWinLossMetric
    close_this_month_estimate: float
    top_open_deals: list[ForecastDealItem]


class ForecastInsightResponse(BaseModel):
    """Forecast manager guidance produced by the ForecastAgent."""

    summary: str
    risks: list[str]
    opportunities: list[str]
    recommended_actions: list[str]


class ForecastInsightEnvelope(BaseModel):
    """Combined metrics plus manager-facing forecast commentary."""

    metrics: ForecastMetricsResponse
    summary: str
    risks: list[str]
    opportunities: list[str]
    recommended_actions: list[str]


class ApprovalDecisionRequest(BaseModel):
    """Optional notes for approving or rejecting a draft."""

    notes: str | None = Field(default=None, max_length=1000)


class AgentApprovalListItem(BaseModel):
    """Approval queue item for the UI."""

    id: UUID
    type: Literal["email"]
    status: Literal["pending", "approved", "rejected"]
    contact_id: UUID
    deal_id: UUID | None = None
    draft_id: UUID
    created_at: datetime
    decided_at: datetime | None = None
    decision_notes: str | None = None
    executed_at: datetime | None = None
    execution_status: str | None = None
    provider_message_id: str | None = None
    execution_detail: str | None = None
    contact_name: str
    subject: str
    body: str
    sms_body: str | None = None


class AgentApprovalDecisionResponse(BaseModel):
    """Approval decision result."""

    id: UUID
    status: Literal["approved", "rejected"]
    decided_at: datetime | None = None
    decision_notes: str | None = None
    executed_at: datetime | None = None
    execution_status: str | None = None
    provider_message_id: str | None = None
    execution_detail: str | None = None


class NurtureGenerateRequest(BaseModel):
    """Manual nurture trigger request."""

    contact_id: UUID | None = None
    deal_id: UUID | None = None


class NurtureGenerateResponse(BaseModel):
    """Outcome from a nurture generation attempt."""

    status: str
    approval_id: str | None = None
    reason: str | None = None


class NurturePendingItem(BaseModel):
    """Pending nurture approval mapping."""

    approval_id: str
    contact_id: str
    deal_id: str | None = None
    created_at: str


class NurtureStatusResponse(BaseModel):
    """Pending nurture approval status for the UI."""

    pending_count: int
    pending_contact_ids: list[str]
    pending_deal_ids: list[str]
    pending_items: list[NurturePendingItem]


class SchedulerSuggestRequest(BaseModel):
    """Scheduler suggestion request."""

    contact_id: UUID | None = None
    deal_id: UUID | None = None
    duration_minutes: int = Field(default=30, ge=15, le=120)
    timezone: str = Field(default="UTC", max_length=100)


class SchedulerSuggestedSlot(BaseModel):
    """Suggested slot from the scheduler agent."""

    starts_at: datetime
    ends_at: datetime
    label: str
    your_time_label: str
    customer_time_label: str
    your_timezone: str
    customer_timezone: str
    duration_minutes: int


class SchedulerAvailabilitySummary(BaseModel):
    """Availability summary for one side of the scheduling match."""

    timezone: str
    working_days: str
    working_hours_start: str
    working_hours_end: str
    preferred_meeting_windows: str | None = None
    blocked_days: str | None = None
    summary: str


class SchedulerSuggestResponse(BaseModel):
    """Available slot suggestions."""

    slots: list[SchedulerSuggestedSlot]
    message: str
    your_availability: SchedulerAvailabilitySummary
    customer_availability: SchedulerAvailabilitySummary


class SchedulerBookRequest(BaseModel):
    """Scheduler booking request."""

    contact_id: UUID | None = None
    deal_id: UUID | None = None
    starts_at: datetime
    duration_minutes: int = Field(default=30, ge=15, le=120)
    timezone: str = Field(default="UTC", max_length=100)
