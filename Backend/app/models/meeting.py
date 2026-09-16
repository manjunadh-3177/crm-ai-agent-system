"""Meeting model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Meeting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Meeting/Calendar event within a team."""

    __tablename__ = "meetings"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_meetings_ends_after_starts"),
    )

    team_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, default="UTC")
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="scheduled"
    )  # scheduled, completed, cancelled
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    meeting_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="internal"
    )  # call, demo, followup, internal
    reminder_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    contact_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    deal_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("deals.id", ondelete="SET NULL"),
        nullable=True,
    )
    account_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )

    team: Mapped["Team"] = relationship("Team")
    contact: Mapped["Contact | None"] = relationship("Contact")
    deal: Mapped["Deal | None"] = relationship("Deal")
    account: Mapped["Account | None"] = relationship("Account")
