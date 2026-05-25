from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.bridge import BridgeError, send_message
from app.config import get_settings
from app.conversation import handle_inbound
from app.db import get_db
from app.notify import notify_lead_ready_for_call, notify_llm_failure
from app.schemas import WebhookMessageIn, WebhookMessageOut

logger = logging.getLogger(__name__)
router = APIRouter()

# Per-lead lock: prevents concurrent LLM calls for the same number.
_lead_locks: dict[str, asyncio.Lock] = {}


def _check_bridge_token(x_bridge_token: str | None) -> None:
    s = get_settings()
    if not s.bridge_token:
        return  # no token configured -> open
    if x_bridge_token != s.bridge_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid bridge token")


@router.post("/webhook/wa", response_model=WebhookMessageOut)
async def webhook_wa(
    payload: WebhookMessageIn,
    x_bridge_token: str | None = Header(default=None, alias="X-Bridge-Token"),
    db: Session = Depends(get_db),
) -> WebhookMessageOut:
    _check_bridge_token(x_bridge_token)

    # Whitelist check — skip if ALLOWED_NUMBERS is set and number not in list
    s = get_settings()
    allowed = s.allowed_numbers_list
    if allowed and payload.wa_number not in allowed:
        logger.info("ignoring message from non-whitelisted number: %s", payload.wa_number)
        return WebhookMessageOut(reply="", state="NEW", skipped=True, reason="not whitelisted")
        _lead_locks[payload.wa_number] = asyncio.Lock()
    if payload.wa_number not in _lead_locks:
        _lead_locks[payload.wa_number] = asyncio.Lock()
    lock = _lead_locks[payload.wa_number]

    async with lock:
        reply, new_state, escalate = await handle_inbound(
            db,
            wa_number=payload.wa_number,
            body=payload.body,
            message_id=payload.message_id,
        )
        db.commit()

    # Re-fetch lead for notify side-effect
    from app.models import Lead, LeadState
    from app.state import ESCALATE_STATES

    lead = db.query(Lead).filter(Lead.wa_number == payload.wa_number).one()

    try:
        if reply:
            await send_message(payload.wa_number, reply, reply_jid=payload.reply_jid)
    except BridgeError as e:
        logger.error("failed to send reply via bridge: %s", e)

    if escalate and lead.state in ESCALATE_STATES:
        await notify_lead_ready_for_call(lead.name or "", lead.wa_number, payload.body)
    elif escalate and not reply:
        await notify_llm_failure(payload.wa_number, "LLM call failed; bot diam (silent fail)")

    return WebhookMessageOut(reply=reply, state=new_state)
