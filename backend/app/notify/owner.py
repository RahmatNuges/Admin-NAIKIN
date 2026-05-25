from __future__ import annotations

import logging

from app.bridge import BridgeError, send_message
from app.config import get_settings

logger = logging.getLogger(__name__)


async def notify_owner(message: str) -> None:
    s = get_settings()
    number = s.effective_alert_number
    if not number:
        logger.warning("no alert number configured — skipping notification: %s", message)
        return
    try:
        await send_message(number, f"[BOT-NOTIF] {message}")
    except BridgeError as e:
        logger.error("failed to notify owner: %s", e)


async def notify_lead_ready_for_call(lead_name: str, wa_number: str, last_message: str) -> None:
    snippet = (last_message or "").strip()
    if len(snippet) > 200:
        snippet = snippet[:200] + "..."
    msg = (
        f"Lead siap call: {lead_name or '(no name)'} ({wa_number}).\n"
        f"Pesan terakhir: \"{snippet}\".\n"
        f"Cek admin endpoint untuk detail."
    )
    await notify_owner(msg)


async def notify_llm_failure(wa_number: str, error: str) -> None:
    await notify_owner(f"LLM error untuk {wa_number}: {error}. Bot diam, perlu takeover manual.")
