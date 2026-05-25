from __future__ import annotations

import re

from app.models import LeadState

# Regex sebagai safety net — sinyal LLM (suggested_state) adalah sumber primer.
# Pola lower-case; matching dilakukan setelah .lower().

_PATTERNS_AGREE_CALL = [
    r"\bboleh\s*(kak|dok|pak|bu)?\s*(ditelp|telp|telepon|call)\b",
    r"\b(silakan|silahkan)\b.*\b(telp|telepon|call)\b",
    r"\b(ok\.?e?|oke|sip|siap|gas|ayo)\b.{0,15}\b(telp|telepon|call)\b",
    r"\b(telp|telepon|call)\b.{0,10}\b(aja|saja|ya|yuk|dong)\b",
    r"\bbisa\b.{0,15}\b(telp|telepon|call)\b",
    r"\bayo\s*(telp|telepon|call)\b",
]

_PATTERNS_DECLINE = [
    r"\b(ga|gak|nggak|tidak|tdk|engga|enggak)\s*(butuh|tertarik|minat|perlu)\b",
    r"\bstop\b",
    r"\bjangan\s*(chat|kirim|hubungi)\b",
    r"\bblok(ir)?\b",
    r"\bmaaf\s*(ga|gak|tidak)\s*(butuh|tertarik|minat)\b",
]

_PATTERNS_PRICE_QUESTION = [
    r"\b(harga|biaya|tarif|cost|price)\b",
    r"\bberapa(an|nya)?\b.*\b(bayar|biaya|harga)\b",
    r"\b(paket|berapa)\s*(an|nya)?\b",
]

_PATTERNS_PORTFOLIO_REQUEST = [
    r"\b(contoh|portfolio|portofolio|sample|hasil)\b",
    r"\bbisa\s*(lihat|liat)\s*(contoh|hasil)\b",
]

_PATTERNS_POSITIVE_FEEDBACK = [
    r"\b(bagus|keren|menarik|oke|mantap|wah|wow|tertarik)\b",
    r"\bsuka\s*(banget|sekali)?\b",
]


def _match_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def detect_intent(message: str) -> str:
    """Return a coarse intent label from regex inspection."""
    if not message:
        return "other"
    text = message.lower().strip()
    if _match_any(text, _PATTERNS_DECLINE):
        return "declining"
    if _match_any(text, _PATTERNS_AGREE_CALL):
        return "agreeing_call"
    if _match_any(text, _PATTERNS_PRICE_QUESTION):
        return "asking_price"
    if _match_any(text, _PATTERNS_PORTFOLIO_REQUEST):
        return "asking_portfolio"
    if _match_any(text, _PATTERNS_POSITIVE_FEEDBACK):
        return "positive_feedback"
    return "other"


def fallback_state_from_intent(current: LeadState, intent: str) -> LeadState | None:
    """Best-effort fallback transition kalau LLM tidak kasih suggested_state valid."""
    if intent == "declining":
        return LeadState.CLOSED_LOST
    if intent == "agreeing_call" and current in {
        LeadState.WARM,
        LeadState.PORTFOLIO_SENT,
        LeadState.READY_FOR_CALL,
        LeadState.FOLLOW_UP_1,
        LeadState.FOLLOW_UP_3,
        LeadState.FOLLOW_UP_7,
        LeadState.FOLLOW_UP_14,
    }:
        return LeadState.READY_FOR_CALL
    if intent == "positive_feedback" and current == LeadState.PORTFOLIO_SENT:
        return LeadState.READY_FOR_CALL
    if current == LeadState.OUTREACHED:
        # any reply moves OUTREACHED -> WARM
        return LeadState.WARM
    return None
