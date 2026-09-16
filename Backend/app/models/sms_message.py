"""SMS message model for Twilio-backed messaging history."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class SMSMessage(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Tracks inbound and outbound SMS conversations."""

    __tablename__ = "sms_messages"

    team_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False, default="outbound")
    thread_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    from_number: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    to_number: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="Queued")
    provider_sid: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)

    team: Mapped["Team"] = relationship("Team")
    contact: Mapped["Contact | None"] = relationship("Contact")
