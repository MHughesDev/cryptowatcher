"""Discord webhook client — send alert embeds."""

from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from wigs.config import get_settings

settings = get_settings()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def send_webhook(
    content: str,
    *,
    username: str = "WIGS",
    client: httpx.AsyncClient | None = None,
) -> bool:
    if not settings.discord_alert_webhook_url:
        return False
    payload = {"content": content, "username": username}
    async with (client or httpx.AsyncClient(timeout=10)) as c:
        resp = await c.post(settings.discord_alert_webhook_url, json=payload)
        return resp.status_code in (200, 204)
