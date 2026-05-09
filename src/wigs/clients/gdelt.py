"""GDELT 2.0 DOC API client — real-world event/news correlation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import quote_plus

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"


@dataclass
class NewsArticle:
    url: str
    title: str
    source: str
    published: datetime | None
    relevance: float = 0.0


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=10))
async def search_news_events(
    terms: list[str],
    *,
    window_days: int = 7,
    max_records: int = 20,
    client: httpx.AsyncClient | None = None,
) -> list[NewsArticle]:
    if not terms:
        return []

    query = " OR ".join(f'"{t}"' for t in terms[:3])
    start = (datetime.utcnow() - timedelta(days=window_days)).strftime("%Y%m%d%H%M%S")

    params = {
        "query": query,
        "mode": "artlist",
        "maxrecords": max_records,
        "startdatetime": start,
        "format": "json",
    }

    async with (client or httpx.AsyncClient(timeout=20)) as c:
        try:
            resp = await c.get(DOC_API, params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()
            articles = []
            for item in data.get("articles", []):
                articles.append(NewsArticle(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    source=item.get("domain", ""),
                    published=None,
                    relevance=float(item.get("socialshares", 0)),
                ))
            return articles
        except Exception:
            return []
