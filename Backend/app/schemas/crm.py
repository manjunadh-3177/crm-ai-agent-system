"""Schemas for CRM APIs."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.user import UserRole


class ORMBaseSchema(BaseModel):
    """Base schema configured for SQLAlchemy ORM objects."""

    model_config = ConfigDict(from_attributes=True)


class TeamRead(ORMBaseSchema):
    id: UUID
    name: str
    timezone: str
    created_at: datetime
    updated_at: datetime


class EmailMessageRead(ORMBaseSchema):
    id: UUID
    team_id: UUID
    contact_id: UUID | None
    deal_id: UUID | None
    approval_id: UUID | None
    direction: str
    recipient_email: str
    subject: str
    body: str
    provider_message_id: str | None
    status: str
    error_detail: str | None
    created_at: datetime


class SMSMessageRead(ORMBaseSchema):
    id: UUID
    team_id: UUID
    contact_id: UUID | None
    direction: str
    thread_id: str
    from_number: str
    to_number: str
    body: str
    status: str
    provider_sid: str | None
    error_detail: str | None
    sent_at: datetime | None
    received_at: datetime | None
    is_read: bool
    read_at: datetime | None
    agent_suggestion: str | None
    created_at: datetime
    contact: "ContactRead | None" = None


class ContactRead(ORMBaseSchema):
    id: UUID
    team_id: UUID
    first_name: str
    last_name: str
    email: str
    phone: str | None
    consent_sms: bool
    consent_email: bool
    job_title: str | None
    description: str | None
    account_id: UUID | None
    lead_score: int
    lead_tier: str | None
    lead_reason: str | None
    preferred_timezone: str | None
    working_days: str | None
    working_hours_start: str | None
    working_hours_end: str | None
    preferred_meeting_windows: str | None
    blocked_days: str | None
    created_at: datetime
    updated_at: datetime


class ContactCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)
    consent_sms: bool = False
    consent_email: bool = False
    job_title: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    account_id: UUID | None = None
    preferred_timezone: str | None = Field(default=None, max_length=100)
    working_days: str | None = Field(default="Mon-Fri", max_length=100)
    working_hours_start: str | None = Field(default="09:00", max_length=20)
    working_hours_end: str | None = Field(default="17:00", max_length=20)
    preferred_meeting_windows: str | None = Field(default=None, max_length=255)
    blocked_days: str | None = Field(default=None, max_length=255)


class ContactUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    consent_sms: bool | None = None
    consent_email: bool | None = None
    job_title: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    account_id: UUID | None = None
    preferred_timezone: str | None = Field(default=None, max_length=100)
    working_days: str | None = Field(default=None, max_length=100)
    working_hours_start: str | None = Field(default=None, max_length=20)
    working_hours_end: str | None = Field(default=None, max_length=20)
    preferred_meeting_windows: str | None = Field(default=None, max_length=255)
    blocked_days: str | None = Field(default=None, max_length=255)


class AccountRead(ORMBaseSchema):
    id: UUID
    team_id: UUID
    name: str
    domain: str | None
    industry: str | None
    created_at: datetime
    updated_at: datetime


class AccountDetailContactRead(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: str
    phone: str | None


class AccountDetailOpenDealRead(BaseModel):
    id: UUID
    name: str
    amount: Decimal | None
    stage: str
    probability: int | None
    expected_close_date: date | None


class AccountDetailClosedDealRead(BaseModel):
    id: UUID
    name: str
    amount: Decimal | None
    stage: str
    updated_at: datetime


class AccountDetailStakeholderRead(BaseModel):
    deal_name: str
    contact_name: str
    role: str


class AccountActivitySummaryRead(BaseModel):
    total_contacts: int
    total_open_deals: int
    pipeline_value: Decimal
    won_value: Decimal
    last_activity_at: datetime | None


class AccountDetailRead(BaseModel):
    id: UUID
    name: str
    website: str | None
    industry: str | None
    size: str | None
    created_at: datetime
    contacts: list[AccountDetailContactRead]
    open_deals: list[AccountDetailOpenDealRead]
    closed_deals: list[AccountDetailClosedDealRead]
    stakeholders: list[AccountDetailStakeholderRead]
    activity_summary: AccountActivitySummaryRead


class ProductRead(ORMBaseSchema):
    id: UUID
    team_id: UUID
    name: str
    sku: str
    description: str | None
    price: Decimal
    currency: str
    custom_fields: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    sku: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    price: Decimal = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sku: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    price: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    custom_fields: dict[str, Any] | None = None


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    domain: str | None = Field(default=None, max_length=255)
    industry: str | None = Field(default=None, max_length=255)


class DealStageRead(ORMBaseSchema):
    id: UUID
    team_id: UUID
    name: str
    position: int
    is_closed: bool
    created_at: datetime
    updated_at: datetime


class UserRead(ORMBaseSchema):
    id: UUID
    email: str
    full_name: str
    role: UserRole


class DealCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    amount: Decimal | None = None
    currency: str = Field(default="USD", min_length=3, max_length=3)
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_close_date: date | None = None
    owner_user_id: UUID | None = None
    stage_id: UUID
    contact_id: UUID | None = None
    account_id: UUID | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "DealCreate":
        if self.contact_id is None and self.account_id is None:
            raise ValueError("At least one of contact_id or account_id is required.")
        return self


class DealUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    amount: Decimal | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_close_date: date | None = None
    owner_user_id: UUID | None = None
    stage_id: UUID | None = None
    contact_id: UUID | None = None
    account_id: UUID | None = None


class DealStageUpdate(BaseModel):
    stage_id: UUID


class DealSummaryRead(ORMBaseSchema):
    id: UUID
    team_id: UUID
    name: str
    amount: Decimal | None
    currency: str
    probability: int | None
    expected_close_date: date | None
    owner_user_id: UUID | None
    stage_id: UUID
    contact_id: UUID | None
    account_id: UUID | None
    deal_health: str
    deal_reason: str | None
    created_at: datetime
    updated_at: datetime
    stage: DealStageRead
    owner: UserRead | None
    contact: ContactRead | None = None
    account: AccountRead | None = None
    line_items: list["DealLineItemRead"] = Field(default_factory=list)
    stakeholders: list["DealContactRoleRead"] = Field(default_factory=list)


class DealLineItemRead(ORMBaseSchema):
    id: UUID
    team_id: UUID
    deal_id: UUID
    product_id: UUID
    quantity: Decimal
    unit_price: Decimal
    subtotal: Decimal
    currency: str
    created_at: datetime
    updated_at: datetime
    product: ProductRead


class DealLineItemCreate(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal | None = Field(default=None, gt=0)


class DealLineItemUpdate(BaseModel):
    quantity: Decimal | None = Field(default=None, gt=0)
    unit_price: Decimal | None = Field(default=None, gt=0)


class DealContactRoleRead(ORMBaseSchema):
    id: UUID
    team_id: UUID
    deal_id: UUID
    contact_id: UUID
    role: str
    created_at: datetime
    updated_at: datetime
    contact: ContactRead


class DealContactRoleCreate(BaseModel):
    contact_id: UUID
    role: str = Field(pattern="^(decision_maker|champion|influencer|blocker|end_user)$")


class DealContactRoleUpdate(BaseModel):
    role: str = Field(pattern="^(decision_maker|champion|influencer|blocker|end_user)$")


class DealDetailRead(DealSummaryRead):
    pass


class MeetingRead(ORMBaseSchema):
    id: UUID
    team_id: UUID
    title: str
    description: str | None
    starts_at: datetime
    ends_at: datetime
    timezone: str
    status: str
    location: str | None
    meeting_type: str
    reminder_minutes: int | None
    contact_id: UUID | None
    deal_id: UUID | None
    account_id: UUID | None
    created_at: datetime
    updated_at: datetime
    contact: ContactRead | None = None
    deal: DealSummaryRead | None = None
    account: AccountRead | None = None


class MeetingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    starts_at: datetime
    ends_at: datetime
    timezone: str = Field(default="UTC", max_length=100)
    location: str | None = Field(default=None, max_length=500)
    meeting_type: str = Field(pattern="^(call|demo|followup|internal)$", default="internal")
    reminder_minutes: int | None = None
    contact_id: UUID | None = None
    deal_id: UUID | None = None
    account_id: UUID | None = None


class MeetingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    timezone: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=500)
    meeting_type: str | None = Field(pattern="^(call|demo|followup|internal)$", default=None)
    reminder_minutes: int | None = None
    contact_id: UUID | None = None
    deal_id: UUID | None = None
    account_id: UUID | None = None


class SMSMessageSend(BaseModel):
    to_number: str = Field(min_length=5, max_length=40)
    body: str = Field(min_length=1, max_length=1600)
    contact_id: UUID | None = None


class SMSAssignContactRequest(BaseModel):
    contact_id: UUID


class SMSCreateTaskRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class TaskRead(ORMBaseSchema):
    id: UUID
    team_id: UUID
    title: str
    description: str | None
    due_at: datetime | None
    priority: str
    status: str
    contact_id: UUID | None
    deal_id: UUID | None
    account_id: UUID | None
    assigned_user_id: str | None
    created_at: datetime
    updated_at: datetime
    contact: ContactRead | None = None
    deal: DealSummaryRead | None = None
    account: AccountRead | None = None


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    due_at: datetime | None = None
    priority: str = Field(pattern="^(low|med|high)$", default="med")
    status: str = Field(pattern="^(open|done|cancelled)$", default="open")
    contact_id: UUID | None = None
    deal_id: UUID | None = None
    account_id: UUID | None = None
    assigned_user_id: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    due_at: datetime | None = None
    priority: str | None = Field(pattern="^(low|med|high)$", default=None)
    status: str | None = Field(pattern="^(open|done|cancelled)$", default=None)
    contact_id: UUID | None = None
    deal_id: UUID | None = None
    account_id: UUID | None = None
    assigned_user_id: str | None = None


class DocumentRead(ORMBaseSchema):
    id: UUID
    team_id: UUID
    deal_id: UUID | None
    contact_id: UUID | None
    account_id: UUID | None
    title: str
    document_type: str
    content_format: str
    status: str
    created_at: datetime
    updated_at: datetime


class ProposalDraftResponse(BaseModel):
    document: DocumentRead
    title: str
    content: str
    content_format: str


class BulkDeleteRequest(BaseModel):
    ids: list[UUID] = Field(min_length=1)


class BulkDealStageUpdateRequest(BaseModel):
    ids: list[UUID] = Field(min_length=1)
    stage_id: UUID


class BulkOperationResponse(BaseModel):
    processed: int
    skipped: int


class ImportRowError(BaseModel):
    row_number: int
    message: str
    row: dict[str, str]


class ImportResultResponse(BaseModel):
    entity: str
    created: int
    skipped: int
    failed: int
    errors: list[ImportRowError]


class DealTimelineItem(BaseModel):
    id: UUID
    type: str
    time: datetime
    description: str


class ReportsSummaryRead(BaseModel):
    total_contacts: int
    open_deals: int
    won_deals: int
    lost_deals: int
    tasks_pending: int
    meetings_upcoming: int
    pipeline_value: Decimal


class ReportsPipelineStageRead(BaseModel):
    stage: str
    count: int
    total_value: Decimal


class ReportsPipelineRead(BaseModel):
    deals_by_stage: list[ReportsPipelineStageRead]
    stages: list[ReportsPipelineStageRead] = Field(default_factory=list)


class ReportsPerformanceRead(BaseModel):
    period: str
    closed_deals: int
    won_revenue: Decimal
    meetings_completed: int
    tasks_completed: int


DealSummaryRead.model_rebuild()
DealDetailRead.model_rebuild()
SMSMessageRead.model_rebuild()


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    entity_type: str = Field(min_length=1, max_length=50)
    entity_id: UUID


class NoteUpdate(BaseModel):
    body: str | None = Field(default=None, min_length=1, max_length=5000)


class NoteOut(ORMBaseSchema):
    id: UUID
    team_id: UUID
    body: str
    entity_type: str
    entity_id: UUID
    created_by_user_id: str | None
    created_at: datetime
    updated_at: datetime


class ActivityFeedItem(BaseModel):
    id: UUID
    type: str
    time: datetime
    title: str
    description: str
    actor_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    metadata_json: dict[str, Any] | None = None


class AutomationRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    trigger_type: str = Field(min_length=1, max_length=100)
    conditions_json: dict[str, Any] = Field(default_factory=dict)
    action_type: str = Field(min_length=1, max_length=100)
    action_payload_json: dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = True


class AutomationRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    trigger_type: str | None = Field(default=None, min_length=1, max_length=100)
    conditions_json: dict[str, Any] | None = None
    action_type: str | None = Field(default=None, min_length=1, max_length=100)
    action_payload_json: dict[str, Any] | None = None
    is_enabled: bool | None = None


class AutomationRuleOut(ORMBaseSchema):
    id: UUID
    team_id: UUID
    name: str
    description: str | None
    trigger_type: str
    conditions_json: dict[str, Any]
    action_type: str
    action_payload_json: dict[str, Any]
    is_enabled: bool
    run_count: int
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class NotificationRead(ORMBaseSchema):
    id: UUID
    team_id: UUID
    user_id: str | None
    type: str
    title: str
    message: str
    entity_type: str | None
    entity_id: str | None
    is_read: bool
    created_at: datetime
