"""Re-stagger PENDING outreach jobs starting from a given time.

Usage:
    python -m app.cli.restagger_outreach           # restagger from now
    python -m app.cli.restagger_outreach --dry-run # preview only
"""
from __future__ import annotations

import argparse
import sys
from datetime import timedelta, timezone

from app.db import session_scope
from app.models import OutreachQueue, OutreachStatus
from app.utils import next_work_slot, now_local


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Re-stagger PENDING outreach jobs")
    p.add_argument("--dry-run", action="store_true", help="Preview, no DB writes")
    p.add_argument(
        "--offset-minutes",
        type=int,
        default=5,
        help="Start scheduling N minutes from now (default: 5)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    from app.config import get_settings

    args = parse_args(argv or sys.argv[1:])
    s = get_settings()
    interval = timedelta(minutes=s.outreach_interval_minutes)

    start = now_local() + timedelta(minutes=args.offset_minutes)
    cursor = next_work_slot(start)

    with session_scope() as db:
        jobs = (
            db.query(OutreachQueue)
            .filter(OutreachQueue.status == OutreachStatus.PENDING)
            .order_by(OutreachQueue.scheduled_at.asc())
            .all()
        )
        if not jobs:
            print("no PENDING jobs to re-stagger")
            return 0

        print(f"re-staggering {len(jobs)} PENDING jobs, interval={s.outreach_interval_minutes}min")
        print(f"start cursor (WIB): {cursor.strftime('%Y-%m-%d %H:%M')}")
        print()

        for job in jobs:
            new_utc = cursor.astimezone(timezone.utc).replace(tzinfo=None)
            old_utc = job.scheduled_at
            print(
                f"  job {job.id}: {old_utc} UTC -> {new_utc} UTC "
                f"({cursor.strftime('%Y-%m-%d %H:%M')} WIB)"
            )
            if not args.dry_run:
                job.scheduled_at = new_utc
            cursor = next_work_slot(cursor + interval)

        if args.dry_run:
            print("\ndry-run: no DB writes")
        else:
            print(f"\nupdated {len(jobs)} jobs")

    return 0


if __name__ == "__main__":
    sys.exit(main())
