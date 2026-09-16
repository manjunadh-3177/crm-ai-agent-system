"""Document metadata model."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Metadata row for generated CRM documents."""

    __tablename__ = "documents"

    team_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    deal_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("deals.id", ondelete="SET NULL"),
        nullable=True,
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
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, default="proposal")
    content_format: Mapped[str] = mapped_column(String(20), nullable=False, default="markdown")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")

    team: Mapped[Team] = relationship("Team", back_populates="documents")
    deal: Mapped[Deal | None] = relationship("Deal", back_populates="documents")
    contact: Mapped[Contact | None] = relationship("Contact")
    account: Mapped[Account | None] = relationship("Account")
