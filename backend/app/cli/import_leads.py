from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

import phonenumbers

from app.db import session_scope
from app.models import Lead, LeadState, OutreachQueue, OutreachStatus
from app.utils import stagger_slots

REQUIRED_COLS = {"wa_number"}
OPTIONAL_COLS = {"name", "clinic_name", "clinic_type", "city", "source"}


def normalize_number(raw: str) -> str | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        parsed = phonenumbers.parse(raw, "ID")
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164).lstrip("+")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Import leads from CSV")
    p.add_argument("--csv", required=True, help="Path to CSV file")
    p.add_argument("--dry-run", action="store_true", help="Validate only, no DB writes")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    path = Path(args.csv)
    if not path.exists():
        print(f"file not found: {path}", file=sys.stderr)
        return 2

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        if not rows:
            print("no rows in CSV")
            return 0
        cols = set(reader.fieldnames or [])
        missing = REQUIRED_COLS - cols
        if missing:
            print(f"missing columns: {missing}", file=sys.stderr)
            return 2

    valid: list[dict] = []
    invalid: list[tuple[int, str]] = []
    seen: set[str] = set()
    for i, row in enumerate(rows, start=2):  # header is line 1
        number = normalize_number(row.get("wa_number", ""))
        if not number:
            invalid.append((i, row.get("wa_number", "")))
            continue
        if number in seen:
            continue
        seen.add(number)
        valid.append(
            {
                "wa_number": number,
                "name": (row.get("name") or "").strip() or None,
                "clinic_name": (row.get("clinic_name") or "").strip() or None,
                "clinic_type": (row.get("clinic_type") or "").strip() or None,
                "city": (row.get("city") or "").strip() or None,
                "source": (row.get("source") or "").strip() or None,
            }
        )

    print(f"valid rows: {len(valid)}, invalid: {len(invalid)}, deduped to: {len(valid)}")
    if invalid:
        for line, raw in invalid[:10]:
            print(f"  line {line}: {raw!r}")
        if len(invalid) > 10:
            print(f"  ...and {len(invalid) - 10} more")

    if args.dry_run:
        print("dry-run: no DB writes")
        return 0

    inserted = 0
    skipped_existing = 0
    with session_scope() as db:
        existing = {
            n
            for (n,) in db.query(Lead.wa_number).filter(Lead.wa_number.in_(seen)).all()
        }
        new_rows = [r for r in valid if r["wa_number"] not in existing]
        skipped_existing = len(valid) - len(new_rows)

        slots = stagger_slots(len(new_rows))
        for r, slot in zip(new_rows, slots, strict=True):
            lead = Lead(state=LeadState.NEW, **r)
            db.add(lead)
            db.flush()
            db.add(
                OutreachQueue(
                    lead_id=lead.id,
                    scheduled_at=slot.astimezone(timezone.utc).replace(tzinfo=None),
                    status=OutreachStatus.PENDING,
                )
            )
            inserted += 1

    print(f"inserted leads: {inserted}, skipped (already exist): {skipped_existing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
