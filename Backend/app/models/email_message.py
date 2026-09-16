"""Email Message model for tracking sent/failed emails."""

from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class EmailMessage(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Tracks outbound email communications."""

    __tablename__ = "email_messages"

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
    deal_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("deals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    approval_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("agent_approvals.id", ondelete="SET NULL"),
        nullable=True,
    )

    direction: Mapped[str] = mapped_column(String(32), nullable=False, default="outbound")
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False)  # sent, failed
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    team: Mapped["Team"] = relationship("Team")
    contact: Mapped["Contact | None"] = relationship("Contact")
    deal: Mapped["Deal | None"] = relationship("Deal")
