"""Lightweight graph run persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class GraphRun(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Stored result for a graph workflow run."""

    __tablename__ = "graph_runs"

    graph_name: Mapped[str] = mapped_column(String(100), nullable=False)
    deal_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("deals.id", ondelete="SET NULL"),
        nullable=True,
    )
    result: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
