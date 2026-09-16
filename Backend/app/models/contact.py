"""Contact model."""

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Contact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Person record within a team."""

    __tablename__ = "contacts"

    team_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    consent_sms: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    # Metadata for Lead Scoring
    job_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    account_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Lead Scoring results
    lead_score: Mapped[int] = mapped_column(nullable=False, default=0)
    lead_tier: Mapped[str | None] = mapped_column(String(20), nullable=True) # Hot, Warm, Cold
    lead_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preferred_timezone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    working_days: Mapped[str | None] = mapped_column(String(100), nullable=True)
    working_hours_start: Mapped[str | None] = mapped_column(String(20), nullable=True)
    working_hours_end: Mapped[str | None] = mapped_column(String(20), nullable=True)
    preferred_meeting_windows: Mapped[str | None] = mapped_column(String(255), nullable=True)
    blocked_days: Mapped[str | None] = mapped_column(String(255), nullable=True)

    team: Mapped["Team"] = relationship("Team", back_populates="contacts")
    account: Mapped["Account | None"] = relationship("Account")
    deals: Mapped[list["Deal"]] = relationship("Deal", back_populates="contact")
    email_drafts: Mapped[list["EmailDraft"]] = relationship("EmailDraft")
    approvals: Mapped[list["AgentApproval"]] = relationship("AgentApproval")
    documents: Mapped[list["Document"]] = relationship("Document")
