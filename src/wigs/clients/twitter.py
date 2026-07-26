"""Twitter / X social mention client — uses twikit (unofficial internal API).

twikit requires no API key. Credentials are a plain X account username + password.
The feature flag ENABLE_TWITTER defaults to False. Enable only intentionally.

What this is used for:
  - Search tweets/posts mentioning a token symbol, cashtag ($SYMBOL), or mint address
  - Return mention records with account age and follower count for credibility filtering
  - Feed into social_verifier.py alongside Reddit, YouTube, Telegram, and GDELT
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from wigs.config import get_settings

settings = get_settings()


@dataclass
class MentionRecord:
    text: str
    account_id: str
    account_age_days: int       # 0 if unavailable
    follower_count: int         # used to filter obvious bot/low-quality accounts
    source: str
    created_at: datetime
    url: str = ""


async def search_mentions(
    terms: list[str],
    *,
    window_hours: int = 24,
    max_results_per_term: int = 20,
) -> list[MentionRecord]:
    """Search X for recent mentions of the given terms.

    Returns all mentions within the time window — no filtering by account age or
    follower count. Those values are returned as fields so social_verifier.py can
    weight them in scoring rather than hard-dropping mentions here.

    A new account with few followers still carries signal (viral origin posts,
    organic spread from real newcomers). The scorer decides what to do with it.

    Returns an empty list if ENABLE_TWITTER is False or credentials are missing.
    Silently suppresses errors so a twikit breakage never takes down the pipeline.
    """
    if not settings.enable_twitter:
        return []
    if not settings.twitter_username or not settings.twitter_password:
        return []

    try:
        import twikit  # type: ignore[import]
    except ImportError:
        return []

    try:
        client = twikit.Client(language="en-US")
        await client.login(
            auth_info_1=settings.twitter_username,
            password=settings.twitter_password,
        )
    except Exception:
        return []

    results: list[MentionRecord] = []
    now = datetime.now(timezone.utc)

    for term in terms[:3]:  # cap to 3 terms to keep request volume low
        try:
            tweets = await client.search_tweet(
                query=f"{term} lang:en",
                product="Latest",
                count=max_results_per_term,
            )
        except Exception:
            continue

        for tweet in tweets:
            try:
                user = tweet.user
                created_at = tweet.created_at_datetime
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)

                age_delta = now - created_at
                if age_delta.total_seconds() > window_hours * 3600:
                    continue

                # account age from user creation date
                account_created = getattr(user, "created_at_datetime", None)
                if account_created:
                    if account_created.tzinfo is None:
                        account_created = account_created.replace(tzinfo=timezone.utc)
                    account_age_days = (now - account_created).days
                else:
                    account_age_days = 0

                followers = getattr(user, "followers_count", 0) or 0

                results.append(MentionRecord(
                    text=tweet.text,
                    account_id=str(user.id),
                    account_age_days=account_age_days,
                    follower_count=followers,
                    source="twitter",
                    created_at=created_at,
                    url=f"https://x.com/{user.screen_name}/status/{tweet.id}",
                ))
            except Exception:
                continue

        await asyncio.sleep(1)  # polite pacing between term searches

    return results
