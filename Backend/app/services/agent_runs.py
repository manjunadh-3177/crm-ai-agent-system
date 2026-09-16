"""Persistence helpers for agent graph runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentRun, AuditLog
from app.schemas.graphs import AgentRunLogRead


async def create_agent_run(
    db: AsyncSession,
    *,
    team_id: UUID,
    graph_name: str,
    event_name: str,
    deal_id: UUID | None,
    status_value: str,
    result: str,
    duration_ms: int,
) -> AgentRun:
    """Persist a graph workflow run."""
    row = AgentRun(
        team_id=team_id,
        graph_name=graph_name,
        event_name=event_name,
        deal_id=deal_id,
        status=status_value,
        result=result,
        duration_ms=duration_ms,
    )
    db.add(row)
    await db.flush()
    return row


async def list_agent_runs(
    db: AsyncSession,
    *,
    team_id: UUID,
    graph_name: str | None = None,
    graph_names: list[str] | None = None,
    limit: int = 20,
) -> list[AgentRun]:
    """Return recent graph runs newest first."""
    query = select(AgentRun).where(AgentRun.team_id == team_id)
    if graph_names:
        query = query.where(AgentRun.graph_name.in_(graph_names))
    elif graph_name is not None:
        query = query.where(AgentRun.graph_name == graph_name)

    result = await db.execute(query.order_by(AgentRun.created_at.desc()).limit(limit))
    runs = list(result.scalars().all())
    await _hydrate_agent_runs(db, runs, team_id=team_id)
    return runs


async def get_agent_run_or_404(db: AsyncSession, run_id: UUID, *, team_id: UUID) -> AgentRun:
    """Return a single run or raise 404."""
    result = await db.execute(select(AgentRun).where(AgentRun.id == run_id, AgentRun.team_id == team_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found.",
        )
    await _hydrate_agent_runs(db, [run], team_id=team_id)
    return run


async def _hydrate_agent_runs(db: AsyncSession, runs: list[AgentRun], *, team_id: UUID) -> None:
    if not runs:
        return

    run_id_strings = {str(run.id) for run in runs}
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.team_id == team_id)
        .order_by(AuditLog.created_at.desc())
        .limit(500)
    )
    audit_logs = list(result.scalars().all())

    logs_by_run_id: dict[str, list[AgentRunLogRead]] = {run_id: [] for run_id in run_id_strings}
    approval_by_run_id: dict[str, UUID | None] = {}

    for log in audit_logs:
        metadata = log.metadata_json or {}
        run_id = metadata.get("run_id")
        if run_id not in run_id_strings:
            continue

        message = _extract_log_message(log.action, metadata)
        logs_by_run_id.setdefault(run_id, []).append(
            AgentRunLogRead(
                time=log.created_at,
                action=log.action,
                message=message,
            )
        )

        approval_id = metadata.get("approval_id")
        if approval_id and run_id not in approval_by_run_id:
            try:
                approval_by_run_id[run_id] = UUID(str(approval_id))
            except ValueError:
                approval_by_run_id[run_id] = None

    for run in runs:
        run_id = str(run.id)
        setattr(run, "logs", sorted(logs_by_run_id.get(run_id, []), key=lambda item: item.time, reverse=True))
        setattr(run, "approval_id", approval_by_run_id.get(run_id))


def _extract_log_message(action: str, metadata: dict[str, Any]) -> str:
    logs = metadata.get("logs")
    if isinstance(logs, list) and logs:
        latest = logs[-1]
        if isinstance(latest, str) and latest.strip():
            return latest

    reason = metadata.get("reason")
    if isinstance(reason, str) and reason.strip():
        return reason

    result = metadata.get("result")
    if isinstance(result, str) and result.strip():
        return result

    graph_name = metadata.get("graph_name")
    if isinstance(graph_name, str) and graph_name.strip():
        return graph_name

    return action
