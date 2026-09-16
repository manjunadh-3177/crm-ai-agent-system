"""DealContactRole model."""

from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DealContactRole(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Links a deal to multiple contacts with specific roles."""

    __tablename__ = "deal_contact_roles"
    __table_args__ = (
        UniqueConstraint("deal_id", "contact_id", name="uq_deal_contact"),
    )

    team_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    deal_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("deals.id", ondelete="CASCADE"),
        nullable=False,
    )
    contact_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)

    team: Mapped["Team"] = relationship("Team")
    deal: Mapped["Deal"] = relationship("Deal", back_populates="stakeholders")
    contact: Mapped["Contact"] = relationship("Contact")
