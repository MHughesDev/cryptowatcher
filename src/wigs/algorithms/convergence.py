"""Wallet convergence scoring — the primary candidate signal.

When multiple independent high-quality wallets buy the same token in a short
window, that is a much stronger signal than any single wallet buy. This module
computes a convergence score that accounts for:

  - Wallet quality of each buyer
  - Recency decay (recent buys count more)
  - Cluster membership (cabals count as one vote)
  - Time compression (tightly clustered buys = stronger signal)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from wigs.config import get_settings
from wigs.filters import (
    convergence_confidence,
    convergence_threshold_adjustment,
    independence_weight as _independence_weight_fn,
    time_compression_factor as _time_compression_factor_fn,
)

settings = get_settings()


@dataclass
class BuyRecord:
    wallet_address: str
    wallet_quality: int          # 0–100 composite score
    event_time: datetime
    cluster_id: str | None       # None = no cluster (fully independent)
    cluster_type: str | None     # SMART_MONEY / CABAL_SUSPECT / BOT_FARM / etc.
    cluster_size: int = 1


@dataclass
class ConvergenceResult:
    convergence_score: int                   # 0–100
    independent_buyer_count: int
    total_buyer_count: int
    time_spread_seconds: float
    threshold_adjustment: int                # points to subtract from decision thresholds
    qualifies_for_forced_strong_watch: bool
    weighted_sum: float                      # raw weighted sum before normalization


def _recency_weight(event_time: datetime, now: datetime) -> float:
    """Exponential decay: w = exp(-λ * minutes_ago)."""
    minutes_ago = max(0.0, (now - event_time).total_seconds() / 60)
    return math.exp(-settings.convergence_recency_lambda * minutes_ago)


def _independence_weight(record: BuyRecord) -> float:
    """Delegate to filters.independence_weight — single source of truth."""
    return _independence_weight_fn(record.cluster_type, record.cluster_id, record.cluster_size)


def _time_compression_factor(spread_seconds: float) -> float:
    """Delegate to filters.time_compression_factor — single source of truth."""
    return _time_compression_factor_fn(spread_seconds)


def _time_spread(times: list[datetime]) -> float:
    """Standard deviation of entry times in seconds."""
    if len(times) < 2:
        return 0.0
    timestamps = [t.timestamp() for t in times]
    mean = sum(timestamps) / len(timestamps)
    variance = sum((t - mean) ** 2 for t in timestamps) / len(timestamps)
    return math.sqrt(variance)


def _normalize(value: float, max_expected: float = 500.0) -> int:
    """Clamp and scale to 0–100."""
    return min(100, max(0, int(value / max_expected * 100)))


def compute_convergence_score(
    buyers: list[BuyRecord],
    now: datetime | None = None,
) -> ConvergenceResult:
    """
    Main convergence scoring function.

    buyers: list of all tracked wallets that have bought this token.
    now: reference time (defaults to utcnow).
    """
    if now is None:
        now = datetime.utcnow()

    if not buyers:
        return ConvergenceResult(
            convergence_score=0,
            independent_buyer_count=0,
            total_buyer_count=0,
            time_spread_seconds=0.0,
            threshold_adjustment=0,
            qualifies_for_forced_strong_watch=False,
            weighted_sum=0.0,
        )

    weighted_sum = 0.0
    independent_count = 0
    seen_clusters: set[str] = set()   # deduplicate smart-money clusters
    entry_times: list[datetime] = []

    for record in buyers:
        ind_weight = _independence_weight(record)

        # Count independent buyers (non-clustered or one representative per cluster)
        is_independent = record.cluster_id is None
        is_new_smart_cluster = (
            record.cluster_id is not None
            and record.cluster_type == "SMART_MONEY"
            and record.cluster_id not in seen_clusters
        )
        if is_independent or is_new_smart_cluster:
            independent_count += 1
            if record.cluster_id:
                seen_clusters.add(record.cluster_id)

        if ind_weight == 0.0:
            continue  # excluded wallet — skip but still track time

        rec_weight = _recency_weight(record.event_time, now)
        weighted_sum += record.wallet_quality * rec_weight * ind_weight
        entry_times.append(record.event_time)

    spread = _time_spread(entry_times)
    compression = _time_compression_factor(spread)

    confidence = convergence_confidence(independent_count)

    raw_score = weighted_sum * compression * confidence
    score = _normalize(raw_score)

    threshold_adj = convergence_threshold_adjustment(independent_count)

    forced_strong_watch = (
        independent_count >= settings.convergence_forced_upgrade_min_wallets
        and spread <= settings.convergence_forced_upgrade_max_spread_seconds
    )

    return ConvergenceResult(
        convergence_score=score,
        independent_buyer_count=independent_count,
        total_buyer_count=len(buyers),
        time_spread_seconds=spread,
        threshold_adjustment=threshold_adj,
        qualifies_for_forced_strong_watch=forced_strong_watch,
        weighted_sum=raw_score,
    )


def get_threshold_adjustment(independent_buyer_count: int) -> int:
    """Delegate to filters.convergence_threshold_adjustment — single source of truth."""
    return convergence_threshold_adjustment(independent_buyer_count)
