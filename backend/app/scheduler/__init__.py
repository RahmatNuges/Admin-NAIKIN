from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.scheduler.followup import run_followup_tick
from app.scheduler.outreach import run_outreach_tick
from app.utils import tz

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler:
        return _scheduler

    s = get_settings()
    sch = AsyncIOScheduler(timezone=tz())

    # Outreach: every 20 minutes within working hours.
    sch.add_job(
        run_outreach_tick,
        CronTrigger(
            day_of_week=",".join(s.work_days_list),
            hour=f"{s.work_hours_start}-{s.work_hours_end - 1}",
            minute=f"*/{s.outreach_interval_minutes}",
            timezone=tz(),
        ),
        id="outreach_tick",
        max_instances=1,
        coalesce=True,
    )

    # Follow-up: once a day at 10:00 local.
    sch.add_job(
        run_followup_tick,
        CronTrigger(hour=10, minute=0, timezone=tz()),
        id="followup_tick",
        max_instances=1,
        coalesce=True,
    )

    sch.start()
    logger.info("scheduler started")
    _scheduler = sch
    return sch


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
