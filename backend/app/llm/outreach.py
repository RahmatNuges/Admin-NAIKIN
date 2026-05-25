from __future__ import annotations

from app.config import get_settings
from app.llm.client import LLMClient
from app.models import Lead

OUTREACH_SYSTEM = """\
Kamu adalah Nuges dari NAIKIN. Tugas kamu: tulis 1 (SATU) pesan WhatsApp pertama ke \
pemilik klinik. Tujuannya HANYA memastikan ini nomor yang benar dan bikin mereka balas.

Ini seperti "mengetuk pintu" — bukan jualan, bukan perkenalan panjang.

Aturan KETAT:
- Maksimal 1-2 kalimat SAJA. Sangat singkat.
- TIDAK BOLEH ada link, URL, atau attachment.
- TIDAK BOLEH sebut produk, website, SEO, atau NAIKIN.
- TIDAK BOLEH basa-basi panjang.
- Gunakan variasi template di bawah sebagai inspirasi — jangan copy paste persis.
- Sesuaikan dengan nama klinik / jenis klinik / kota kalau ada datanya.
- Kalau tidak ada data, pakai sapaan umum yang natural.

Variasi template (pilih satu dan adaptasi):
1. "Halo kak, benar ini dari [nama klinik]?"
2. "Permisi kak, ini [nama klinik] di [kota] ya?"
3. "Halo kak, ini nomor klinik [nama] ya?"
4. "Selamat siang kak, benar ini dari klinik [jenis] di [kota]?"
5. "Halo kak, maaf ganggu — ini [nama klinik] ya?"

Output: HANYA teks pesan, no quotes, no markdown, no penjelasan tambahan.
"""


def _build_user_prompt(lead: Lead) -> str:
    bits = []
    if lead.name:
        bits.append(f"Nama kontak: {lead.name}")
    if lead.clinic_name:
        bits.append(f"Nama klinik: {lead.clinic_name}")
    if lead.clinic_type:
        bits.append(f"Jenis klinik: {lead.clinic_type}")
    if lead.city:
        bits.append(f"Kota: {lead.city}")
    if not bits:
        bits.append("(tidak ada data profil — pakai sapaan umum)")
    return "Data prospek:\n" + "\n".join(f"- {b}" for b in bits) + "\n\nTulis pesan DM pertama:"


async def generate_outreach_message(lead: Lead, llm: LLMClient | None = None) -> tuple[str, dict]:
    client = llm or LLMClient()
    messages = [
        {"role": "system", "content": OUTREACH_SYSTEM},
        {"role": "user", "content": _build_user_prompt(lead)},
    ]
    text, meta = await client.chat(messages, temperature=0.95, max_tokens=100)
    text = text.strip().strip('"').strip("'")
    return text, meta
