"""Services for admin agent activity views."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog
from app.services.audit import list_audit_logs_by_actions


FOLLOWUP_AGENT_ACTIONS = [
    "agent.followup.triggered",
    "agent.followup.no_action",
    "agent.followup.draft_created",
]


async def list_followup_agent_logs(db: AsyncSession, *, team_id: UUID, limit: int = 20) -> list[AuditLog]:
    """Return recent FollowUpAgent audit rows."""
    return await list_audit_logs_by_actions(db, FOLLOWUP_AGENT_ACTIONS, team_id=team_id, limit=limit)
