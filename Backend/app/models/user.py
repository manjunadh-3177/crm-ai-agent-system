"""User model."""

from enum import Enum
from uuid import UUID

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class UserRole(str, Enum):
    """Allowed CRM user roles."""

    ADMIN = "admin"
    MANAGER = "manager"
    REP = "rep"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """CRM user belonging to a team."""

    __tablename__ = "users"

    team_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.REP,
    )

    team: Mapped["Team"] = relationship("Team", back_populates="users")
    owned_deals: Mapped[list["Deal"]] = relationship("Deal", back_populates="owner")
