from app.models import LeadState
from app.state.triggers import detect_intent, fallback_state_from_intent


def test_decline_intent():
    assert detect_intent("Maaf ga butuh") == "declining"
    assert detect_intent("STOP") == "declining"
    assert detect_intent("nggak tertarik") == "declining"


def test_agree_call_intent():
    assert detect_intent("boleh telp") == "agreeing_call"
    assert detect_intent("Ok call aja") == "agreeing_call"
    assert detect_intent("siap, telepon ya") == "agreeing_call"


def test_price_intent():
    assert detect_intent("berapa harganya?") == "asking_price"
    assert detect_intent("biaya paket berapa") == "asking_price"


def test_portfolio_intent():
    assert detect_intent("ada contoh hasilnya?") == "asking_portfolio"
    assert detect_intent("bisa lihat portofolio?") == "asking_portfolio"


def test_positive_intent():
    assert detect_intent("Wah keren!") == "positive_feedback"
    assert detect_intent("menarik nih") == "positive_feedback"


def test_other_intent_default():
    assert detect_intent("hmm") == "other"
    assert detect_intent("") == "other"


def test_fallback_decline_to_lost():
    assert fallback_state_from_intent(LeadState.WARM, "declining") == LeadState.CLOSED_LOST


def test_fallback_agree_call_from_warm():
    assert fallback_state_from_intent(LeadState.WARM, "agreeing_call") == LeadState.READY_FOR_CALL


def test_fallback_outreached_any_reply_warms():
    assert fallback_state_from_intent(LeadState.OUTREACHED, "other") == LeadState.WARM


def test_fallback_no_change_when_state_terminal():
    assert fallback_state_from_intent(LeadState.CLOSED_WON, "other") is None
