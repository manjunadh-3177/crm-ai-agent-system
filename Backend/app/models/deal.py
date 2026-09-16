"""Deal model."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Deal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Deal supporting both B2B and B2C shapes."""

    __tablename__ = "deals"
    __table_args__ = (
        CheckConstraint(
            "contact_id IS NOT NULL OR account_id IS NOT NULL",
            name="ck_deals_contact_or_account_required",
        ),
    )

    team_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    probability: Mapped[int | None] = mapped_column(nullable=True)
    expected_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    stage_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("deal_stages.id", ondelete="RESTRICT"),
        nullable=False,
    )
    contact_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    account_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Agent Health Tracking
    deal_health: Mapped[str] = mapped_column(String(20), nullable=False, default="healthy") # healthy, at_risk, stalled
    deal_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    team: Mapped["Team"] = relationship("Team", back_populates="deals")
    owner: Mapped["User | None"] = relationship("User", back_populates="owned_deals")
    stage: Mapped["DealStage"] = relationship("DealStage", back_populates="deals")
    contact: Mapped["Contact | None"] = relationship("Contact", back_populates="deals")
    account: Mapped["Account | None"] = relationship("Account", back_populates="deals")
    email_drafts: Mapped[list["EmailDraft"]] = relationship("EmailDraft")
    approvals: Mapped[list["AgentApproval"]] = relationship("AgentApproval")
    line_items: Mapped[list["DealLineItem"]] = relationship(
        "DealLineItem",
        back_populates="deal",
        cascade="all, delete-orphan",
    )
    stakeholders: Mapped[list["DealContactRole"]] = relationship(
        "DealContactRole",
        back_populates="deal",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="deal")
