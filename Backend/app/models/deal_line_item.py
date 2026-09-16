"""Deal line item model."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DealLineItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A product attached to a deal."""

    __tablename__ = "deal_line_items"

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
    product_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    team: Mapped["Team"] = relationship("Team", back_populates="deal_line_items")
    deal: Mapped["Deal"] = relationship("Deal", back_populates="line_items")
    product: Mapped["Product"] = relationship("Product", back_populates="line_items")
