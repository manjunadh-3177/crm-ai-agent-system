"""Admin utility routes."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthContext, get_auth_context, requires_role
from app.core.db import get_db
from app.schemas.admin import AuditLogRead
from app.schemas.graphs import AgentRunRead
from app.services.agent_activity import list_followup_agent_logs
from app.services.agent_runs import get_agent_run_or_404, list_agent_runs
from app.services.audit import list_audit_logs
from app.services.seeder import seed_current_workspace


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-logs", response_model=list[AuditLogRead])
async def get_audit_logs(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(requires_role("admin")),
) -> list[AuditLogRead]:
    """Return audit logs newest first."""
    return await list_audit_logs(db, team_id=auth.team_id)


@router.get("/agents/followup/logs", response_model=list[AuditLogRead])
async def get_followup_agent_logs(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(requires_role("admin")),
) -> list[AuditLogRead]:
    """Return recent FollowUpAgent audit actions."""
    return await list_followup_agent_logs(db, team_id=auth.team_id)


@router.get("/graphs/followup/runs", response_model=list[AgentRunRead])
async def get_followup_graph_runs(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(requires_role("admin")),
) -> list[AgentRunRead]:
    """Return recent follow-up graph runs."""
    return await list_agent_runs(
        db,
        team_id=auth.team_id,
        graph_names=["followup_graph", "swarm_followup"],
    )


@router.get("/graphs/followup/runs/{run_id}", response_model=AgentRunRead)
async def get_followup_graph_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(requires_role("admin")),
) -> AgentRunRead:
    """Return a single follow-up graph run."""
    return await get_agent_run_or_404(db, run_id, team_id=auth.team_id)

@router.post("/seed-current-workspace")
async def seed_workspace_route(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> dict:
    """Seed the current user's workspace with demo data."""
    return await seed_current_workspace(db, team_id=auth.team_id, user_id=auth.user_id)
