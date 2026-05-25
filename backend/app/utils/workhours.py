from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings

_DAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def now_local() -> datetime:
    return datetime.now(tz())


def is_work_day(dt: datetime | None = None) -> bool:
    s = get_settings()
    dt = dt or now_local()
    allowed = {_DAY_MAP[d] for d in s.work_days_list if d in _DAY_MAP}
    return dt.weekday() in allowed


def is_work_hours(dt: datetime | None = None) -> bool:
    s = get_settings()
    dt = dt or now_local()
    if not is_work_day(dt):
        return False
    start = time(hour=s.work_hours_start)
    end = time(hour=s.work_hours_end)
    return start <= dt.time() < end


def next_work_slot(after: datetime | None = None) -> datetime:
    """Return the next datetime that falls within work hours."""
    s = get_settings()
    cur = (after or now_local()).astimezone(tz())
    for _ in range(14):  # search up to 2 weeks
        if is_work_hours(cur):
            return cur
        if is_work_day(cur):
            start = cur.replace(
                hour=s.work_hours_start, minute=0, second=0, microsecond=0
            )
            if cur < start:
                return start
        cur = (cur + timedelta(days=1)).replace(
            hour=s.work_hours_start, minute=0, second=0, microsecond=0
        )
    return cur


def stagger_slots(count: int, *, start_at: datetime | None = None) -> list[datetime]:
    """Build `count` outreach slots, throttled by interval, only inside work hours."""
    s = get_settings()
    interval = timedelta(minutes=s.outreach_interval_minutes)
    cursor = next_work_slot(start_at)
    slots: list[datetime] = []
    while len(slots) < count:
        if is_work_hours(cursor):
            slots.append(cursor)
            cursor = cursor + interval
        else:
            cursor = next_work_slot(cursor)
    return slots
