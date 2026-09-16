"""ARQ worker settings exposed as ``app.workers.WorkerSettings``."""

from __future__ import annotations

from app.core.config import get_settings
from app.jobs import (
    ARQ_AVAILABLE,
    _redis_settings,
    auto_contact_draft_job,
    csv_import_job,
    crm_graph_job,
    notification_job,
    opportunity_watch_job,
    proposal_job,
    nurture_scan_job,
    research_job,
    send_sms_job,
    send_email_job,
)


if ARQ_AVAILABLE:

    class WorkerSettings:
        """ARQ worker configuration for Acufy CRM background jobs."""

        functions = [
            send_email_job,
            send_sms_job,
            crm_graph_job,
            auto_contact_draft_job,
            nurture_scan_job,
            research_job,
            csv_import_job,
            notification_job,
            opportunity_watch_job,
            proposal_job,
        ]
        redis_settings = _redis_settings()
        max_jobs = 10
        job_timeout = 300
        keep_result = 3600
        queue_name = "arq:queue"

else:

    class WorkerSettings:
        """Fallback placeholder when ARQ is unavailable in the environment."""

        functions: list[object] = []
        redis_settings = None
        max_jobs = 0
        job_timeout = 0
        keep_result = 0
        queue_name = "arq:queue"


__all__ = ["WorkerSettings"]
