"""Team-scoped forecasting and pipeline analytics helpers."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AuditLog, Contact, Deal, Meeting, Task
from app.schemas.ai import (
    ForecastDealItem,
    ForecastMetricsResponse,
    ForecastStageMetric,
    ForecastWinLossMetric,
)
from app.schemas.crm import ReportsPerformanceRead, ReportsPipelineRead, ReportsPipelineStageRead, ReportsSummaryRead
from app.services.seeding import DEFAULT_STAGES, seed_pipeline_data_if_empty


STALL_THRESHOLD_DAYS = 14
TOP_OPEN_DEALS_LIMIT = 5


def _normalize_stage_name(value: str | None) -> str:
    return (value or "").strip().lower()


def _to_float(value: Decimal | None) -> float:
    return float(value) if value is not None else 0.0


def _sum_decimal(values: list[Decimal | None]) -> Decimal:
    total = Decimal("0")
    for value in values:
        if value is not None:
            total += value
    return total


def _get_period_bounds(period: str, *, start_date: date | None = None, end_date: date | None = None) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    today = now.date()
    if period == "custom" and start_date and end_date:
        return (
            datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc),
            datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc),
        )
    if period == "today":
        start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
        return start, start + timedelta(days=1)
    if period == "last_7_days":
        return now - timedelta(days=7), now
    if period == "last_30_days":
        return now - timedelta(days=30), now
    if period == "last_quarter":
        current_quarter = (now.month - 1) // 3
        if current_quarter == 0:
            start = datetime(now.year - 1, 10, 1, tzinfo=timezone.utc)
            end = datetime(now.year, 1, 1, tzinfo=timezone.utc)
        else:
            start_month = ((current_quarter - 1) * 3) + 1
            start = datetime(now.year, start_month, 1, tzinfo=timezone.utc)
            end = datetime(now.year, start_month + 3, 1, tzinfo=timezone.utc)
        return start, end
    if period == "this_year":
        return datetime(now.year, 1, 1, tzinfo=timezone.utc), datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)

    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now.month == 12:
        next_month = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_month = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    return month_start, next_month


async def compute_team_pipeline_metrics(
    db: AsyncSession,
    *,
    team_id: UUID,
) -> ForecastMetricsResponse:
    """Compute deterministic forecasting metrics for a team."""
    deals_result = await db.execute(
        select(Deal)
        .options(selectinload(Deal.stage), selectinload(Deal.owner))
        .where(Deal.team_id == team_id)
        .order_by(Deal.created_at.desc())
    )
    deals = list(deals_result.scalars().all())

    stage_change_logs_result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.team_id == team_id,
            AuditLog.action == "deal.stage_changed",
            AuditLog.entity_type == "deal",
        )
        .order_by(AuditLog.created_at.desc())
    )
    stage_change_logs = list(stage_change_logs_result.scalars().all())

    latest_stage_change_by_deal: dict[str, datetime] = {}
    for log in stage_change_logs:
        if log.entity_id and log.entity_id not in latest_stage_change_by_deal:
            latest_stage_change_by_deal[log.entity_id] = log.created_at

    open_deals = [deal for deal in deals if not (deal.stage and deal.stage.is_closed)]
    now = datetime.now(timezone.utc)
    today = date.today()
    month_start = today.replace(day=1)
    next_month_start = date(today.year + (1 if today.month == 12 else 0), 1 if today.month == 12 else today.month + 1, 1)

    deals_by_stage_counts: defaultdict[str, int] = defaultdict(int)
    for deal in deals:
        stage_name = deal.stage.name if deal.stage else "Unknown"
        deals_by_stage_counts[stage_name] += 1

    deals_by_stage = [
        ForecastStageMetric(stage=stage_name, count=count)
        for stage_name, count in sorted(deals_by_stage_counts.items(), key=lambda item: item[0])
    ]

    total_pipeline_value = round(sum(_to_float(deal.amount) for deal in open_deals), 2)
    weighted_pipeline_value = round(
        sum(_to_float(deal.amount) * ((deal.probability or 0) / 100) for deal in open_deals),
        2,
    )

    open_deals_with_amount = [deal for deal in open_deals if deal.amount is not None]
    avg_deal_size = round(
        sum(_to_float(deal.amount) for deal in open_deals_with_amount) / len(open_deals_with_amount),
        2,
    ) if open_deals_with_amount else 0.0

    stalled_cutoff = now - timedelta(days=STALL_THRESHOLD_DAYS)
    stalled_deals: list[ForecastDealItem] = []
    for deal in open_deals:
        last_moved_at = latest_stage_change_by_deal.get(str(deal.id), deal.updated_at)
        if last_moved_at < stalled_cutoff:
            stalled_days = max((now - last_moved_at).days, STALL_THRESHOLD_DAYS)
            stalled_deals.append(_to_deal_item(deal, last_activity_at=last_moved_at, stalled_days=stalled_days))

    stalled_deals.sort(key=lambda item: ((item.stalled_days or 0), item.amount or 0), reverse=True)

    won_deals = [
        deal
        for deal in deals
        if deal.stage and deal.stage.is_closed and deal.stage.name.lower() == "won" and month_start <= deal.updated_at.date() < next_month_start
    ]
    lost_deals = [
        deal
        for deal in deals
        if deal.stage and deal.stage.is_closed and deal.stage.name.lower() == "lost" and month_start <= deal.updated_at.date() < next_month_start
    ]

    won_this_month = ForecastWinLossMetric(
        count=len(won_deals),
        total_value=round(sum(_to_float(deal.amount) for deal in won_deals), 2),
    )
    lost_this_month = ForecastWinLossMetric(
        count=len(lost_deals),
        total_value=round(sum(_to_float(deal.amount) for deal in lost_deals), 2),
    )

    close_this_month_estimate = round(
        sum(
            _to_float(deal.amount) * ((deal.probability or 0) / 100)
            for deal in open_deals
            if deal.expected_close_date is not None and month_start <= deal.expected_close_date < next_month_start
        ),
        2,
    )

    ranked_open_deals = sorted(
        open_deals,
        key=lambda deal: (_to_float(deal.amount), deal.probability or 0),
        reverse=True,
    )[:TOP_OPEN_DEALS_LIMIT]
    top_open_deals = [_to_deal_item(deal) for deal in ranked_open_deals]

    return ForecastMetricsResponse(
        deals_by_stage=deals_by_stage,
        total_pipeline_value=total_pipeline_value,
        weighted_pipeline_value=weighted_pipeline_value,
        avg_deal_size=avg_deal_size,
        stalled_deals=stalled_deals[:TOP_OPEN_DEALS_LIMIT],
        won_this_month=won_this_month,
        lost_this_month=lost_this_month,
        close_this_month_estimate=close_this_month_estimate,
        top_open_deals=top_open_deals,
    )


async def get_reports_summary(
    db: AsyncSession,
    *,
    team_id: UUID,
    period: str = "this_month",
    start_date: date | None = None,
    end_date: date | None = None,
) -> ReportsSummaryRead:
    await seed_pipeline_data_if_empty(db, team_id, user_id=db.info.get("user_id"))
    start_at, end_at = _get_period_bounds(period, start_date=start_date, end_date=end_date)
    contacts_result = await db.execute(
        select(Contact.id).where(Contact.team_id == team_id, Contact.created_at >= start_at, Contact.created_at < end_at)
    )
    deals_result = await db.execute(
        select(Deal)
        .options(selectinload(Deal.stage))
        .where(Deal.team_id == team_id, Deal.updated_at >= start_at, Deal.updated_at < end_at)
    )
    tasks_result = await db.execute(
        select(Task.id).where(Task.team_id == team_id, Task.status == "open", Task.updated_at >= start_at, Task.updated_at < end_at)
    )
    meetings_result = await db.execute(
        select(Meeting.id).where(
            Meeting.team_id == team_id,
            Meeting.status == "scheduled",
            Meeting.starts_at >= datetime.now(timezone.utc),
            Meeting.starts_at < end_at,
        )
    )

    deals = list(deals_result.scalars().all())
    open_deals = [deal for deal in deals if not (deal.stage and deal.stage.is_closed)]
    won_deals = [deal for deal in deals if deal.stage and deal.stage.name.lower() == "won"]
    lost_deals = [deal for deal in deals if deal.stage and deal.stage.name.lower() == "lost"]

    return ReportsSummaryRead(
        total_contacts=len(list(contacts_result.scalars().all())),
        open_deals=len(open_deals),
        won_deals=len(won_deals),
        lost_deals=len(lost_deals),
        tasks_pending=len(list(tasks_result.scalars().all())),
        meetings_upcoming=len(list(meetings_result.scalars().all())),
        pipeline_value=_sum_decimal([deal.amount for deal in open_deals]),
    )


async def get_reports_pipeline(
    db: AsyncSession,
    *,
    team_id: UUID,
    period: str = "this_month",
    start_date: date | None = None,
    end_date: date | None = None,
) -> ReportsPipelineRead:
    await seed_pipeline_data_if_empty(db, team_id, user_id=db.info.get("user_id"))
    start_at, end_at = _get_period_bounds(period, start_date=start_date, end_date=end_date)
    deals_result = await db.execute(
        select(Deal)
        .options(selectinload(Deal.stage))
        .where(Deal.team_id == team_id, Deal.updated_at >= start_at, Deal.updated_at < end_at)
        .order_by(Deal.created_at.desc())
    )
    deals = list(deals_result.scalars().all())
    stage_map: defaultdict[str, list[Deal]] = defaultdict(list)
    for deal in deals:
        stage_key = _normalize_stage_name(deal.stage.name if deal.stage else None)
        if stage_key:
            stage_map[stage_key].append(deal)

    rows = [
        ReportsPipelineStageRead(
            stage=name,
            count=len(stage_map.get(_normalize_stage_name(name), [])),
            total_value=_sum_decimal([deal.amount for deal in stage_map.get(_normalize_stage_name(name), [])]),
        )
        for name, _ in DEFAULT_STAGES
    ]
    return ReportsPipelineRead(deals_by_stage=rows, stages=rows)


async def get_reports_performance(
    db: AsyncSession,
    *,
    team_id: UUID,
    period: str = "this_month",
    start_date: date | None = None,
    end_date: date | None = None,
) -> ReportsPerformanceRead:
    start_at, end_at = _get_period_bounds(period, start_date=start_date, end_date=end_date)
    deals_result = await db.execute(
        select(Deal)
        .options(selectinload(Deal.stage))
        .where(Deal.team_id == team_id, Deal.updated_at >= start_at, Deal.updated_at < end_at)
    )
    meetings_result = await db.execute(
        select(Meeting.id).where(
            Meeting.team_id == team_id,
            Meeting.status == "completed",
            Meeting.updated_at >= start_at,
            Meeting.updated_at < end_at,
        )
    )
    tasks_result = await db.execute(
        select(Task.id).where(
            Task.team_id == team_id,
            Task.status == "done",
            Task.updated_at >= start_at,
            Task.updated_at < end_at,
        )
    )

    deals = list(deals_result.scalars().all())
    closed_deals = [deal for deal in deals if deal.stage and deal.stage.is_closed]
    won_deals = [deal for deal in closed_deals if deal.stage and deal.stage.name.lower() == "won"]

    return ReportsPerformanceRead(
        period=period,
        closed_deals=len(closed_deals),
        won_revenue=_sum_decimal([deal.amount for deal in won_deals]),
        meetings_completed=len(list(meetings_result.scalars().all())),
        tasks_completed=len(list(tasks_result.scalars().all())),
    )


async def list_recent_team_activity(
    db: AsyncSession,
    *,
    team_id: UUID,
    limit: int = 8,
) -> list[dict[str, str]]:
    """Return recent forecast-relevant activity in compact form."""
    result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.team_id == team_id,
            AuditLog.action.in_(
                [
                    "deal.created",
                    "deal.stage_changed",
                    "approval.created",
                    "approval.approved",
                    "approval.rejected",
                    "email.executed",
                ]
            ),
        )
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    logs = list(result.scalars().all())
    return [
        {
            "action": log.action,
            "entity_id": log.entity_id or "",
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


def _to_deal_item(
    deal: Deal,
    *,
    last_activity_at: datetime | None = None,
    stalled_days: int | None = None,
) -> ForecastDealItem:
    return ForecastDealItem(
        id=deal.id,
        name=deal.name,
        amount=round(_to_float(deal.amount), 2) if deal.amount is not None else None,
        currency=deal.currency,
        probability=deal.probability,
        stage=deal.stage.name if deal.stage else "Unknown",
        owner=deal.owner.full_name if deal.owner else None,
        expected_close_date=deal.expected_close_date,
        last_activity_at=last_activity_at,
        stalled_days=stalled_days,
    )
