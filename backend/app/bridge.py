from __future__ import annotations

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class BridgeError(Exception):
    pass


async def send_message(wa_number: str, text: str, reply_jid: str | None = None) -> str | None:
    """Send a WhatsApp message via the Baileys bridge. Returns message_id if available."""
    s = get_settings()
    url = f"{s.bridge_url.rstrip('/')}/send"
    headers = {"X-Bridge-Token": s.bridge_token, "Content-Type": "application/json"}
    payload: dict = {"wa_number": wa_number, "text": text}
    if reply_jid:
        payload["reply_jid"] = reply_jid
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as e:
        raise BridgeError(f"bridge unreachable: {e}") from e
    if res.status_code >= 400:
        raise BridgeError(f"bridge {res.status_code}: {res.text[:200]}")
    data = res.json()
    return data.get("message_id")


async def is_ready() -> bool:
    s = get_settings()
    url = f"{s.bridge_url.rstrip('/')}/health"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(url)
        return bool(res.json().get("ready"))
    except Exception as e:
        logger.warning("bridge health check failed: %s", e)
        return False
