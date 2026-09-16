"""Human-in-the-loop approval records for AI drafts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AgentApproval(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Approval gate for external-facing AI actions."""

    __tablename__ = "agent_approvals"

    type: Mapped[str] = mapped_column(String(50), nullable=False, default="email")
    team_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    contact_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    deal_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("deals.id", ondelete="SET NULL"),
        nullable=True,
    )
    draft_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("email_drafts.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    execution_detail: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    team: Mapped[Team] = relationship("Team")
    contact: Mapped[Contact] = relationship("Contact")
    deal: Mapped[Deal | None] = relationship("Deal")
    draft: Mapped[EmailDraft] = relationship("EmailDraft", back_populates="approvals")
