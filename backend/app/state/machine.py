from __future__ import annotations

from app.models import LeadState

# Allowed transitions. Keys = from-state, values = set of valid to-states.
# Guards eksternal (cron untuk follow-up, manual override) bypass tabel ini.

ALLOWED_TRANSITIONS: dict[LeadState, set[LeadState]] = {
    LeadState.NEW: {LeadState.OUTREACHED, LeadState.INVALID, LeadState.ARCHIVED},
    LeadState.OUTREACHED: {
        LeadState.WARM,
        LeadState.CLOSED_LOST,
        LeadState.ARCHIVED,
        LeadState.FOLLOW_UP_1,
    },
    LeadState.WARM: {
        LeadState.PORTFOLIO_SENT,
        LeadState.READY_FOR_CALL,
        LeadState.CLOSED_LOST,
        LeadState.ARCHIVED,
    },
    LeadState.PORTFOLIO_SENT: {
        LeadState.READY_FOR_CALL,
        LeadState.WARM,
        LeadState.CLOSED_LOST,
        LeadState.ARCHIVED,
    },
    LeadState.READY_FOR_CALL: {
        LeadState.CALL_SCHEDULED,
        LeadState.WARM,
        LeadState.CLOSED_LOST,
        LeadState.ARCHIVED,
    },
    LeadState.CALL_SCHEDULED: {
        LeadState.FOLLOW_UP_1,
        LeadState.CLOSED_WON,
        LeadState.CLOSED_LOST,
        LeadState.ARCHIVED,
    },
    LeadState.FOLLOW_UP_1: {
        LeadState.FOLLOW_UP_3,
        LeadState.READY_FOR_CALL,
        LeadState.CLOSED_WON,
        LeadState.CLOSED_LOST,
        LeadState.ARCHIVED,
    },
    LeadState.FOLLOW_UP_3: {
        LeadState.FOLLOW_UP_7,
        LeadState.READY_FOR_CALL,
        LeadState.CLOSED_WON,
        LeadState.CLOSED_LOST,
        LeadState.ARCHIVED,
    },
    LeadState.FOLLOW_UP_7: {
        LeadState.FOLLOW_UP_14,
        LeadState.READY_FOR_CALL,
        LeadState.CLOSED_WON,
        LeadState.CLOSED_LOST,
        LeadState.ARCHIVED,
    },
    LeadState.FOLLOW_UP_14: {
        LeadState.ARCHIVED,
        LeadState.READY_FOR_CALL,
        LeadState.CLOSED_WON,
        LeadState.CLOSED_LOST,
    },
    LeadState.CLOSED_WON: set(),
    LeadState.CLOSED_LOST: set(),
    LeadState.ARCHIVED: set(),
    LeadState.INVALID: set(),
}

# State yang menandakan owner perlu tahu segera.
ESCALATE_STATES = {LeadState.READY_FOR_CALL, LeadState.CALL_SCHEDULED, LeadState.CLOSED_WON}


def can_transition(from_state: LeadState, to_state: LeadState) -> bool:
    if from_state == to_state:
        return False
    return to_state in ALLOWED_TRANSITIONS.get(from_state, set())


def resolve_transition(
    current: LeadState, suggested: LeadState | None, fallback: LeadState | None
) -> LeadState | None:
    """Pilih state baru: prioritas suggested LLM, lalu fallback regex.

    Hanya kembalikan state baru kalau benar-benar valid menurut tabel transisi.
    """
    for candidate in (suggested, fallback):
        if candidate is None:
            continue
        if can_transition(current, candidate):
            return candidate
    return None
