"""Telegram Bot API client — send alerts and scan authorized channels."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from wigs.config import get_settings

settings = get_settings()
BASE_URL = "https://api.telegram.org"


def _message_text(message: dict) -> str:
    return (
        message.get("text")
        or message.get("caption")
        or message.get("channel_post", {}).get("text")
        or ""
    )


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
    try:
        if client is not None:
            resp = await client.post(
                url,
                json={"chat_id": target, "text": text, "parse_mode": parse_mode},
            )
        else:
            async with httpx.AsyncClient(timeout=10) as c:
                resp = await c.post(
                    url,
                    json={"chat_id": target, "text": text, "parse_mode": parse_mode},
                )
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def scan_authorized_channels(
    bot_token: str,
    channel_ids: list[str],
    query: str,
    limit: int = 20,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    if not bot_token or not channel_ids or not query:
        return []

    url = f"{BASE_URL}/bot{bot_token}/getUpdates"
    normalized_ids = {str(channel_id) for channel_id in channel_ids}
    lowered_query = query.lower()

    try:
        if client is not None:
            resp = await client.get(url, params={"limit": max(limit * 3, 20), "timeout": 0})
        else:
            async with httpx.AsyncClient(timeout=15) as c:
                resp = await c.get(url, params={"limit": max(limit * 3, 20), "timeout": 0})
        if resp.status_code != 200:
            return []
        payload = resp.json()
    except httpx.HTTPError:
        return []

    matches: list[dict] = []
    for update in payload.get("result", []):
        message = update.get("channel_post") or update.get("message") or {}
        chat = message.get("chat", {})
        channel_id = str(chat.get("id", ""))
        text = _message_text(message)
        if channel_id not in normalized_ids or lowered_query not in text.lower():
            continue
        matches.append(
            {
                "channel_id": channel_id,
                "message_id": message.get("message_id"),
                "text": text,
                "date": datetime.fromtimestamp(message.get("date", 0), tz=timezone.utc).isoformat(),
                "author_id": message.get("from", {}).get("id"),
            }
        )
        if len(matches) >= limit:
            break
    return matches
