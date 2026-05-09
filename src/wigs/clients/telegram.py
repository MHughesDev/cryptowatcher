"""Telegram Bot API client — send alerts and scan authorized channels."""

from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from wigs.config import get_settings

settings = get_settings()
BASE_URL = "https://api.telegram.org"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def send_message(
    text: str,
    *,
    chat_id: str | None = None,
    parse_mode: str = "HTML",
    client: httpx.AsyncClient | None = None,
) -> bool:
    """Send a message to the configured alert chat. Returns True on success."""
    if not settings.telegram_bot_token:
        return False
    target = chat_id or settings.telegram_alert_chat_id
    url = f"{BASE_URL}/bot{settings.telegram_bot_token}/sendMessage"
    async with (client or httpx.AsyncClient(timeout=10)) as c:
        resp = await c.post(url, json={"chat_id": target, "text": text, "parse_mode": parse_mode})
        return resp.status_code == 200
