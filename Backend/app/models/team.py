"""Team model."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Team(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant root for CRM data."""

    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False)

    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="team",
        cascade="all, delete-orphan",
    )
    contacts: Mapped[list["Contact"]] = relationship(
        "Contact",
        back_populates="team",
        cascade="all, delete-orphan",
    )
    accounts: Mapped[list["Account"]] = relationship(
        "Account",
        back_populates="team",
        cascade="all, delete-orphan",
    )
    deal_stages: Mapped[list["DealStage"]] = relationship(
        "DealStage",
        back_populates="team",
        cascade="all, delete-orphan",
    )
    deals: Mapped[list["Deal"]] = relationship(
        "Deal",
        back_populates="team",
        cascade="all, delete-orphan",
    )
    products: Mapped[list["Product"]] = relationship(
        "Product",
        back_populates="team",
        cascade="all, delete-orphan",
    )
    deal_line_items: Mapped[list["DealLineItem"]] = relationship(
        "DealLineItem",
        back_populates="team",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="team",
        cascade="all, delete-orphan",
    )
