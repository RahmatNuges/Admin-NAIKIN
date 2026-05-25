from app.models import Lead, LeadState
from app.llm.prompts import build_system_prompt


def _make_lead(state=LeadState.NEW, **kwargs) -> Lead:
    defaults = dict(
        wa_number="6281234567890",
        name="dr. Andi",
        clinic_name="Klinik Sehat",
        clinic_type="umum",
        city="Jakarta",
        state=state,
    )
    defaults.update(kwargs)
    return Lead(**defaults)


def test_prompt_includes_profile():
    lead = _make_lead()
    p = build_system_prompt(lead)
    assert "dr. Andi" in p
    assert "Klinik Sehat" in p
    assert "Jakarta" in p
    assert "JSON" in p  # output format embedded


def test_prompt_changes_with_state():
    lead = _make_lead()
    p_new = build_system_prompt(lead, LeadState.NEW)
    p_warm = build_system_prompt(lead, LeadState.WARM)
    assert p_new != p_warm
    assert "Outreach pertama" in p_new
    assert "naikin.xyz" in p_warm or "portfolio" in p_warm.lower()


def test_prompt_minimal_profile():
    lead = Lead(wa_number="628000", state=LeadState.NEW)
    p = build_system_prompt(lead)
    assert "profil minim" in p.lower()


def test_prompt_includes_pricing_rule():
    lead = _make_lead(state=LeadState.WARM)
    p = build_system_prompt(lead)
    assert "harga" in p.lower()
    assert "call" in p.lower() or "telp" in p.lower() or "telepon" in p.lower()
