"""API v1 router aggregation."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import get_ai_health
from app.core.auth import AuthContext, get_auth_context, requires_role
from app.core.db import get_db
from app.jobs import (
    enqueue_background_job,
    get_job_snapshot,
    get_worker_status_snapshot,
    list_team_jobs_snapshot,
)
from app.models import AgentRun, AuditLog, Notification
from app.routers.api.accounts import router as accounts_router
from app.routers.api.activity import router as activity_router
from app.routers.api.automations import router as automations_router
from app.routers.api.contacts import router as contacts_router
from app.routers.api.deals import router as deals_router
from app.routers.api.emails import router as emails_router
from app.routers.api.import_export import router as import_export_router
from app.routers.api.meetings import router as meetings_router
from app.routers.api.notes import router as notes_router
from app.routers.api.notifications import router as notifications_router
from app.routers.api.products import router as products_router
from app.routers.api.reports import router as reports_router
from app.routers.api.sms import router as sms_router
from app.routers.api.stages import router as stages_router
from app.routers.api.tasks import router as tasks_router
from app.routers.api.teams import router as teams_router
from app.schemas.crm import ProposalDraftResponse
from app.services.agent_runs import list_agent_runs
from app.services.swarm_agents import run_swarm_agent

router = APIRouter(prefix="/api/v1")
router.include_router(teams_router)
router.include_router(contacts_router)
router.include_router(accounts_router)
router.include_router(deals_router)
router.include_router(import_export_router)
router.include_router(products_router)
router.include_router(reports_router)
router.include_router(sms_router)
router.include_router(stages_router)
router.include_router(meetings_router)
router.include_router(tasks_router)
router.include_router(notes_router)
router.include_router(activity_router)
router.include_router(automations_router)
router.include_router(emails_router)
router.include_router(notifications_router)


@router.get("/worker/status")
async def get_worker_status(
    auth: AuthContext = Depends(get_auth_context),
) -> dict:
    """Return Redis/queue health for the current API environment."""
    del auth
    return await get_worker_status_snapshot()


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    auth: AuthContext = Depends(get_auth_context),
) -> dict:
    """Return background job metadata when it belongs to the current team."""
    snapshot = await get_job_snapshot(job_id, team_id=auth.team_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return snapshot


@router.get("/swarm/status")
async def get_swarm_status(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(requires_role("admin")),
) -> dict:
    """Return a live agent and platform status snapshot for the Swarm Console."""
    logs = await _list_recent_team_logs(db, team_id=auth.team_id, limit=500)
    runs = await list_agent_runs(
        db,
        team_id=auth.team_id,
        graph_names=[*list(_agent_configs().keys()), *_workflow_graph_names()],
        limit=120,
    )
    queue_snapshot = await list_team_jobs_snapshot(auth.team_id, limit=20)
    ai_health = get_ai_health()

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "health": {
            "redis": queue_snapshot["health"].get("redis", "unknown"),
            "workers": queue_snapshot["health"].get("workers", "unknown"),
            "queue_enabled": queue_snapshot["health"].get("queue_enabled", False),
            "running_count": queue_snapshot["health"].get("running_count", 0),
            "queued_count": queue_snapshot["health"].get("queued_count", 0),
            "worker_heartbeat": queue_snapshot["health"].get("worker_heartbeat"),
            "ai": ai_health.get("status", "unknown"),
            "provider": ai_health.get("provider"),
            "model": ai_health.get("model"),
        },
        "agents": [_build_agent_snapshot(name, config, logs, runs, queue_snapshot) for name, config in _agent_configs().items()],
        "graph_runs": [_graph_run_history_item(run, logs) for run in runs if run.graph_name in _workflow_graph_names()][:20],
    }


@router.get("/swarm/events")
async def get_swarm_events(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(requires_role("admin")),
) -> list[dict]:
    """Return recent autonomous activity for the Swarm Console feed."""
    logs = await _list_recent_team_logs(db, team_id=auth.team_id, limit=80)
    notifications = await _list_recent_notifications(db, team_id=auth.team_id, limit=20)

    events: list[dict] = []
    for log in logs:
        event = _audit_log_to_swarm_event(log)
        if event:
            events.append(event)

    for notification in notifications:
        events.append(
            {
                "id": f"notification:{notification.id}",
                "source": "notification",
                "type": notification.type,
                "message": f"{notification.title}: {notification.message}",
                "created_at": notification.created_at,
                "level": "info",
            }
        )

    events.sort(key=lambda item: item["created_at"], reverse=True)
    return events[:30]


@router.get("/swarm/jobs")
async def get_swarm_jobs(
    auth: AuthContext = Depends(requires_role("admin")),
) -> dict:
    """Return queue health and recent ARQ jobs for the Swarm Console."""
    return await list_team_jobs_snapshot(auth.team_id, limit=20)


@router.post("/swarm/agents/{agent_name}/run")
async def run_swarm_agent_endpoint(
    agent_name: str,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(requires_role("admin")),
) -> dict:
    """Manually run one CRM Swarm agent for the current tenant."""
    try:
        return await run_swarm_agent(db, agent_name=agent_name, team_id=auth.team_id, actor_id=auth.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/ai/opportunity-watch/run")
async def run_opportunity_watch_endpoint(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(requires_role("admin", "manager")),
) -> dict:
    """Run OpportunityWatchAgent for the current team."""
    queue_result = await enqueue_background_job(
        "opportunity_watch_job",
        str(auth.team_id),
        auth.user_id,
        trigger="manual",
    )
    if queue_result.get("queued"):
        return {"status": "queued", "job_id": queue_result["job_id"]}

    from app.ai.agents.opportunity_watch_agent import run_opportunity_watch

    return await run_opportunity_watch(db, team_id=auth.team_id, actor_id=auth.user_id, trigger="manual")


@router.post("/ai/proposal/generate/{deal_id}", response_model=ProposalDraftResponse)
async def generate_ai_proposal_endpoint(
    deal_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> ProposalDraftResponse:
    """Run ProposalAgent for a deal and return the draft."""
    from fastapi import HTTPException

    from app.ai.agents.proposal_agent import run_proposal_agent

    draft = await run_proposal_agent(
        db,
        deal_id=deal_id,
        team_id=auth.team_id,
        actor_id=auth.user_id,
        trigger="manual",
        force=True,
    )
    if draft is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Proposal generation failed.")
    return draft


def _agent_configs() -> dict[str, dict[str, set[str] | str | None]]:
    return {
        "LeadQualifierAgent": {
            "success_actions": {"agent.lead_qualified", "agent.lead_qualifier.manual_run"},
            "failure_actions": {"agent.lead_qualifier.manual_run_failed"},
            "job_function": None,
        },
        "ResearchAgent": {
            "success_actions": {"agent.research.completed", "agent.research_completed", "agent.research.manual_run"},
            "failure_actions": {"agent.research.failed", "agent.research.manual_run_failed"},
            "job_function": "research_job",
        },
        "NurturerAgent": {
            "success_actions": {"agent.nurturer_triggered", "agent.auto_contact_draft_created", "agent.nurturer.manual_run"},
            "failure_actions": {"agent.nurturer_failed", "agent.nurturer.manual_run_failed"},
            "job_function": "nurture_scan_job",
        },
        "SchedulerAgent": {
            "success_actions": {"agent.scheduler_suggested", "meeting.created_via_scheduler", "agent.scheduler.manual_run"},
            "failure_actions": {"agent.scheduler_failed", "agent.scheduler.manual_run_failed"},
            "job_function": None,
        },
        "DealOrchestratorAgent": {
            "success_actions": {"agent.deal_orchestrated", "agent.deal_orchestrator.manual_run"},
            "failure_actions": {"agent.deal_orchestrator_failed", "agent.deal_orchestrator.manual_run_failed"},
            "job_function": None,
        },
        "ComplianceAgent": {
            "success_actions": {"agent.compliance.passed", "agent.compliance.manual_run"},
            "failure_actions": {"agent.compliance.blocked", "email.execution_blocked", "agent.compliance.manual_run_failed"},
            "job_function": None,
        },
        "OpportunityWatchAgent": {
            "success_actions": {"agent.opportunity_watch.completed", "agent.opportunity_watch.alert", "agent.opportunity_watch.manual_run"},
            "failure_actions": {"agent.opportunity_watch.failed", "agent.opportunity_watch.manual_run_failed"},
            "job_function": "opportunity_watch_job",
        },
        "ProposalAgent": {
            "success_actions": {"agent.proposal.generated", "proposal.generated", "agent.proposal.skipped", "agent.proposal.manual_run"},
            "failure_actions": {"agent.proposal.failed", "agent.proposal.manual_run_failed"},
            "job_function": "proposal_job",
        },
    }


def _workflow_graph_names() -> list[str]:
    return ["NewLeadGraph", "DealRescueGraph", "ProposalGraph"]


async def _list_recent_team_logs(db: AsyncSession, *, team_id: UUID, limit: int) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog).where(AuditLog.team_id == team_id).order_by(AuditLog.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def _list_recent_notifications(db: AsyncSession, *, team_id: UUID, limit: int) -> list[Notification]:
    result = await db.execute(
        select(Notification)
        .where(Notification.team_id == team_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


def _build_agent_snapshot(name: str, config: dict, logs: list[AuditLog], runs: list[AgentRun], queue_snapshot: dict) -> dict:
    relevant_actions = config["success_actions"] | config["failure_actions"]
    agent_logs = [log for log in logs if log.action in relevant_actions]
    agent_runs = [run for run in runs if run.graph_name == name]
    now = datetime.now(UTC)
    today = now.date()
    last_log = agent_logs[0] if agent_logs else None
    last_run = agent_runs[0] if agent_runs else None

    last_success = next((log for log in agent_logs if log.action in config["success_actions"]), None)
    last_error = next((log for log in agent_logs if log.action in config["failure_actions"]), None)

    success_count = sum(1 for log in agent_logs if log.action in config["success_actions"])
    failure_count = sum(1 for log in agent_logs if log.action in config["failure_actions"])
    runs_today = sum(1 for run in agent_runs if run.created_at.date() == today) or sum(1 for log in agent_logs if log.created_at.date() == today)

    is_running = False
    job_func = config.get("job_function")
    if job_func:
        for job in queue_snapshot.get("queued_jobs", []):
            if job.get("function") == job_func:
                is_running = True
                break
        for job in queue_snapshot.get("running_jobs", []):
            if job.get("function") == job_func:
                is_running = True
                break

    status_value = "idle"
    if is_running:
        status_value = "running"
    elif last_error and (not last_success or last_error.created_at > last_success.created_at):
        if (now - last_error.created_at).total_seconds() < 86400:
            status_value = "error"
    elif last_success and (now - last_success.created_at).total_seconds() < 86400:
        status_value = "success"

    return {
        "name": name,
        "status": status_value,
        "last_run_at": last_run.created_at if last_run else (last_log.created_at if last_log else None),
        "last_trigger": last_run.event_name if last_run else ("event" if last_log else "Never"),
        "last_action": _describe_agent_action(last_log) if last_log else "No activity yet.",
        "last_output": _last_manual_output(last_run, agent_logs) if last_run else (_describe_agent_action(last_log) if last_log else "No output yet."),
        "runs_today": runs_today,
        "success_count": success_count,
        "failure_count": failure_count,
        "run_history": [_run_history_item(run, agent_logs) for run in agent_runs[:5]],
    }


def _run_history_item(run: AgentRun, logs: list[AuditLog]) -> dict:
    matching_log = next((log for log in logs if (log.metadata_json or {}).get("run_id") == str(run.id)), None)
    metadata = matching_log.metadata_json if matching_log else {}
    return {
        "run_id": str(run.id),
        "current_node": metadata.get("current_node"),
        "completed_nodes": metadata.get("completed_nodes") or [],
        "failed_node": metadata.get("failed_node"),
        "duration": run.duration_ms,
        "final_result": metadata.get("final_result") or run.result,
        "status": run.status,
        "trigger": run.event_name,
        "output": metadata.get("summary") or run.result,
        "records_affected": metadata.get("records_affected"),
        "created_at": run.created_at,
    }


def _graph_run_history_item(run: AgentRun, logs: list[AuditLog]) -> dict:
    return {
        **_run_history_item(run, logs),
        "graph_name": run.graph_name,
    }


def _last_manual_output(run: AgentRun, logs: list[AuditLog]) -> str:
    matching = next((log for log in logs if (log.metadata_json or {}).get("run_id") == str(run.id)), None)
    if matching:
        summary = (matching.metadata_json or {}).get("summary")
        if summary:
            return str(summary)
    return run.result


def _describe_agent_action(log: AuditLog) -> str:
    metadata = log.metadata_json or {}
    if log.action in {"agent.research.completed", "agent.research_completed"}:
        return f"Enriched {metadata.get('contact_name') or metadata.get('account_name') or metadata.get('entity_name') or 'record'}"
    if log.action == "agent.nurturer_triggered":
        return "Created a nurture approval draft."
    if log.action == "agent.auto_contact_draft_created":
        return "Queued a welcome outreach approval."
    if log.action == "agent.scheduler_suggested":
        return "Suggested meeting slots."
    if log.action == "meeting.created_via_scheduler":
        return "Booked a meeting from scheduler suggestions."
    if log.action == "agent.deal_orchestrated":
        return "Reviewed deal health and orchestration rules."
    if log.action == "agent.compliance.passed":
        return "Cleared an outreach draft for approval."
    if log.action in {"agent.compliance.blocked", "email.execution_blocked"}:
        return "Blocked an outreach because of compliance rules."
    if log.action == "agent.lead_qualified":
        return "Qualified a newly created lead."
    if log.action == "agent.opportunity_watch.completed":
        return f"Scanned opportunities and created {metadata.get('signals_created', 0)} signal(s)."
    if log.action == "agent.opportunity_watch.alert":
        return f"Flagged opportunity: {metadata.get('next_best_action') or metadata.get('kind') or 'review needed'}"
    if log.action == "agent.proposal.generated":
        return f"Generated proposal draft {metadata.get('title') or ''}".strip()
    if log.action == "agent.proposal.skipped":
        return "Skipped proposal generation because a draft already exists."
    if log.action.endswith(".manual_run"):
        return str((log.metadata_json or {}).get("summary") or "Manual agent run completed.")
    return log.action


def _audit_log_to_swarm_event(log: AuditLog) -> dict | None:
    metadata = log.metadata_json or {}
    if log.action.endswith(".manual_run") or log.action.endswith(".manual_run_failed"):
        return {
            "id": f"audit:{log.id}",
            "source": "audit",
            "type": log.action,
            "message": f"{metadata.get('agent_name') or 'Agent'}: {metadata.get('summary') or log.action}",
            "created_at": log.created_at,
            "level": "error" if log.action.endswith("_failed") else "info",
        }

    message_map = {
        "agent.lead_qualified": "LeadQualifierAgent qualified a new contact.",
        "agent.research.completed": f"ResearchAgent enriched {metadata.get('contact_name') or metadata.get('account_name') or 'a record'}.",
        "agent.research_completed": f"ResearchAgent enriched {metadata.get('contact_name') or metadata.get('account_name') or 'a record'}.",
        "agent.nurturer_triggered": "NurturerAgent created an approval draft.",
        "agent.auto_contact_draft_created": "Auto contact draft queued for approval.",
        "agent.scheduler_suggested": "SchedulerAgent suggested new meeting slots.",
        "meeting.created_via_scheduler": "SchedulerAgent booked a meeting.",
        "agent.deal_orchestrated": "DealOrchestratorAgent reviewed a deal.",
        "agent.compliance.passed": "ComplianceAgent approved a draft path.",
        "agent.compliance.blocked": "ComplianceAgent blocked a draft path.",
        "agent.opportunity_watch.completed": f"OpportunityWatchAgent scanned opportunities and created {metadata.get('signals_created', 0)} signal(s).",
        "agent.opportunity_watch.alert": f"OpportunityWatchAgent flagged a deal: {metadata.get('next_best_action') or metadata.get('kind') or 'review needed'}.",
        "agent.proposal.generated": f"ProposalAgent generated {metadata.get('title') or 'a proposal draft'}.",
        "agent.proposal.skipped": "ProposalAgent skipped generation because a draft already exists.",
        "agent.proposal.failed": "ProposalAgent failed to generate a proposal.",
        "email.executed": "send_email_job completed successfully.",
        "email.failed": "send_email_job failed.",
        "import.completed": "csv_import_job completed.",
        "import.started": "csv_import_job started.",
        "approval.created": "Approval created for review.",
        "approval.approved": "Approval approved and queued for send.",
        "approval.rejected": "Approval rejected.",
    }
    if log.action not in message_map and not log.action.startswith(("agent.", "email.", "approval.", "import.")):
        return None

    return {
        "id": f"audit:{log.id}",
        "source": "audit",
        "type": log.action,
        "message": message_map.get(log.action, log.action),
        "created_at": log.created_at,
        "level": "error" if "failed" in log.action or "blocked" in log.action else "info",
    }


@router.post("/debug/test-email")
async def send_test_email(
    auth: AuthContext = Depends(get_auth_context),
) -> dict:
    """Dev endpoint: sends a test email directly to EMAIL_REDIRECT_TO bypassing all approval logic."""
    from app.core.config import get_settings
    from app.services.ai_approvals import UNSUBSCRIBE_FOOTER, _send_approved_email

    settings = get_settings()
    target = (settings.email_redirect_to or "").strip() if settings.email_redirect_enabled else None

    if not target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="EMAIL_REDIRECT_ENABLED=true and EMAIL_REDIRECT_TO must be set to use this endpoint.",
        )

    body = (
        "<h2>Acufy CRM — Email Delivery Test</h2>"
        "<p>This is a direct delivery test sent from the <code>/api/v1/debug/test-email</code> endpoint.</p>"
        "<ul>"
        f"<li><strong>Provider:</strong> {settings.email_provider}</li>"
        f"<li><strong>From:</strong> {settings.email_from}</li>"
        f"<li><strong>To (redirect):</strong> {target}</li>"
        f"<li><strong>Actor:</strong> {auth.user_id}</li>"
        "</ul>"
        "<p>If you received this email, the Resend integration is working correctly.</p>"
        + UNSUBSCRIBE_FOOTER.format(unsubscribe_url="http://127.0.0.1:5173/unsubscribe?token=test").replace("\n", "<br>")
    )

    result = await _send_approved_email(
        to_email=target,
        subject="[Acufy CRM] Email Delivery Test",
        body=body,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Email send FAILED: {result.detail}",
        )

    return {
        "status": "delivered",
        "to": target,
        "provider": result.provider,
        "message_id": result.message_id,
        "detail": result.detail,
    }
