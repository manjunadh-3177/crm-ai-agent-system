"""Email draft model."""

from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class EmailDraft(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stored AI-generated email draft."""

    __tablename__ = "email_drafts"

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
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    team: Mapped["Team"] = relationship("Team")
    contact: Mapped["Contact"] = relationship("Contact")
    deal: Mapped["Deal | None"] = relationship("Deal")
    approvals: Mapped[list["AgentApproval"]] = relationship(
        "AgentApproval",
        back_populates="draft",
    )
