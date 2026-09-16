"""ARQ-backed background jobs and queue helpers."""

from __future__ import annotations

import base64
import logging
import re
from typing import Any
from uuid import UUID

from redis.asyncio import from_url as redis_from_url
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.services.notifications import create_notification

try:  # pragma: no cover - optional dependency at runtime
    from arq import create_pool
    from arq.connections import RedisSettings
    from arq.jobs import Job

    ARQ_AVAILABLE = True
except ImportError:  # pragma: no cover - graceful fallback when arq is unavailable
    create_pool = None
    RedisSettings = None
    Job = None
    ARQ_AVAILABLE = False


logger = logging.getLogger("acufy.jobs")
IMPORT_QUEUE_THRESHOLD_BYTES = 128_000
SWARM_JOB_FUNCTIONS = {
    "send_email_job",
    "crm_graph_job",
    "auto_contact_draft_job",
    "nurture_scan_job",
    "research_job",
    "csv_import_job",
    "notification_job",
    "opportunity_watch_job",
    "proposal_job",
    "send_sms_job",
}


def _redis_dsn() -> str:
    settings = get_settings()
    return settings.redis_url or "redis://localhost:6379"


def _redis_settings() -> Any:
    if not ARQ_AVAILABLE or RedisSettings is None:
        return None
    return RedisSettings.from_dsn(_redis_dsn())


async def _create_arq_pool() -> Any | None:
    if not ARQ_AVAILABLE or create_pool is None:
        return None
    return await create_pool(_redis_settings())


async def get_worker_status_snapshot() -> dict[str, Any]:
    """Return a lightweight queue/Redis health snapshot."""
    if not ARQ_AVAILABLE:
        return {
            "status": "unavailable",
            "redis": "unknown",
            "arq": "missing",
            "queue_enabled": False,
        }

    try:
        client = redis_from_url(_redis_dsn(), decode_responses=True)
        pong = await client.ping()
        await client.aclose()
        return {
            "status": "ok" if pong else "degraded",
            "redis": "connected" if pong else "unreachable",
            "arq": "available",
            "queue_enabled": bool(pong),
        }
    except Exception as exc:  # pragma: no cover - network dependent
        return {
            "status": "degraded",
            "redis": "unreachable",
            "arq": "available",
            "queue_enabled": False,
            "detail": str(exc),
        }


async def enqueue_background_job(function_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Try to enqueue an ARQ job and fail gracefully when Redis/ARQ is unavailable."""
    pool = await _create_arq_pool()
    if pool is None:
        return {"queued": False, "reason": "arq_unavailable"}

    try:
        job = await pool.enqueue_job(function_name, *args, **kwargs)
    except Exception as exc:  # pragma: no cover - network dependent
        logger.warning("Failed to enqueue job %s: %s", function_name, exc)
        await pool.aclose()
        return {"queued": False, "reason": str(exc)}

    await pool.aclose()
    if job is None:
        return {"queued": False, "reason": "enqueue_returned_none"}
    return {"queued": True, "job_id": job.job_id}


async def get_job_snapshot(job_id: str, *, team_id: UUID) -> dict[str, Any] | None:
    """Return job metadata when it belongs to the current team."""
    if not ARQ_AVAILABLE or Job is None:
        return None

    pool = await _create_arq_pool()
    if pool is None:
        return None

    try:
        job = Job(job_id, pool)
        status = await job.status()
        info = await job.info()
        result_info = await job.result_info()

        team_matches = _job_matches_team(info, team_id) or _job_matches_team(result_info, team_id)

        if not team_matches:
            return None

        return {
            "job_id": job_id,
            "status": getattr(status, "value", str(status)),
            "function": getattr(info, "function", None) or getattr(result_info, "function", None),
            "queue_name": getattr(info, "queue_name", None) or getattr(result_info, "queue_name", None),
            "enqueue_time": getattr(info, "enqueue_time", None) or getattr(result_info, "enqueue_time", None),
            "success": getattr(result_info, "success", None),
            "result": getattr(result_info, "result", None),
        }
    finally:
        await pool.aclose()


async def list_team_jobs_snapshot(team_id: UUID, *, limit: int = 20) -> dict[str, Any]:
    """Return a queue snapshot for the current tenant."""
    worker_status = await get_worker_status_snapshot()
    snapshot: dict[str, Any] = {
        "health": {
            **worker_status,
            "workers": "unknown",
            "running_count": 0,
            "queued_count": 0,
        },
        "counts": {
            "queued": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
        },
        "queued_jobs": [],
        "running_jobs": [],
        "completed_jobs": [],
    }

    runtime_health = await _get_worker_runtime_health()
    snapshot["health"].update(runtime_health)

    if not ARQ_AVAILABLE:
        return snapshot

    pool = await _create_arq_pool()
    if pool is None:
        return snapshot

    try:
        queued_jobs = await pool.queued_jobs()
        completed_jobs = await pool.all_job_results()
    except Exception as exc:  # pragma: no cover - network dependent
        logger.warning("Failed to inspect queue state: %s", exc)
        snapshot["health"]["detail"] = str(exc)
        return snapshot
    finally:
        await pool.aclose()

    queued_items = [
        _serialize_job_def(job)
        for job in queued_jobs
        if _job_matches_team(job, team_id) and job.function in SWARM_JOB_FUNCTIONS
    ]
    completed_items = [
        _serialize_job_result(job)
        for job in completed_jobs
        if _job_matches_team(job, team_id) and job.function in SWARM_JOB_FUNCTIONS
    ]
    completed_items.sort(key=lambda item: item.get("finish_time") or "", reverse=True)

    snapshot["queued_jobs"] = queued_items[:limit]
    snapshot["completed_jobs"] = completed_items[:limit]
    snapshot["counts"]["queued"] = len(queued_items)
    snapshot["counts"]["running"] = int(snapshot["health"].get("running_count") or 0)
    snapshot["counts"]["completed"] = sum(1 for item in completed_items if item["status"] == "completed")
    snapshot["counts"]["failed"] = sum(1 for item in completed_items if item["status"] == "failed")
    snapshot["health"]["queued_count"] = len(queued_items)
    return snapshot


async def _get_worker_runtime_health() -> dict[str, Any]:
    """Inspect ARQ worker heartbeat information when available."""
    try:
        client = redis_from_url(_redis_dsn(), decode_responses=True)
        raw_value = await client.get("arq:queue:health-check")
        ttl = await client.ttl("arq:queue:health-check")
        await client.aclose()
    except Exception as exc:  # pragma: no cover - network dependent
        return {
            "workers": "offline",
            "worker_heartbeat": None,
            "worker_detail": str(exc),
            "running_count": 0,
            "queued_count": 0,
        }

    if not raw_value or ttl <= 0:
        return {
            "workers": "offline",
            "worker_heartbeat": None,
            "running_count": 0,
            "queued_count": 0,
        }

    ongoing_match = re.search(r"j_ongoing=(\d+)", raw_value)
    queued_match = re.search(r"queued=(\d+)", raw_value)
    return {
        "workers": "online",
        "worker_heartbeat": raw_value,
        "running_count": int(ongoing_match.group(1)) if ongoing_match else 0,
        "queued_count": int(queued_match.group(1)) if queued_match else 0,
    }


def _job_matches_team(job_def: Any, team_id: UUID) -> bool:
    if not job_def:
        return False
    team_str = str(team_id)
    kwargs = getattr(job_def, "kwargs", {}) or {}
    if str(kwargs.get("team_id", "")) == team_str:
        return True
    args = getattr(job_def, "args", ()) or ()
    for arg in args:
        if str(arg) == team_str:
            return True
    return False


def _serialize_job_def(job: Any) -> dict[str, Any]:
    return {
        "job_id": getattr(job, "job_id", None),
        "function": getattr(job, "function", None),
        "status": "queued",
        "enqueue_time": getattr(job, "enqueue_time", None),
        "finish_time": None,
        "success": None,
        "result": None,
    }


def _serialize_job_result(job: Any) -> dict[str, Any]:
    return {
        "job_id": getattr(job, "job_id", None),
        "function": getattr(job, "function", None),
        "status": "completed" if getattr(job, "success", False) else "failed",
        "enqueue_time": getattr(job, "enqueue_time", None),
        "finish_time": getattr(job, "finish_time", None),
        "success": getattr(job, "success", None),
        "result": _summarize_job_result(getattr(job, "result", None)),
    }


def _summarize_job_result(result: Any) -> str | None:
    if result is None:
        return None
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("status", "reason", "message"):
            value = result.get(key)
            if value:
                return str(value)
        return str(result)[:160]
    return str(result)[:160]


async def _session_with_context(*, team_id: UUID, actor_id: str | None = None):
    session = AsyncSessionLocal()
    session.info["team_id"] = team_id
    session.info["user_id"] = actor_id
    await session.execute(text("SELECT set_config('app.current_team_id', :team_id, true)"), {"team_id": str(team_id)})
    await session.execute(
        text("SELECT set_config('app.current_user_id', :user_id, true)"),
        {"user_id": str(actor_id or "system")},
    )
    return session


async def send_email_job(ctx: dict[str, Any], approval_id: str, team_id: str, actor_id: str | None = None) -> dict[str, Any]:
    """Send an approved email in the background."""
    del ctx
    try:
        from app.services.ai_approvals import execute_email_approval_by_id

        team_uuid = UUID(team_id)
        async with await _session_with_context(team_id=team_uuid, actor_id=actor_id) as db:
            result = await execute_email_approval_by_id(
                db,
                approval_id=UUID(approval_id),
                team_id=team_uuid,
                actor_id=actor_id,
            )
            await db.commit()
            return result
    except Exception as exc:
        logger.exception("send_email_job failed")
        return {"status": "error", "reason": str(exc)}


async def crm_graph_job(
    ctx: dict[str, Any],
    graph_name: str,
    team_id: str,
    actor_id: str | None = None,
    contact_id: str | None = None,
    deal_id: str | None = None,
    trigger: str = "queued",
) -> dict[str, Any]:
    """Run a shared LangGraph CRM workflow in the background."""
    del ctx
    try:
        from app.ai.graphs.crm_orchestration import (
            DEAL_RESCUE_GRAPH,
            NEW_LEAD_GRAPH,
            PROPOSAL_GRAPH,
            run_deal_rescue_graph,
            run_new_lead_graph,
            run_proposal_graph,
        )

        team_uuid = UUID(team_id)
        async with await _session_with_context(team_id=team_uuid, actor_id=actor_id) as db:
            if graph_name == NEW_LEAD_GRAPH:
                if contact_id is None:
                    return {"status": "error", "reason": "contact_id_required"}
                return await run_new_lead_graph(
                    db,
                    contact_id=UUID(contact_id),
                    team_id=team_uuid,
                    actor_id=actor_id,
                    trigger=trigger,
                )
            if graph_name == DEAL_RESCUE_GRAPH:
                if deal_id is None:
                    return {"status": "error", "reason": "deal_id_required"}
                return await run_deal_rescue_graph(
                    db,
                    deal_id=UUID(deal_id),
                    team_id=team_uuid,
                    actor_id=actor_id,
                    trigger=trigger,
                )
            if graph_name == PROPOSAL_GRAPH:
                if deal_id is None:
                    return {"status": "error", "reason": "deal_id_required"}
                return await run_proposal_graph(
                    db,
                    deal_id=UUID(deal_id),
                    team_id=team_uuid,
                    actor_id=actor_id,
                    trigger=trigger,
                )
            return {"status": "error", "reason": "unsupported_graph"}
    except Exception as exc:
        logger.exception("crm_graph_job failed")
        return {"status": "error", "reason": str(exc)}


async def nurture_scan_job(ctx: dict[str, Any], team_id: str, actor_id: str | None = None) -> dict[str, Any]:
    """Run the nurturer scan in the background."""
    del ctx
    try:
        from app.ai.agents.nurturer_agent import run_nurturer_scan

        team_uuid = UUID(team_id)
        async with await _session_with_context(team_id=team_uuid, actor_id=actor_id) as db:
            result = await run_nurturer_scan(db, team_id=team_uuid, actor_id=actor_id)
            await db.commit()
            return result
    except Exception as exc:
        logger.exception("nurture_scan_job failed")
        return {"status": "error", "reason": str(exc)}


async def research_job(
    ctx: dict[str, Any],
    entity_type: str,
    entity_id: str,
    team_id: str,
) -> dict[str, Any]:
    """Run contact/account research in the background."""
    del ctx
    try:
        from app.ai.agents.research_agent import research_account, research_contact

        team_uuid = UUID(team_id)
        async with await _session_with_context(team_id=team_uuid, actor_id="ai") as db:
            if entity_type == "contact":
                result = await research_contact(db, UUID(entity_id), team_id=team_uuid)
            elif entity_type == "account":
                result = await research_account(db, UUID(entity_id), team_id=team_uuid)
            else:
                return {"status": "error", "reason": "unsupported_entity"}
            await db.commit()
            if result is None:
                return {"status": "skipped", "reason": "Insufficient data or LLM unavailable"}
            return {"status": "completed", **result}
    except Exception as exc:
        logger.exception("research_job failed")
        return {"status": "error", "reason": str(exc)}


async def csv_import_job(
    ctx: dict[str, Any],
    entity: str,
    file_name: str,
    content_b64: str,
    team_id: str,
    actor_id: str | None = None,
    column_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Process a CSV import from base64 content."""
    del ctx
    try:
        from app.services.import_export import run_import_from_bytes

        team_uuid = UUID(team_id)
        content = base64.b64decode(content_b64.encode("utf-8"))
        async with await _session_with_context(team_id=team_uuid, actor_id=actor_id) as db:
            result = await run_import_from_bytes(
                db,
                entity=entity,
                filename=file_name,
                content=content,
                team_id=team_uuid,
                actor_id=actor_id,
                column_map=column_map,
            )
            await db.commit()
            return result.model_dump()
    except Exception as exc:
        logger.exception("csv_import_job failed")
        return {"status": "error", "reason": str(exc)}


async def notification_job(
    ctx: dict[str, Any],
    team_id: str,
    title: str,
    message: str,
    notification_type: str = "system.info",
    user_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> dict[str, Any]:
    """Create an in-app notification asynchronously."""
    del ctx
    try:
        team_uuid = UUID(team_id)
        async with await _session_with_context(team_id=team_uuid, actor_id=user_id) as db:
            notification = await create_notification(
                db,
                team_id=team_uuid,
                type=notification_type,
                title=title,
                message=message,
                user_id=user_id,
                entity_type=entity_type,
                entity_id=entity_id,
            )
            await db.commit()
            return {"status": "created", "notification_id": str(notification.id)}
    except Exception as exc:
        logger.exception("notification_job failed")
        return {"status": "error", "reason": str(exc)}


async def opportunity_watch_job(
    ctx: dict[str, Any],
    team_id: str,
    actor_id: str | None = None,
    deal_id: str | None = None,
    trigger: str = "queued",
) -> dict[str, Any]:
    """Run OpportunityWatchAgent in the background."""
    del ctx
    try:
        from app.ai.agents.opportunity_watch_agent import run_opportunity_watch

        team_uuid = UUID(team_id)
        async with await _session_with_context(team_id=team_uuid, actor_id=actor_id) as db:
            return await run_opportunity_watch(
                db,
                team_id=team_uuid,
                actor_id=actor_id,
                deal_id=UUID(deal_id) if deal_id else None,
                trigger=trigger,
            )
    except Exception as exc:
        logger.exception("opportunity_watch_job failed")
        return {"status": "error", "reason": str(exc)}


async def proposal_job(
    ctx: dict[str, Any],
    deal_id: str,
    team_id: str,
    actor_id: str | None = None,
    trigger: str = "queued",
    force: bool = False,
) -> dict[str, Any]:
    """Run ProposalAgent in the background."""
    del ctx
    try:
        from app.ai.agents.proposal_agent import run_proposal_agent

        team_uuid = UUID(team_id)
        async with await _session_with_context(team_id=team_uuid, actor_id=actor_id) as db:
            draft = await run_proposal_agent(
                db,
                deal_id=UUID(deal_id),
                team_id=team_uuid,
                actor_id=actor_id,
                trigger=trigger,
                force=force,
            )
            if draft is None:
                return {"status": "skipped", "reason": "proposal_not_generated"}
            return {"status": "completed", "document_id": str(draft.document.id)}
    except Exception as exc:
        logger.exception("proposal_job failed")
        return {"status": "error", "reason": str(exc)}


async def auto_contact_draft_job(
    ctx: dict[str, Any],
    contact_id: str,
    team_id: str,
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Generate a welcome/outreach draft for a newly created contact."""
    del ctx
    try:
        from app.services.ai_email import create_auto_contact_draft

        team_uuid = UUID(team_id)
        async with await _session_with_context(team_id=team_uuid, actor_id=actor_id) as db:
            result = await create_auto_contact_draft(
                db,
                contact_id=UUID(contact_id),
                team_id=team_uuid,
                actor_id=actor_id,
            )
            await db.commit()
            return result
    except Exception as exc:
        logger.exception("auto_contact_draft_job failed")
        return {"status": "error", "reason": str(exc)}


async def send_sms_job(ctx: dict[str, Any], sms_id: str, team_id: str, actor_id: str | None = None) -> dict[str, Any]:
    """Send a queued SMS in the background."""
    del ctx
    try:
        from app.services.sms import execute_sms_send_by_id

        team_uuid = UUID(team_id)
        async with await _session_with_context(team_id=team_uuid, actor_id=actor_id) as db:
            message = await execute_sms_send_by_id(
                db,
                sms_id=UUID(sms_id),
                team_id=team_uuid,
                actor_id=actor_id,
            )
            return {
                "status": message.status,
                "provider_sid": message.provider_sid,
                "error_detail": message.error_detail,
            }
    except Exception as exc:
        logger.exception("send_sms_job failed")
        return {"status": "error", "reason": str(exc)}
