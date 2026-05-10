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
    try:
        if client is not None:
            resp = await client.post(settings.discord_alert_webhook_url, json=payload)
        else:
            async with httpx.AsyncClient(timeout=10) as c:
                resp = await c.post(settings.discord_alert_webhook_url, json=payload)
        return resp.status_code in (200, 204)
    except httpx.HTTPError:
        return False


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def scan_authorized_servers(
    bot_token: str,
    channel_ids: list[str],
    query: str,
    limit: int = 20,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    if not bot_token or not channel_ids or not query:
        return []

    headers = {"Authorization": f"Bot {bot_token}"}
    lowered_query = query.lower()
    matches: list[dict] = []

    try:
        if client is None:
            async with httpx.AsyncClient(timeout=15) as c:
                for channel_id in channel_ids:
                    resp = await c.get(
                        f"https://discord.com/api/v10/channels/{channel_id}/messages",
                        params={"limit": min(limit, 100)},
                        headers=headers,
                    )
                    if resp.status_code != 200:
                        continue
                    for message in resp.json():
                        content = message.get("content", "")
                        if lowered_query not in content.lower():
                            continue
                        matches.append(
                            {
                                "channel_id": str(channel_id),
                                "message_id": message.get("id"),
                                "content": content,
                                "timestamp": message.get("timestamp"),
                                "author_id": message.get("author", {}).get("id"),
                            }
                        )
                        if len(matches) >= limit:
                            return matches
        else:
            for channel_id in channel_ids:
                resp = await client.get(
                    f"https://discord.com/api/v10/channels/{channel_id}/messages",
                    params={"limit": min(limit, 100)},
                    headers=headers,
                )
                if resp.status_code != 200:
                    continue
                for message in resp.json():
                    content = message.get("content", "")
                    if lowered_query not in content.lower():
                        continue
                    matches.append(
                        {
                            "channel_id": str(channel_id),
                            "message_id": message.get("id"),
                            "content": content,
                            "timestamp": message.get("timestamp"),
                            "author_id": message.get("author", {}).get("id"),
                        }
                    )
                    if len(matches) >= limit:
                        return matches
    except httpx.HTTPError:
        return matches

    return matches
