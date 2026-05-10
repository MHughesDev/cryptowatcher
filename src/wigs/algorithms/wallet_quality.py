"""Wallet quality scoring primitives."""

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime
from typing import Any


DEFAULT_WEIGHTS = {
    "pnl": 0.22,
    "early_entry": 0.18,
    "lead_lag": 0.18,
    "exit_quality": 0.14,
    "rug_avoidance": 0.12,
    "repeatability": 0.08,
    "independence": 0.05,
    "freshness": 0.03,
}


def _clamp_0_100(value: float) -> float:
    return max(0.0, min(100.0, value))


def _extract_trade_return(trade: dict[str, Any]) -> float:
    if "pnl_usd" in trade:
        return float(trade["pnl_usd"])
    if "tradable_return_usd" in trade:
        return float(trade["tradable_return_usd"])
    if "tradable_return_pct" in trade and "position_size_usd" in trade:
        return float(trade["tradable_return_pct"]) * float(trade["position_size_usd"])
    return float(trade.get("return_usd", 0.0))


def calculate_realized_pnl_score(trades: list[dict]) -> float:
    total = sum(_extract_trade_return(trade) for trade in trades)
    if total <= 0:
        return 0.0
    score = math.log1p(total) / math.log1p(10_000) * 100.0
    return _clamp_0_100(score)


def calculate_early_entry_score(trades: list[dict]) -> float:
    if not trades:
        return 0.0

    early_hits = 0.0
    for trade in trades:
        percentile = trade.get("entry_percentile")
        if percentile is None:
            rank = float(trade.get("entry_rank", 1))
            total = float(trade.get("buyer_count", trade.get("buyers_total", 1)) or 1)
            percentile = rank / total
        percentile = max(0.0, min(1.0, float(percentile)))
        if percentile <= 0.2:
            early_hits += 1.0

    score = (early_hits / len(trades)) * 100.0
    return _clamp_0_100(score)


def calculate_exit_quality_score(trades: list[dict]) -> float:
    if not trades:
        return 0.0

    quality_sum = 0.0
    for trade in trades:
        if "drawdown_avoided_pct" in trade:
            quality = float(trade["drawdown_avoided_pct"])
        else:
            drawdown = float(trade.get("max_drawdown_after_sell", 0.0))
            entry_price = float(trade.get("entry_price", 1.0) or 1.0)
            quality = 1.0 - max(0.0, drawdown / entry_price)
        if float(trade.get("exit_price_impact", 0.0)) > 0.15:
            quality *= 0.5
        quality_sum += max(0.0, min(1.0, quality))

    return _clamp_0_100((quality_sum / len(trades)) * 100.0)


def calculate_rug_avoidance_score(trades: list[dict]) -> float:
    if not trades:
        return 0.0

    rug_count = sum(1 for trade in trades if trade.get("is_rug"))
    avg_exposure = (
        sum(float(trade.get("rug_exposure", 1.0 if trade.get("is_rug") else 0.0)) for trade in trades)
        / len(trades)
    )
    avoidance = (1.0 - rug_count / len(trades)) * (1.0 - max(0.0, min(1.0, avg_exposure)))
    return _clamp_0_100(avoidance * 100.0)


def calculate_repeatability_score(return_buckets: list[float]) -> float:
    if not return_buckets:
        return 0.0
    counts = Counter(return_buckets)
    total = sum(counts.values())
    if total <= 1:
        return 0.0
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * math.log2(p)
    max_entropy = math.log2(len(counts)) if len(counts) > 1 else 1.0
    if max_entropy <= 0:
        return 0.0
    return _clamp_0_100((entropy / max_entropy) * 100.0)


def _bucketize_returns(returns: list[float]) -> list[float]:
    buckets = []
    for value in returns:
        if value < -0.5:
            buckets.append(-1.0)
        elif value < 0:
            buckets.append(-0.25)
        elif value < 0.5:
            buckets.append(0.25)
        elif value < 1.0:
            buckets.append(0.75)
        elif value < 2.0:
            buckets.append(1.5)
        else:
            buckets.append(3.0)
    return buckets


def calculate_independence_score(wallet: str | dict[str, Any], cluster_members: list[str | dict[str, Any]]) -> float:
    wallet_history: list[str]
    if isinstance(wallet, dict):
        wallet_history = list(wallet.get("token_history", []))
    else:
        wallet_history = []

    if not cluster_members or not wallet_history:
        return 100.0

    wallet_set = set(wallet_history)
    similarities: list[float] = []
    for member in cluster_members:
        if isinstance(member, dict):
            member_tokens = set(member.get("token_history", []))
        else:
            member_tokens = set()
        if not member_tokens:
            continue
        denom = math.sqrt(len(wallet_set) * len(member_tokens))
        if denom == 0:
            continue
        similarity = len(wallet_set & member_tokens) / denom
        similarities.append(similarity)

    if not similarities:
        return 100.0
    return _clamp_0_100((1.0 - (sum(similarities) / len(similarities))) * 100.0)


def calculate_freshness_score(last_active_days_ago: float) -> float:
    weeks_since_active = max(0.0, float(last_active_days_ago) / 7.0)
    freshness = math.exp(-0.1 * weeks_since_active)
    return _clamp_0_100(freshness * 100.0)


def score_wallet(
    wallet_address: str,
    trades: list[dict],
    cluster_members: list[str | dict[str, Any]],
    last_active_days_ago: float,
    weights: dict[str, float] | None = None,
) -> dict[str, float | int]:
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}

    pnl_score = calculate_realized_pnl_score(trades)
    early_entry_score = calculate_early_entry_score(trades)
    lead_lag_values = [float(trade["lead_lag_score"]) for trade in trades if "lead_lag_score" in trade]
    lead_lag_score = sum(lead_lag_values) / len(lead_lag_values) if lead_lag_values else 50.0
    exit_quality_score = calculate_exit_quality_score(trades)
    rug_avoidance_score = calculate_rug_avoidance_score(trades)
    return_values = [
        float(trade.get("tradable_return_pct", trade.get("return_pct", 0.0)))
        for trade in trades
    ]
    repeatability_score = calculate_repeatability_score(_bucketize_returns(return_values))
    wallet_context = {
        "wallet_address": wallet_address,
        "token_history": [trade.get("token_mint") for trade in trades if trade.get("token_mint")],
    }
    independence_score = calculate_independence_score(wallet_context, cluster_members)
    freshness_score = calculate_freshness_score(last_active_days_ago)

    quality = (
        weights["pnl"] * pnl_score
        + weights["early_entry"] * early_entry_score
        + weights["lead_lag"] * lead_lag_score
        + weights["exit_quality"] * exit_quality_score
        + weights["rug_avoidance"] * rug_avoidance_score
        + weights["repeatability"] * repeatability_score
        + weights["independence"] * independence_score
        + weights["freshness"] * freshness_score
    )

    return {
        "wallet_quality": int(round(_clamp_0_100(quality))),
        "realized_pnl_score": round(pnl_score, 2),
        "early_entry_score": round(early_entry_score, 2),
        "lead_lag_score": round(_clamp_0_100(lead_lag_score), 2),
        "exit_quality_score": round(exit_quality_score, 2),
        "rug_avoidance_score": round(rug_avoidance_score, 2),
        "repeatability_score": round(repeatability_score, 2),
        "independence_score": round(independence_score, 2),
        "freshness_score": round(freshness_score, 2),
    }
