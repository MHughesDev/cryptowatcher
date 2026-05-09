"""Social and narrative verification.

Computes social_score from cross-platform mention velocity, novelty
(bot detection via cosine similarity), unique source diversity, and
real-world event matching via GDELT.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field

from wigs.clients import gdelt, reddit, youtube
from wigs.clients.reddit import MentionRecord
from wigs.config import get_settings

settings = get_settings()


@dataclass
class SocialEvidence:
    reddit_mentions: int = 0
    telegram_mentions: int = 0
    discord_mentions: int = 0
    youtube_mentions: int = 0
    gdelt_mentions: int = 0
    unique_sources: int = 0
    velocity_acceleration: float = 0.0
    novelty_score: float = 0.5     # 0 = all identical (bots), 1 = fully diverse
    organic_ratio: float | None = None
    gdelt_relevance: float = 0.0
    cross_platform_count: int = 0  # how many distinct platforms have mentions
    all_texts: list[str] = field(default_factory=list)
    all_records: list[MentionRecord] = field(default_factory=list)


@dataclass
class SocialScore:
    value: int              # 0–100
    evidence: SocialEvidence
    narrative_type: str = "UNKNOWN"


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x ** 2 for x in a))
    mag_b = math.sqrt(sum(x ** 2 for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _tfidf_embedding(text: str, vocab: dict[str, int], idf: dict[str, float]) -> list[float]:
    """Lightweight bag-of-words TF-IDF embedding (no ML deps required at import time)."""
    tokens = text.lower().split()
    tf: dict[str, float] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    n = len(tokens) or 1
    vec = [0.0] * len(vocab)
    for word, idx in vocab.items():
        if word in tf:
            vec[idx] = (tf[word] / n) * idf.get(word, 1.0)
    return vec


def compute_novelty_score(texts: list[str]) -> float:
    """
    Detect coordinated/bot social campaigns by measuring linguistic diversity.
    Returns 0.0 (all identical = bots) to 1.0 (fully diverse = organic).
    Uses lightweight TF-IDF if sentence-transformers not available.
    """
    if len(texts) < 2:
        return 1.0

    try:
        # Prefer sentence-transformers / CryptoBERT if installed
        from sentence_transformers import SentenceTransformer  # type: ignore

        model = SentenceTransformer("all-MiniLM-L6-v2")  # fallback; swap for cryptobert
        embeddings = model.encode(texts[:50], show_progress_bar=False).tolist()
    except ImportError:
        # Fallback: bag-of-words TF-IDF
        vocab: dict[str, int] = {}
        for text in texts:
            for word in text.lower().split():
                if word not in vocab:
                    vocab[word] = len(vocab)
        idf = {w: 1.0 for w in vocab}
        embeddings = [_tfidf_embedding(t, vocab, idf) for t in texts[:50]]

    sims = []
    for i in range(len(embeddings) - 1):
        sim = _cosine_similarity(embeddings[i], embeddings[i + 1])
        sims.append(sim)

    avg_sim = sum(sims) / len(sims) if sims else 0.0
    return round(1.0 - avg_sim, 3)


def compute_velocity_acceleration(records: list[MentionRecord]) -> float:
    """
    Rate of change of mentions (velocity acceleration).
    Positive = accelerating growth. Negative = decelerating.
    """
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    window_5m = now - timedelta(minutes=5)
    window_10m = now - timedelta(minutes=10)

    v_now = sum(1 for r in records if r.created_utc >= window_5m)
    v_prev = sum(1 for r in records if window_10m <= r.created_utc < window_5m)

    return float(v_now - v_prev)


def score_unique_sources(records: list[MentionRecord]) -> float:
    """Count quality accounts (age > 30 days) across distinct account IDs."""
    quality = {r.account_id for r in records if r.account_age_days > 30}
    return min(1.0, len(quality) / 20.0)   # normalize: 20 quality accounts = score 1.0


def _normalize_0_100(value: float) -> int:
    return min(100, max(0, int(value * 100)))


def build_search_terms(token_mint: str, symbol: str | None, name: str | None) -> list[str]:
    terms = [token_mint]
    if symbol:
        terms.append(symbol)
        terms.append(symbol.lower())
    if name:
        terms.append(name)
        terms.append(name.lower().replace(" ", ""))
    return list(dict.fromkeys(terms))  # deduplicated, order preserved


def classify_narrative(symbol: str | None, name: str | None, gdelt_relevance: float) -> str:
    text = f"{symbol or ''} {name or ''}".lower()
    if gdelt_relevance > 0.3:
        return "REAL_WORLD_EVENT"
    animals = ["dog", "cat", "pepe", "frog", "shib", "inu", "bear", "bull", "whale", "shark"]
    if any(a in text for a in animals):
        return "ANIMAL"
    ai_terms = ["gpt", "claude", "ai", "agi", "robot", "musk"]
    if any(a in text for a in ai_terms):
        return "AI_TECH"
    copycat = ["2", "v2", "elon", "killer", "inu2", "classic"]
    if any(c in text for c in copycat):
        return "DERIVATIVE"
    return "UNKNOWN"


async def fetch_and_score(
    token_mint: str,
    symbol: str | None = None,
    name: str | None = None,
) -> SocialScore:
    if not settings.enable_social_scoring:
        return SocialScore(value=0, evidence=SocialEvidence(), narrative_type="UNKNOWN")

    terms = build_search_terms(token_mint, symbol, name)

    # Fetch from all social sources concurrently
    tasks = [reddit.search_mentions(terms, window_hours=24)]
    if settings.enable_youtube:
        tasks.append(youtube.search_video_mentions(terms, window_days=7))  # type: ignore
    if settings.enable_gdelt:
        tasks.append(gdelt.search_news_events(terms, window_days=7))  # type: ignore

    results = await asyncio.gather(*tasks, return_exceptions=True)

    reddit_records: list[MentionRecord] = results[0] if not isinstance(results[0], Exception) else []
    yt_mentions = results[1] if len(results) > 1 and not isinstance(results[1], Exception) else []
    gdelt_articles = results[2] if len(results) > 2 and not isinstance(results[2], Exception) else []

    all_records = list(reddit_records)
    all_texts = [r.text for r in reddit_records]

    platforms_with_data = 0
    if reddit_records:
        platforms_with_data += 1
    if yt_mentions:
        platforms_with_data += 1
    if gdelt_articles:
        platforms_with_data += 1

    gdelt_relevance = min(1.0, len(gdelt_articles) / 5.0)

    evidence = SocialEvidence(
        reddit_mentions=len(reddit_records),
        youtube_mentions=len(yt_mentions),
        gdelt_mentions=len(gdelt_articles),
        unique_sources=len({r.account_id for r in all_records}),
        velocity_acceleration=compute_velocity_acceleration(all_records),
        novelty_score=compute_novelty_score(all_texts) if all_texts else 0.5,
        gdelt_relevance=gdelt_relevance,
        cross_platform_count=platforms_with_data,
        all_texts=all_texts,
        all_records=all_records,
    )

    unique_src_score = score_unique_sources(all_records)
    vel_score = min(1.0, max(0.0, (evidence.velocity_acceleration + 5) / 10))

    raw_score = (
        0.25 * vel_score
        + 0.20 * unique_src_score
        + 0.15 * evidence.novelty_score
        + 0.15 * gdelt_relevance
        + 0.10 * min(1.0, evidence.reddit_mentions / 20)
        + 0.10 * min(1.0, platforms_with_data / 3)
        + 0.05 * min(1.0, evidence.youtube_mentions / 5)
    )

    narrative = classify_narrative(symbol, name, gdelt_relevance)

    return SocialScore(
        value=_normalize_0_100(raw_score),
        evidence=evidence,
        narrative_type=narrative,
    )
