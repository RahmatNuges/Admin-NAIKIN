from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import get_settings
from app.llm import LLMClient, LLMError, build_system_prompt
from app.models import Conversation, Lead, LeadState, MessageDirection, StateLog
from app.state import (
    ESCALATE_STATES,
    detect_intent,
    fallback_state_from_intent,
    resolve_transition,
)

logger = logging.getLogger(__name__)

FALLBACK_REPLY = "Maaf Dok, lagi ada kendala teknis sebentar. Saya balas lagi ya 🙏"


def upsert_lead(db: Session, wa_number: str) -> tuple[Lead, bool]:
    lead = db.query(Lead).filter(Lead.wa_number == wa_number).one_or_none()
    if lead:
        return lead, False
    lead = Lead(wa_number=wa_number, state=LeadState.NEW)
    db.add(lead)
    db.flush()
    return lead, True


def record_inbound(db: Session, lead: Lead, body: str, message_id: str | None) -> Conversation:
    now = datetime.utcnow()
    conv = Conversation(
        lead_id=lead.id,
        direction=MessageDirection.IN,
        body=body,
        wa_message_id=message_id,
    )
    db.add(conv)
    lead.last_inbound_at = now
    return conv


def record_outbound(
    db: Session,
    lead: Lead,
    body: str,
    *,
    llm_model: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    wa_message_id: str | None = None,
) -> Conversation:
    now = datetime.utcnow()
    conv = Conversation(
        lead_id=lead.id,
        direction=MessageDirection.OUT,
        body=body,
        llm_model=llm_model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        wa_message_id=wa_message_id,
    )
    db.add(conv)
    lead.last_outbound_at = now
    return conv


def transition_state(
    db: Session,
    lead: Lead,
    *,
    new_state: LeadState,
    trigger: str,
    note: str | None = None,
) -> None:
    log = StateLog(
        lead_id=lead.id,
        from_state=lead.state,
        to_state=new_state,
        trigger=trigger,
        note=note,
    )
    db.add(log)
    lead.state = new_state


def history_messages(db: Session, lead: Lead, limit: int) -> list[dict[str, str]]:
    db.flush()  # ensure pending writes are visible
    db.expire(lead)  # force reload of relationships from DB
    convs = sorted(lead.conversations, key=lambda c: c.created_at)[-limit:]
    out = []
    for c in convs:
        role = "user" if c.direction == MessageDirection.IN else "assistant"
        out.append({"role": role, "content": c.body})
    return out


def parse_suggested_state(value) -> LeadState | None:
    if not value:
        return None
    if isinstance(value, LeadState):
        return value
    try:
        return LeadState(str(value).upper().strip())
    except ValueError:
        return None


async def handle_inbound(
    db: Session,
    *,
    wa_number: str,
    body: str,
    message_id: str | None,
    llm: LLMClient | None = None,
) -> tuple[str, LeadState, bool]:
    """Process an incoming WA message. Returns (reply_text, new_state, escalate_flag).

    Caller is responsible for committing the session and sending the reply.
    """
    s = get_settings()
    lead, _created = upsert_lead(db, wa_number)
    record_inbound(db, lead, body, message_id)

    if lead.state in {LeadState.CLOSED_WON, LeadState.CLOSED_LOST, LeadState.ARCHIVED}:
        # Cold lead replied — re-open conversation as WARM (fresh contact attempt)
        transition_state(
            db, lead, new_state=LeadState.WARM, trigger="reopen", note="lead replied after closed"
        )

    client = llm or LLMClient()
    system_prompt = build_system_prompt(lead)
    convo_history = history_messages(db, lead, s.conversation_history_limit)

    # Inject JSON reminder into last user message to enforce output format
    if convo_history and convo_history[-1]["role"] == "user":
        convo_history[-1] = {
            "role": "user",
            "content": convo_history[-1]["content"] + "\n\n[WAJIB: Balas dalam JSON valid sesuai schema di system prompt. Jangan balas dengan teks biasa.]",
        }

    messages = [{"role": "system", "content": system_prompt}, *convo_history]

    reply_text = FALLBACK_REPLY
    suggested_state: LeadState | None = None
    intent: str | None = None
    meta: dict = {}
    llm_failed = False

    try:
        parsed, meta = await client.chat_json(messages, temperature=0.7, max_tokens=2000, json_mode=False)
        reply_text = (parsed.get("reply") or "").strip() or FALLBACK_REPLY
        suggested_state = parse_suggested_state(parsed.get("suggested_state"))
        intent = parsed.get("detected_intent")
    except LLMError as e:
        logger.error("LLM call failed for %s: %s", wa_number, e)
        llm_failed = True
        return "", lead.state, True  # silent fail — no reply sent

    if not intent:
        intent = detect_intent(body)
    fallback_state = fallback_state_from_intent(lead.state, intent)
    new_state = resolve_transition(lead.state, suggested_state, fallback_state)

    record_outbound(
        db,
        lead,
        reply_text,
        llm_model=meta.get("model"),
        tokens_in=meta.get("tokens_in"),
        tokens_out=meta.get("tokens_out"),
    )

    escalate = False
    if new_state and new_state != lead.state:
        trigger_label = "llm" if suggested_state else "regex"
        transition_state(
            db, lead, new_state=new_state, trigger=trigger_label, note=f"intent={intent}"
        )
        if new_state in ESCALATE_STATES:
            escalate = True

    return reply_text, lead.state, (escalate or llm_failed)
