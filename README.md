# WA Bot Klinik — Sales Chatbot Website & SEO

Bot WhatsApp untuk outreach, engage, dan arahkan pemilik klinik ke telepon 15 menit. Backend Python (FastAPI) + bridge Baileys (Node.js) + OpenRouter LLM.

## Stack
- **Backend:** Python 3.11, FastAPI, SQLAlchemy, APScheduler
- **WA Bridge:** Node.js 20, @whiskeysockets/baileys
- **DB:** SQLite (path: `data/bot.db`)
- **LLM:** OpenRouter (default `deepseek/deepseek-v4-flash:nitro`)

## Setup pertama kali

### 1. Clone & env
```bash
cd wa-bot-klinik
cp .env.example .env
# edit .env — minimal isi: OPENROUTER_API_KEY, OWNER_WA_NUMBER,
# BACKEND_ADMIN_TOKEN, BRIDGE_TOKEN
```

### 2. Backend (Python)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
# init DB + buat tabel
python -m app.cli.init_db
# run
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. Baileys bridge (Node.js)
```bash
cd baileys-bridge
npm install
node src/index.js
# scan QR di terminal dengan WhatsApp bot account
# session tersimpan di ./sessions/, persist antar restart
```

### 4. Import lead awal
```bash
cd backend
python -m app.cli.import_leads --csv ../data/leads.csv --dry-run
python -m app.cli.import_leads --csv ../data/leads.csv
```

## Operasi harian
- Outreach scheduler & follow-up jalan otomatis di backend (APScheduler).
- Cek `GET /admin/leads?state=READY_FOR_CALL` untuk lead yang minta call.
- Approve/override state lewat `POST /admin/leads/{id}/state`.

## Struktur project
Lihat plan di `/Users/nuges/.claude/plans/ethereal-riding-dewdrop.md`.

## Deployment (VPS Ubuntu)
- Backend: systemd unit `wa-bot-backend.service`.
- Bridge: PM2 `pm2 start baileys-bridge/src/index.js --name wa-bridge`.
- Reverse proxy nginx hanya jika backend perlu diakses dari luar (default semua localhost).

