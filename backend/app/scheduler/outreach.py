from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bridge import BridgeError, send_message
from app.config import get_settings
from app.conversation import record_outbound, transition_state
from app.db import session_scope
from app.llm import LLMClient, generate_outreach_message
from app.models import Lead, LeadState, OutreachQueue, OutreachStatus
from app.utils import is_work_hours, now_local

logger = logging.getLogger(__name__)


def _eligible_jobs(db: Session, *, limit: int) -> list[OutreachQueue]:
    naive_now = datetime.utcnow()
    stmt = (
        select(OutreachQueue)
        .where(OutreachQueue.status == OutreachStatus.PENDING)
        .where(OutreachQueue.scheduled_at <= naive_now)
        .order_by(OutreachQueue.scheduled_at.asc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


def _sent_in_last_hour(db: Session) -> int:
    cutoff = datetime.utcnow() - timedelta(hours=1)
    return (
        db.query(OutreachQueue)
        .filter(OutreachQueue.status == OutreachStatus.SENT)
        .filter(OutreachQueue.sent_at >= cutoff)
        .count()
    )


async def _process_one(job: OutreachQueue, lead: Lead, llm: LLMClient) -> tuple[str, dict] | None:
    try:
        text, meta = await generate_outreach_message(lead, llm=llm)
    except Exception as e:
        logger.error("outreach LLM failed for lead %s: %s", lead.id, e)
        return None
    try:
        await send_message(lead.wa_number, text)
    except BridgeError as e:
        logger.error("outreach send failed for lead %s: %s", lead.id, e)
        return None
    return text, meta


async def run_outreach_tick() -> None:
    s = get_settings()
    if not is_work_hours():
        logger.debug("outreach tick skipped: outside work hours")
        return

    llm = LLMClient()
    with session_scope() as db:
        sent_count = _sent_in_last_hour(db)
        budget = max(0, s.outreach_per_hour - sent_count)
        if budget <= 0:
            logger.info("outreach budget exhausted (%s sent in last hour)", sent_count)
            return
        jobs = _eligible_jobs(db, limit=budget)
        if not jobs:
            return

        for job in jobs:
            lead = db.get(Lead, job.lead_id)
            if not lead or lead.state != LeadState.NEW:
                job.status = OutreachStatus.SKIPPED
                job.error = "lead missing or not NEW"
                continue
            result = await _process_one(job, lead, llm)
            if not result:
                job.status = OutreachStatus.FAILED
                job.error = "send or LLM failed"
                continue
            text, meta = result
            record_outbound(
                db,
                lead,
                text,
                llm_model=meta.get("model"),
                tokens_in=meta.get("tokens_in"),
                tokens_out=meta.get("tokens_out"),
            )
            transition_state(
                db, lead, new_state=LeadState.OUTREACHED, trigger="cron_outreach"
            )
            job.status = OutreachStatus.SENT
            job.sent_at = datetime.utcnow()
            await asyncio.sleep(2)  # gentle pacing within tick
