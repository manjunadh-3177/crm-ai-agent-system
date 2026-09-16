"""Notification model for the Notification Center."""

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class Notification(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """In-app notification record for a team member."""

    __tablename__ = "notifications"

    team_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # user_id is stored as a string to match how user IDs are stored elsewhere
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    type: Mapped[str] = mapped_column(String(64), nullable=False)
    # e.g. "approval.pending", "deal.stalled", "task.overdue", "email.failed",
    #      "meeting.today", "nurture.suggested", "lead.hot"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional link to the source entity
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    team: Mapped["Team"] = relationship("Team")
