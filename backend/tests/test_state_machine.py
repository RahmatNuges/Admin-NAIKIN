from app.models import LeadState
from app.state.machine import (
    can_transition,
    resolve_transition,
)


def test_basic_progression():
    assert can_transition(LeadState.NEW, LeadState.OUTREACHED)
    assert can_transition(LeadState.OUTREACHED, LeadState.WARM)
    assert can_transition(LeadState.WARM, LeadState.PORTFOLIO_SENT)
    assert can_transition(LeadState.PORTFOLIO_SENT, LeadState.READY_FOR_CALL)
    assert can_transition(LeadState.READY_FOR_CALL, LeadState.CALL_SCHEDULED)


def test_skip_states_blocked():
    # cannot skip from NEW directly to CALL_SCHEDULED
    assert not can_transition(LeadState.NEW, LeadState.CALL_SCHEDULED)
    # cannot revert WARM -> NEW
    assert not can_transition(LeadState.WARM, LeadState.NEW)
    # terminal states have no outgoing transitions
    assert not can_transition(LeadState.CLOSED_WON, LeadState.WARM)
    assert not can_transition(LeadState.CLOSED_LOST, LeadState.NEW)
    assert not can_transition(LeadState.ARCHIVED, LeadState.NEW)


def test_self_transition_blocked():
    assert not can_transition(LeadState.WARM, LeadState.WARM)


def test_resolve_prefers_suggested():
    new = resolve_transition(LeadState.WARM, LeadState.PORTFOLIO_SENT, LeadState.READY_FOR_CALL)
    assert new == LeadState.PORTFOLIO_SENT


def test_resolve_falls_back():
    new = resolve_transition(LeadState.WARM, None, LeadState.PORTFOLIO_SENT)
    assert new == LeadState.PORTFOLIO_SENT


def test_resolve_invalid_suggested_uses_fallback():
    # NEW cannot directly go to PORTFOLIO_SENT — must skip suggested
    new = resolve_transition(LeadState.NEW, LeadState.PORTFOLIO_SENT, LeadState.OUTREACHED)
    assert new == LeadState.OUTREACHED


def test_resolve_returns_none_when_nothing_valid():
    new = resolve_transition(LeadState.NEW, LeadState.WARM, LeadState.READY_FOR_CALL)
    assert new is None
