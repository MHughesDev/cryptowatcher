"""Slack webhook client — send alert messages."""

from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from wigs.config import get_settings

settings = get_settings()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def send_webhook(
    text: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> bool:
    if not settings.slack_alert_webhook_url:
        return False

    payload = {"text": text}
    try:
        if client is not None:
            resp = await client.post(settings.slack_alert_webhook_url, json=payload)
        else:
            async with httpx.AsyncClient(timeout=10) as c:
                resp = await c.post(settings.slack_alert_webhook_url, json=payload)
        return resp.status_code in (200, 201)
    except httpx.HTTPError:
        return False
