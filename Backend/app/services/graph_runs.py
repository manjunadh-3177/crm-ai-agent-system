"""Services for graph run persistence and retrieval."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GraphRun


async def create_graph_run(
    db: AsyncSession,
    *,
    graph_name: str,
    deal_id: UUID | None,
    result: str,
    duration_ms: int,
) -> GraphRun:
    """Persist a workflow graph run."""
    row = GraphRun(
        graph_name=graph_name,
        deal_id=deal_id,
        result=result,
        duration_ms=duration_ms,
    )
    db.add(row)
    await db.flush()
    return row


async def list_graph_runs(db: AsyncSession, *, graph_name: str, limit: int = 20) -> list[GraphRun]:
    """Return recent graph runs newest first."""
    result = await db.execute(
        select(GraphRun)
        .where(GraphRun.graph_name == graph_name)
        .order_by(GraphRun.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
