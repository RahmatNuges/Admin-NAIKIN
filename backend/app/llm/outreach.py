from __future__ import annotations

from app.config import get_settings
from app.llm.client import LLMClient
from app.models import Lead

OUTREACH_SYSTEM = """\
Kamu adalah konsultan digital yang bantu klinik dapet pasien baru lewat website + SEO. \
Tugas kamu: tulis 1 (SATU) pesan WhatsApp DM pertama ke prospek klinik. Tone hangat, \
ngobrol kayak teman, bukan sales agresif.

Aturan ketat:
- Maksimal 2-3 kalimat pendek. Total <300 karakter.
- TIDAK BOLEH ada link, URL, atau attachment.
- TIDAK BOLEH bilang harga, paket, atau angka apa pun.
- TIDAK BOLEH pakai kata "promo", "diskon", "spesial", "penawaran".
- Sapa: "Dok" untuk dokter, "Pak/Bu" untuk non-dokter. Default "Dok" kalau ragu.
- Sebut nama klinik & kota dengan natural (kalau ada).
- Akhiri dengan 1 pertanyaan ringan yang gampang dijawab.
- Tujuan: bikin prospek mau balas, bukan langsung jualan.

Output: HANYA teks pesan, no quotes, no markdown, no penjelasan tambahan.
"""


def _build_user_prompt(lead: Lead) -> str:
    bits = []
    if lead.name:
        bits.append(f"Nama prospek: {lead.name}")
    if lead.clinic_name:
        bits.append(f"Klinik: {lead.clinic_name}")
    if lead.clinic_type:
        bits.append(f"Jenis klinik: {lead.clinic_type}")
    if lead.city:
        bits.append(f"Kota: {lead.city}")
    if not bits:
        bits.append("(profil minim — pakai sapaan umum)")
    return "Profil prospek:\n" + "\n".join(f"- {b}" for b in bits) + "\n\nTulis pesan DM-nya:"


async def generate_outreach_message(lead: Lead, llm: LLMClient | None = None) -> tuple[str, dict]:
    s = get_settings()
    client = llm or LLMClient()
    messages = [
        {"role": "system", "content": OUTREACH_SYSTEM},
        {"role": "user", "content": _build_user_prompt(lead)},
    ]
    text, meta = await client.chat(messages, temperature=0.85, max_tokens=200)
    text = text.strip().strip('"').strip("'")
    if s.business_name and s.business_name.lower() not in text.lower():
        # tidak wajib, hanya log — tetap kirim
        pass
    return text, meta
