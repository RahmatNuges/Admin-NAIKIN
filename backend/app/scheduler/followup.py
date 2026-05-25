from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bridge import BridgeError, send_message
from app.conversation import record_outbound, transition_state
from app.db import session_scope
from app.llm import LLMClient
from app.llm.client import LLMError
from app.models import Lead, LeadState

logger = logging.getLogger(__name__)

# Tujuan transisi untuk setiap state follow-up.
NEXT_FOLLOWUP: dict[LeadState, tuple[LeadState, int | None]] = {
    LeadState.CALL_SCHEDULED: (LeadState.FOLLOW_UP_1, 1),
    LeadState.FOLLOW_UP_1: (LeadState.FOLLOW_UP_3, 2),
    LeadState.FOLLOW_UP_3: (LeadState.FOLLOW_UP_7, 4),
    LeadState.FOLLOW_UP_7: (LeadState.FOLLOW_UP_14, 7),
    LeadState.FOLLOW_UP_14: (LeadState.ARCHIVED, None),
}

FOLLOWUP_PROMPTS: dict[LeadState, str] = {
    LeadState.FOLLOW_UP_1: (
        "Tulis pesan WhatsApp follow-up H+1 setelah call/diskusi. "
        "Tone casual, tanya kondisi tanpa push. 1-2 kalimat, no link, no harga."
    ),
    LeadState.FOLLOW_UP_3: (
        "Tulis pesan WhatsApp follow-up H+3. "
        "Kasih nilai tambah ringan: tips singkat atau observasi tentang klinik mereka. "
        "1-2 kalimat, no link, no harga."
    ),
    LeadState.FOLLOW_UP_7: (
        "Tulis pesan WhatsApp follow-up H+7 dengan format mini case-study singkat. "
        "Mention klinik dengan kondisi mirip yang dapat hasil bagus. "
        "Maksimal 3 kalimat, no link, no harga."
    ),
    LeadState.FOLLOW_UP_14: (
        "Tulis pesan last follow-up H+14. "
        "Tone respect: kalau lagi ga prioritas, no problem, tetap simpan kontak. "
        "Maksimal 2 kalimat. Tutup dengan respect."
    ),
}

FOLLOWUP_SYSTEM = (
    "Kamu konsultan digital untuk klinik. Tulis HANYA teks pesan WA, "
    "no quotes, no markdown, no link, no harga, no janji hasil spesifik. "
    "Sapa 'Dok' kalau dokter, 'Pak/Bu' kalau owner non-dokter."
)


def _due_leads(db: Session) -> list[Lead]:
    naive_now = datetime.utcnow()
    stmt = (
        select(Lead)
        .where(Lead.next_followup_at != None)  # noqa: E711
        .where(Lead.next_followup_at <= naive_now)
        .where(Lead.state.in_(list(NEXT_FOLLOWUP.keys())))
    )
    return list(db.execute(stmt).scalars())


def _build_user_prompt(lead: Lead, instruction: str) -> str:
    parts = [instruction, "", "Profil prospek:"]
    if lead.name:
        parts.append(f"- Nama: {lead.name}")
    if lead.clinic_name:
        parts.append(f"- Klinik: {lead.clinic_name}")
    if lead.clinic_type:
        parts.append(f"- Jenis: {lead.clinic_type}")
    if lead.city:
        parts.append(f"- Kota: {lead.city}")
    return "\n".join(parts)


async def _send_followup(lead: Lead, instruction: str, llm: LLMClient) -> tuple[str, dict] | None:
    messages = [
        {"role": "system", "content": FOLLOWUP_SYSTEM},
        {"role": "user", "content": _build_user_prompt(lead, instruction)},
    ]
    try:
        text, meta = await llm.chat(messages, temperature=0.8, max_tokens=200)
    except LLMError as e:
        logger.error("followup LLM failed for lead %s: %s", lead.id, e)
        return None
    text = text.strip().strip('"').strip("'")
    try:
        await send_message(lead.wa_number, text)
    except BridgeError as e:
        logger.error("followup send failed for lead %s: %s", lead.id, e)
        return None
    return text, meta


async def run_followup_tick() -> None:
    llm = LLMClient()
    with session_scope() as db:
        leads = _due_leads(db)
        if not leads:
            return
        for lead in leads:
            target_state, delay_days = NEXT_FOLLOWUP.get(lead.state, (None, None))
            if not target_state:
                continue

            instruction = FOLLOWUP_PROMPTS.get(target_state)
            if instruction:
                result = await _send_followup(lead, instruction, llm)
                if result:
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
                db, lead, new_state=target_state, trigger="cron_followup"
            )
            if delay_days:
                lead.next_followup_at = datetime.utcnow() + timedelta(days=delay_days)
            else:
                lead.next_followup_at = None
            await asyncio.sleep(2)
