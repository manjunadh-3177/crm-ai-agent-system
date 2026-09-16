"""Reports API routes."""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthContext, requires_role
from app.core.db import get_db
from app.schemas.crm import ReportsPerformanceRead, ReportsPipelineRead, ReportsSummaryRead
from app.services.analytics import (
    get_reports_performance,
    get_reports_pipeline,
    get_reports_summary,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/summary", response_model=ReportsSummaryRead)
async def get_summary_report(
    period: str = "this_month",
    start_date: date | None = None,
    end_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(requires_role("admin", "manager")),
) -> ReportsSummaryRead:
    """Return top-level CRM summary metrics for the current team."""
    normalized_period = _normalize_period(period)
    return await get_reports_summary(
        db,
        team_id=auth.team_id,
        period=normalized_period,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/pipeline", response_model=ReportsPipelineRead)
async def get_pipeline_report(
    period: str = "this_month",
    start_date: date | None = None,
    end_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(requires_role("admin", "manager")),
) -> ReportsPipelineRead:
    """Return current team pipeline grouped by stage."""
    normalized_period = _normalize_period(period)
    return await get_reports_pipeline(
        db,
        team_id=auth.team_id,
        period=normalized_period,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/performance", response_model=ReportsPerformanceRead)
async def get_performance_report(
    period: str = "this_month",
    start_date: date | None = None,
    end_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(requires_role("admin", "manager")),
) -> ReportsPerformanceRead:
    """Return time-bound performance metrics for the current team."""
    normalized_period = _normalize_period(period)
    return await get_reports_performance(
        db,
        team_id=auth.team_id,
        period=normalized_period,
        start_date=start_date,
        end_date=end_date,
    )


def _normalize_period(period: str) -> str:
    allowed = {"today", "last_7_days", "last_30_days", "this_month", "last_quarter", "this_year", "custom"}
    return period if period in allowed else "this_month"
