"""Reddit Data API client — social mention velocity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from wigs.config import get_settings

settings = get_settings()

TARGET_SUBREDDITS = [
    "solana", "SolanaMemeCoins", "CryptoMoonShots", "memecoinmillionaire",
    "defi", "CryptoCurrency", "altcoin",
]


@dataclass
class MentionRecord:
    text: str
    account_id: str
    account_age_days: int
    source: str
    created_utc: datetime
    url: str = ""


async def _get_access_token(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        "https://www.reddit.com/api/v1/access_token",
        data={"grant_type": "client_credentials"},
        auth=(settings.reddit_client_id, settings.reddit_client_secret),
        headers={"User-Agent": settings.reddit_user_agent},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=15))
async def search_mentions(
    terms: list[str],
    *,
    subreddits: list[str] | None = None,
    window_hours: int = 24,
) -> list[MentionRecord]:
    if not settings.reddit_client_id:
        return []

    subs = subreddits or TARGET_SUBREDDITS
    sub_str = "+".join(subs)
    since = datetime.utcnow() - timedelta(hours=window_hours)
    results: list[MentionRecord] = []

    async with httpx.AsyncClient(
        headers={"User-Agent": settings.reddit_user_agent},
        timeout=20,
    ) as client:
        token = await _get_access_token(client)
        auth_headers = {
            "User-Agent": settings.reddit_user_agent,
            "Authorization": f"Bearer {token}",
        }

        for term in terms[:3]:  # limit to 3 terms to stay within rate limits
            resp = await client.get(
                f"https://oauth.reddit.com/r/{sub_str}/search",
                params={"q": term, "sort": "new", "limit": 25, "restrict_sr": "true"},
                headers=auth_headers,
            )
            if resp.status_code != 200:
                continue
            for post in resp.json().get("data", {}).get("children", []):
                data = post["data"]
                created = datetime.utcfromtimestamp(data["created_utc"])
                if created < since:
                    continue
                results.append(MentionRecord(
                    text=f"{data.get('title', '')} {data.get('selftext', '')}",
                    account_id=data.get("author", ""),
                    account_age_days=0,  # would require separate API call
                    source="reddit",
                    created_utc=created,
                    url=f"https://reddit.com{data.get('permalink', '')}",
                ))

    return results
