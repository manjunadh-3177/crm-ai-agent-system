"""Task model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """CRM task within a team."""

    __tablename__ = "tasks"

    team_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[str] = mapped_column(
        String(10), nullable=False, default="med"
    )  # low, med, high
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open"
    )  # open, done, cancelled

    assigned_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

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
