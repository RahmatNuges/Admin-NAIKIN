import { config } from 'dotenv';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
// .env ada di project root: baileys-bridge/src/ -> ../../
config({ path: resolve(__dirname, '../../.env') });
if (!process.env.BRIDGE_TOKEN) {
  // fallback: coba dari cwd
  config({ path: resolve(process.cwd(), '../.env'), override: false });
}
import express from 'express';
import pino from 'pino';
import qrcode from 'qrcode-terminal';
import {
  default as makeWASocket,
  DisconnectReason,
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
} from '@whiskeysockets/baileys';

const log = pino({ level: process.env.LOG_LEVEL || 'info' });

const BRIDGE_PORT = Number(process.env.BRIDGE_PORT || 3000);
const BRIDGE_TOKEN = process.env.BRIDGE_TOKEN || 'change-me';
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
const SESSIONS_DIR = process.env.SESSIONS_DIR || './sessions';

let sock = null;
let isReady = false;

function jidFromNumber(waNumber) {
  const cleaned = String(waNumber).replace(/\D/g, '');
  return `${cleaned}@s.whatsapp.net`;
}

function numberFromJid(jid) {
  // Strip @s.whatsapp.net, @lid, @c.us etc — take only the number part before @
  const raw = String(jid).split('@')[0].split(':')[0];
  // Remove any non-digit characters
  return raw.replace(/\D/g, '');
}

async function resolveNumber(jid, message) {
  // @lid is WhatsApp's internal linked-device ID — try to resolve to real number
  if (jid.endsWith('@lid')) {
    try {
      // Try to get real number from message participant or verifiedBizName
      const participant = message?.participant || message?.key?.participant;
      if (participant) return numberFromJid(participant);
      // Try contact store lookup
      const contact = sock?.store?.contacts?.[jid];
      if (contact?.id) return numberFromJid(contact.id);
      // Fallback: use lid number as-is (will still work for reply)
    } catch (e) {
      log.warn({ err: e.message }, 'lid resolve failed');
    }
  }
  return numberFromJid(jid);
}

function extractBody(message) {
  const msg = message?.message;
  if (!msg) return null;
  return (
    msg.conversation ||
    msg.extendedTextMessage?.text ||
    msg.imageMessage?.caption ||
    msg.videoMessage?.caption ||
    null
  );
}

async function forwardToBackend(payload) {
  try {
    const res = await fetch(`${BACKEND_URL}/webhook/wa`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Bridge-Token': BRIDGE_TOKEN,
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      log.warn({ status: res.status }, 'backend webhook returned non-2xx');
      return null;
    }
    return await res.json();
  } catch (err) {
    log.error({ err: err.message }, 'failed to forward to backend');
    return null;
  }
}

async function startSocket() {
  const { state, saveCreds } = await useMultiFileAuthState(SESSIONS_DIR);
  const { version } = await fetchLatestBaileysVersion();

  sock = makeWASocket({
    version,
    auth: state,
    printQRInTerminal: false,
    logger: pino({ level: 'silent' }),
    syncFullHistory: false,
    markOnlineOnConnect: false,
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      log.info('scan QR code below to pair WhatsApp account:');
      qrcode.generate(qr, { small: true });
    }
    if (connection === 'open') {
      isReady = true;
      log.info('whatsapp connection open — bridge ready');
    } else if (connection === 'close') {
      isReady = false;
      const code = lastDisconnect?.error?.output?.statusCode;
      const shouldReconnect = code !== DisconnectReason.loggedOut;
      log.warn({ code, shouldReconnect }, 'whatsapp connection closed');
      if (shouldReconnect) {
        setTimeout(() => startSocket().catch((e) => log.error(e, 'reconnect failed')), 3000);
      } else {
        log.error('logged out — delete sessions/ and re-pair');
      }
    }
  });

  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    log.info({ type, count: messages.length }, 'messages.upsert event');
    for (const m of messages) {
      if (m.key.fromMe) continue;
      if (m.key.remoteJid?.endsWith('@g.us')) continue; // skip group messages
      const body = extractBody(m);
      log.info({ type, jid: m.key.remoteJid, hasBody: !!body }, 'message detail');
      if (!body) continue;

      const waNumber = await resolveNumber(m.key.remoteJid, m);
      const replyJid = m.key.remoteJid; // always reply to original JID (works for @lid too)
      const payload = {
        wa_number: waNumber,
        reply_jid: replyJid,
        body,
        timestamp: Number(m.messageTimestamp) || Math.floor(Date.now() / 1000),
        message_id: m.key.id,
      };
      log.info({ waNumber, len: body.length }, 'incoming message');
      await forwardToBackend(payload);
    }
  });
}

const app = express();
app.use(express.json({ limit: '256kb' }));

app.use((req, res, next) => {
  if (req.path === '/health') return next();
  if (req.headers['x-bridge-token'] !== BRIDGE_TOKEN) {
    return res.status(401).json({ error: 'unauthorized' });
  }
  next();
});

app.get('/health', (_req, res) => {
  res.json({ ready: isReady });
});

app.post('/send', async (req, res) => {
  if (!isReady || !sock) {
    return res.status(503).json({ error: 'whatsapp not connected' });
  }
  const { wa_number, text, reply_jid } = req.body || {};
  if (!wa_number || !text) {
    return res.status(400).json({ error: 'wa_number and text required' });
  }
  try {
    // Prefer reply_jid (preserves @lid for multi-device), fallback to constructed JID
    const jid = reply_jid || jidFromNumber(wa_number);
    const result = await sock.sendMessage(jid, { text });
    log.info({ wa_number, jid, len: text.length }, 'sent message');
    return res.json({ ok: true, message_id: result?.key?.id || null });
  } catch (err) {
    log.error({ err: err.message }, 'send failed');
    return res.status(500).json({ error: err.message });
  }
});

app.listen(BRIDGE_PORT, () => {
  log.info({ port: BRIDGE_PORT }, 'bridge http server listening');
});

startSocket().catch((err) => {
  log.error({ err: err.message }, 'startSocket failed');
  process.exit(1);
});
