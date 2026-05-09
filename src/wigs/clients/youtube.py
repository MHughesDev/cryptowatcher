"""YouTube Data API v3 client — video/short mention tracking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from wigs.config import get_settings

settings = get_settings()
BASE_URL = "https://www.googleapis.com/youtube/v3"


@dataclass
class VideoMention:
    video_id: str
    title: str
    channel: str
    published: datetime | None
    view_count: int = 0


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=10))
async def search_video_mentions(
    terms: list[str],
    *,
    window_days: int = 7,
    max_results: int = 10,
    client: httpx.AsyncClient | None = None,
) -> list[VideoMention]:
    if not settings.youtube_api_key or not settings.enable_youtube:
        return []

    published_after = (datetime.utcnow() - timedelta(days=window_days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    query = " OR ".join(terms[:2])

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "publishedAfter": published_after,
        "maxResults": max_results,
        "key": settings.youtube_api_key,
    }

    async with (client or httpx.AsyncClient(timeout=15)) as c:
        try:
            resp = await c.get(f"{BASE_URL}/search", params=params)
            if resp.status_code != 200:
                return []
            items = resp.json().get("items", [])
            return [
                VideoMention(
                    video_id=item["id"]["videoId"],
                    title=item["snippet"]["title"],
                    channel=item["snippet"]["channelTitle"],
                    published=datetime.fromisoformat(
                        item["snippet"]["publishedAt"].replace("Z", "+00:00")
                    ),
                )
                for item in items
                if item["id"].get("kind") == "youtube#video"
            ]
        except Exception:
            return []
