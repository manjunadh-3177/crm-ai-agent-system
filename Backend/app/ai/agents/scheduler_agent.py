"""Scheduler agent for practical meeting slot suggestions and booking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Account, Contact, Deal, Meeting, Team
from app.schemas.crm import MeetingCreate
from app.services.audit import log_audit
from app.services.meetings import create_meeting

DEFAULT_WORKING_DAYS = "Mon-Fri"
DEFAULT_START = "09:00"
DEFAULT_END = "17:00"
MAX_SUGGESTIONS = 4
SEARCH_DAYS = 7
SLOT_INCREMENT_MINUTES = 30
WEEKDAY_TOKENS = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}


@dataclass(slots=True)
class SchedulerContext:
    team_id: UUID
    team: Team
    contact: Contact | None
    deal: Deal | None
    account: Account | None


async def suggest_slots(
    db: AsyncSession,
    *,
    team_id: UUID,
    actor_id: str | None = None,
    contact_id: UUID | None = None,
    deal_id: UUID | None = None,
    duration_minutes: int = 30,
    timezone_name: str | None = None,
) -> dict[str, object]:
    """Suggest the next mutual meeting slots within 7 days."""
    context = await _load_context(db, team_id=team_id, contact_id=contact_id, deal_id=deal_id)
    owner_tz = _load_timezone(timezone_name, fallback=context.team.timezone)
    customer_tz = _load_timezone(
        context.contact.preferred_timezone if context.contact and context.contact.preferred_timezone else context.team.timezone,
        fallback="UTC",
    )
    now = datetime.now(UTC)
    end_window = now + timedelta(days=7)
    meetings = await _load_team_meetings(db, team_id=team_id, end_window=end_window)
    owner_profile = _build_owner_profile(owner_tz)
    customer_profile = _build_contact_profile(context.contact, customer_tz)

    suggestions: list[dict[str, str | int | None]] = []
    owner_now = now.astimezone(owner_tz)
    for day_offset in range(SEARCH_DAYS):
        day = (owner_now + timedelta(days=day_offset)).date()
        if day.weekday() not in owner_profile.allowed_weekdays:
            continue
        for starts_at_owner in _iter_day_slots(day, owner_profile, duration_minutes):
            starts_at_utc = starts_at_owner.astimezone(UTC)
            if starts_at_utc <= now:
                continue
            ends_at_utc = starts_at_utc + timedelta(minutes=duration_minutes)
            if _slot_conflicts(starts_at=starts_at_utc, ends_at=ends_at_utc, meetings=meetings):
                continue
            if not _contact_accepts_slot(starts_at_utc, duration_minutes, customer_profile):
                continue
            suggestions.append(
                {
                    "starts_at": starts_at_utc.isoformat(),
                    "ends_at": ends_at_utc.isoformat(),
                    "label": _format_slot_label(starts_at_utc, owner_profile.timezone),
                    "your_time_label": _format_slot_label(starts_at_utc, owner_profile.timezone),
                    "customer_time_label": _format_slot_label(starts_at_utc, customer_profile.timezone),
                    "your_timezone": owner_profile.timezone.key,
                    "customer_timezone": customer_profile.timezone.key,
                    "duration_minutes": duration_minutes,
                }
            )
            if len(suggestions) == MAX_SUGGESTIONS:
                break
        if len(suggestions) == MAX_SUGGESTIONS:
            break

    contact_name = _contact_name(context.contact)
    message = (
        f"Found {len(suggestions)} mutual meeting slots for {contact_name} this week."
        if suggestions
        else "No common slots found. Suggest async email instead."
    )

    await log_audit(
        db,
        action="agent.scheduler_suggested",
        entity_type="team",
        entity_id=str(team_id),
        actor_type="ai",
        actor_id=actor_id,
        team_id=team_id,
        metadata={
            "contact_id": str(context.contact.id) if context.contact else None,
            "deal_id": str(context.deal.id) if context.deal else None,
            "account_id": str(context.account.id) if context.account else None,
            "duration_minutes": duration_minutes,
            "suggestions_count": len(suggestions),
            "request_timezone": owner_profile.timezone.key,
            "contact_timezone": customer_profile.timezone.key,
            "message": message,
        },
    )
    await db.commit()
    return {
        "slots": suggestions,
        "message": message,
        "your_availability": owner_profile.to_summary(),
        "customer_availability": customer_profile.to_summary(),
    }


async def book_slot(
    db: AsyncSession,
    *,
    team_id: UUID,
    actor_id: str | None = None,
    contact_id: UUID | None = None,
    deal_id: UUID | None = None,
    starts_at: datetime,
    duration_minutes: int = 30,
    timezone_name: str = "UTC",
) -> Meeting:
    """Book a selected slot by creating a meeting through the existing flow."""
    context = await _load_context(db, team_id=team_id, contact_id=contact_id, deal_id=deal_id)
    if context.contact is None and context.deal is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A contact or deal is required.")

    starts_at_utc = _ensure_utc(starts_at)
    if starts_at_utc <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Meeting slot must be in the future.")

    ends_at = starts_at_utc + timedelta(minutes=duration_minutes)
    meetings = await _load_team_meetings(db, team_id=team_id, end_window=ends_at + timedelta(days=1))
    if _slot_conflicts(starts_at=starts_at_utc, ends_at=ends_at, meetings=meetings):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That slot is no longer available.")
    customer_tz = _load_timezone(
        context.contact.preferred_timezone if context.contact and context.contact.preferred_timezone else context.team.timezone,
        fallback="UTC",
    )
    customer_profile = _build_contact_profile(context.contact, customer_tz)
    if not _contact_accepts_slot(starts_at_utc, duration_minutes, customer_profile):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That slot no longer matches the contact's availability.",
        )

    title = _build_meeting_title(context)
    payload = MeetingCreate(
        title=title,
        description=_build_meeting_description(context),
        starts_at=starts_at_utc,
        ends_at=ends_at,
        timezone=timezone_name or "UTC",
        location="Video Call",
        meeting_type="followup",
        reminder_minutes=15,
        contact_id=context.contact.id if context.contact else None,
        deal_id=context.deal.id if context.deal else None,
        account_id=context.account.id if context.account else None,
    )
    meeting = await create_meeting(db, payload, team_id=team_id, actor_id=actor_id)
    await log_audit(
        db,
        action="meeting.created_via_scheduler",
        entity_type="meeting",
        entity_id=str(meeting.id),
        actor_type="ai",
        actor_id=actor_id,
        team_id=team_id,
        metadata={
            "contact_id": str(context.contact.id) if context.contact else None,
            "deal_id": str(context.deal.id) if context.deal else None,
            "account_id": str(context.account.id) if context.account else None,
            "starts_at": meeting.starts_at.isoformat(),
            "duration_minutes": duration_minutes,
        },
    )
    await db.commit()
    return meeting


async def _load_context(
    db: AsyncSession,
    *,
    team_id: UUID,
    contact_id: UUID | None,
    deal_id: UUID | None,
) -> SchedulerContext:
    team = await db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")

    deal: Deal | None = None
    contact: Contact | None = None
    account: Account | None = None

    if deal_id is not None:
        result = await db.execute(
            select(Deal)
            .options(
                selectinload(Deal.contact),
                selectinload(Deal.account),
                selectinload(Deal.stage),
            )
            .where(Deal.id == deal_id, Deal.team_id == team_id)
        )
        deal = result.scalar_one_or_none()
        if deal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found.")
        if deal.stage and deal.stage.is_closed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot schedule against a closed deal.")
        contact = deal.contact
        account = deal.account

    if contact_id is not None:
        loaded_contact = await db.get(Contact, contact_id)
        if loaded_contact is None or loaded_contact.team_id != team_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found.")
        contact = loaded_contact
        if account is None and loaded_contact.account_id:
            loaded_account = await db.get(Account, loaded_contact.account_id)
            if loaded_account is not None and loaded_account.team_id == team_id:
                account = loaded_account

    if deal is None and account is None and contact is not None and contact.account_id:
        loaded_account = await db.get(Account, contact.account_id)
        if loaded_account is not None and loaded_account.team_id == team_id:
            account = loaded_account

    return SchedulerContext(team_id=team_id, team=team, contact=contact, deal=deal, account=account)


async def _load_team_meetings(
    db: AsyncSession,
    *,
    team_id: UUID,
    end_window: datetime,
) -> list[Meeting]:
    result = await db.execute(
        select(Meeting)
        .where(
            Meeting.team_id == team_id,
            Meeting.status == "scheduled",
            Meeting.starts_at <= end_window,
        )
        .order_by(Meeting.starts_at)
    )
    return list(result.scalars().all())


def _slot_conflicts(*, starts_at: datetime, ends_at: datetime, meetings: list[Meeting]) -> bool:
    for meeting in meetings:
        if meeting.starts_at < ends_at and meeting.ends_at > starts_at:
            return True
    return False


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _build_meeting_title(context: SchedulerContext) -> str:
    if context.deal is not None:
        return f"{context.deal.stage.name if context.deal.stage else 'Deal'} Follow-up: {context.deal.name}"
    if context.contact is not None:
        return f"Follow-up with {context.contact.first_name} {context.contact.last_name}".strip()
    return "Follow-up Meeting"


def _build_meeting_description(context: SchedulerContext) -> str:
    lines: list[str] = []
    if context.contact is not None:
        lines.append(f"Contact: {context.contact.first_name} {context.contact.last_name}".strip())
    if context.account is not None:
        lines.append(f"Company: {context.account.name}")
    if context.deal is not None:
        lines.append(f"Deal: {context.deal.name}")
        if context.deal.stage is not None:
            lines.append(f"Stage: {context.deal.stage.name}")
    return "\n".join(lines) if lines else "Scheduled via SchedulerAgent."


@dataclass(slots=True)
class AvailabilityProfile:
    timezone: ZoneInfo
    working_days_label: str
    working_start: time
    working_end: time
    allowed_weekdays: set[int]
    preferred_windows_label: str | None = None
    preferred_windows: list[tuple[time, time]] | None = None
    blocked_days_label: str | None = None
    blocked_dates: set[str] | None = None
    blocked_weekdays: set[int] | None = None

    def to_summary(self) -> dict[str, str | None]:
        windows_text = self.preferred_windows_label or "Working hours"
        blocked_text = self.blocked_days_label or "None"
        return {
            "timezone": self.timezone.key,
            "working_days": self.working_days_label,
            "working_hours_start": self.working_start.strftime("%H:%M"),
            "working_hours_end": self.working_end.strftime("%H:%M"),
            "preferred_meeting_windows": self.preferred_windows_label,
            "blocked_days": self.blocked_days_label,
            "summary": (
                f"{self.working_days_label} {self.working_start.strftime('%I:%M %p')} - "
                f"{self.working_end.strftime('%I:%M %p')} ({self.timezone.key}); "
                f"windows: {windows_text}; blocked: {blocked_text}"
            ),
        }


def _build_owner_profile(owner_tz: ZoneInfo) -> AvailabilityProfile:
    return AvailabilityProfile(
        timezone=owner_tz,
        working_days_label=DEFAULT_WORKING_DAYS,
        working_start=_parse_clock(DEFAULT_START),
        working_end=_parse_clock(DEFAULT_END),
        allowed_weekdays=_parse_working_days(DEFAULT_WORKING_DAYS),
        preferred_windows_label=None,
        preferred_windows=None,
        blocked_days_label=None,
        blocked_dates=set(),
        blocked_weekdays=set(),
    )


def _build_contact_profile(contact: Contact | None, timezone: ZoneInfo) -> AvailabilityProfile:
    working_days = (contact.working_days if contact and contact.working_days else DEFAULT_WORKING_DAYS).strip()
    start = _parse_clock(contact.working_hours_start if contact and contact.working_hours_start else DEFAULT_START)
    end = _parse_clock(contact.working_hours_end if contact and contact.working_hours_end else DEFAULT_END)
    preferred_label = (contact.preferred_meeting_windows or "").strip() if contact else ""
    blocked_label = (contact.blocked_days or "").strip() if contact else ""
    blocked_dates, blocked_weekdays = _parse_blocked_days(blocked_label)
    return AvailabilityProfile(
        timezone=timezone,
        working_days_label=working_days,
        working_start=start,
        working_end=end,
        allowed_weekdays=_parse_working_days(working_days),
        preferred_windows_label=preferred_label or None,
        preferred_windows=_parse_time_ranges(preferred_label) if preferred_label else None,
        blocked_days_label=blocked_label or None,
        blocked_dates=blocked_dates,
        blocked_weekdays=blocked_weekdays,
    )


def _contact_accepts_slot(starts_at_utc: datetime, duration_minutes: int, profile: AvailabilityProfile) -> bool:
    local_start = starts_at_utc.astimezone(profile.timezone)
    local_end = local_start + timedelta(minutes=duration_minutes)
    if local_start.weekday() not in profile.allowed_weekdays:
        return False
    if profile.blocked_weekdays and local_start.weekday() in profile.blocked_weekdays:
        return False
    if profile.blocked_dates and local_start.date().isoformat() in profile.blocked_dates:
        return False
    if not _range_contains(profile.working_start, profile.working_end, local_start.time(), local_end.time()):
        return False
    if profile.preferred_windows:
        return any(_range_contains(start, end, local_start.time(), local_end.time()) for start, end in profile.preferred_windows)
    return True


def _iter_day_slots(day: date, profile: AvailabilityProfile, duration_minutes: int):
    slot_start = datetime.combine(day, profile.working_start, tzinfo=profile.timezone)
    last_start = datetime.combine(day, profile.working_end, tzinfo=profile.timezone) - timedelta(minutes=duration_minutes)
    while slot_start <= last_start:
        if profile.preferred_windows:
            if any(
                _range_contains(start, end, slot_start.timetz().replace(tzinfo=None), (slot_start + timedelta(minutes=duration_minutes)).timetz().replace(tzinfo=None))
                for start, end in profile.preferred_windows
            ):
                yield slot_start
        else:
            yield slot_start
        slot_start += timedelta(minutes=SLOT_INCREMENT_MINUTES)


def _range_contains(window_start: time, window_end: time, slot_start: time, slot_end: time) -> bool:
    return (slot_start >= window_start) and (slot_end <= window_end)


def _parse_working_days(raw_value: str | None) -> set[int]:
    value = (raw_value or DEFAULT_WORKING_DAYS).strip().lower()
    if value in {"daily", "all", "all week", "everyday", "every day"}:
        return set(range(7))
    tokens = [part.strip() for part in re.split(r"[;,]", value) if part.strip()]
    weekdays: set[int] = set()
    for token in tokens or [DEFAULT_WORKING_DAYS.lower()]:
        if "-" in token:
            start_token, end_token = [piece.strip() for piece in token.split("-", 1)]
            start_day = WEEKDAY_TOKENS.get(start_token)
            end_day = WEEKDAY_TOKENS.get(end_token)
            if start_day is None or end_day is None:
                continue
            if start_day <= end_day:
                weekdays.update(range(start_day, end_day + 1))
            else:
                weekdays.update(range(start_day, 7))
                weekdays.update(range(0, end_day + 1))
        else:
            day = WEEKDAY_TOKENS.get(token)
            if day is not None:
                weekdays.add(day)
    return weekdays or {0, 1, 2, 3, 4}


def _parse_time_ranges(raw_value: str) -> list[tuple[time, time]]:
    ranges: list[tuple[time, time]] = []
    for token in [part.strip() for part in raw_value.split(";") if part.strip()]:
        if "-" not in token:
            continue
        start_text, end_text = [piece.strip() for piece in token.split("-", 1)]
        start = _parse_clock(start_text)
        end = _parse_clock(end_text)
        if start < end:
            ranges.append((start, end))
    return ranges


def _parse_blocked_days(raw_value: str) -> tuple[set[str], set[int]]:
    dates: set[str] = set()
    weekdays: set[int] = set()
    for token in [part.strip() for part in re.split(r"[;,]", raw_value) if part.strip()]:
        normalized = token.lower()
        if normalized in WEEKDAY_TOKENS:
            weekdays.add(WEEKDAY_TOKENS[normalized])
            continue
        try:
            dates.add(datetime.fromisoformat(token).date().isoformat())
        except ValueError:
            continue
    return dates, weekdays


def _parse_clock(raw_value: str | None) -> time:
    value = (raw_value or DEFAULT_START).strip()
    for fmt in ("%H:%M", "%I:%M %p", "%I %p"):
        try:
            return datetime.strptime(value.upper(), fmt).time()
        except ValueError:
            continue
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid time value: {value}")


def _load_timezone(primary: str | None, *, fallback: str | None = None) -> ZoneInfo:
    for name in (primary, fallback, "UTC"):
        if not name:
            continue
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            continue
    return ZoneInfo("UTC")


def _format_slot_label(starts_at_utc: datetime, timezone: ZoneInfo) -> str:
    local_value = starts_at_utc.astimezone(timezone)
    return local_value.strftime("%a %b %d, %I:%M %p")


def _contact_name(contact: Contact | None) -> str:
    if contact is None:
        return "this contact"
    return f"{contact.first_name} {contact.last_name}".strip() or "this contact"
