"""Lead-lag detection for wallets versus price movement."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

import numpy as np

try:
    from scipy.stats import f as f_dist
except Exception:  # pragma: no cover
    f_dist = None


def _minute_bucket(ts: datetime) -> datetime:
    return ts.replace(second=0, microsecond=0)


def _build_series(wallet_buy_times: list[datetime], price_series: list[tuple[datetime, float]]) -> tuple[np.ndarray, np.ndarray]:
    if not price_series:
        return np.array([]), np.array([])

    minute_prices: dict[datetime, float] = {}
    for ts, price in price_series:
        minute_prices[_minute_bucket(ts)] = float(price)

    minutes = sorted(minute_prices)
    wallet_counts = defaultdict(float)
    for ts in wallet_buy_times:
        wallet_counts[_minute_bucket(ts)] += 1.0

    buy_series = np.array([wallet_counts.get(minute, 0.0) for minute in minutes], dtype=float)
    prices = np.array([minute_prices[minute] for minute in minutes], dtype=float)
    if len(prices) >= 2:
        price_returns = np.diff(prices, prepend=prices[0])
    else:
        price_returns = prices.copy()
    return buy_series, price_returns


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 2 or len(b) < 2:
        return 0.0
    if np.std(a) == 0 or np.std(b) == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def compute_cross_correlation(
    wallet_buy_times: list[datetime],
    price_series: list[tuple[datetime, float]],
    max_lag_minutes: int = 60,
) -> dict[str, float]:
    """Returns peak lag, peak correlation, and lead rate."""
    buy_series, price_returns = _build_series(wallet_buy_times, price_series)
    if len(buy_series) == 0 or len(price_returns) == 0:
        return {"peak_lag_minutes": 0.0, "peak_correlation": 0.0, "llr": 0.0}

    correlations: dict[int, float] = {}
    for lag in range(-max_lag_minutes, max_lag_minutes + 1):
        if lag < 0:
            corr = _corr(buy_series[-lag:], price_returns[: len(price_returns) + lag])
        elif lag > 0:
            corr = _corr(buy_series[: len(buy_series) - lag], price_returns[lag:])
        else:
            corr = _corr(buy_series, price_returns)
        correlations[lag] = corr

    peak_lag, peak_corr = max(correlations.items(), key=lambda item: item[1])
    negative = max([correlations[lag] for lag in correlations if lag < 0] or [0.0])
    positive = max([correlations[lag] for lag in correlations if lag > 0] or [0.0])
    llr = negative / positive if positive > 0 else (1.0 if negative > 0 else 0.0)
    signed_peak_lag = float(-peak_lag)
    return {
        "peak_lag_minutes": signed_peak_lag,
        "peak_correlation": float(peak_corr),
        "llr": float(llr),
    }


def granger_causality_test(
    wallet_activity_series: list[float],
    price_series: list[float],
    max_lag: int = 4,
) -> dict[str, float | bool]:
    """Lightweight two-model F-test approximation."""
    y = np.asarray(price_series, dtype=float)
    x = np.asarray(wallet_activity_series, dtype=float)
    n = min(len(x), len(y))
    if n <= max_lag + 2:
        return {"p_value": 1.0, "f_statistic": 0.0, "is_causal": False}

    y = y[:n]
    x = x[:n]
    rows = []
    targets = []
    for idx in range(max_lag, n):
        restricted = [1.0]
        restricted.extend(y[idx - lag] for lag in range(1, max_lag + 1))
        unrestricted = restricted + [x[idx - lag] for lag in range(1, max_lag + 1)]
        rows.append((restricted, unrestricted))
        targets.append(y[idx])

    restricted_matrix = np.asarray([row[0] for row in rows], dtype=float)
    unrestricted_matrix = np.asarray([row[1] for row in rows], dtype=float)
    target = np.asarray(targets, dtype=float)

    beta_r, *_ = np.linalg.lstsq(restricted_matrix, target, rcond=None)
    beta_u, *_ = np.linalg.lstsq(unrestricted_matrix, target, rcond=None)
    residual_r = target - restricted_matrix @ beta_r
    residual_u = target - unrestricted_matrix @ beta_u
    rss_r = float(np.sum(residual_r ** 2))
    rss_u = float(np.sum(residual_u ** 2))
    df_num = max_lag
    df_den = len(target) - unrestricted_matrix.shape[1]
    if df_den <= 0 or rss_u <= 0 or rss_r < rss_u:
        return {"p_value": 1.0, "f_statistic": 0.0, "is_causal": False}

    f_stat = ((rss_r - rss_u) / df_num) / (rss_u / df_den)
    if f_dist is None:
        p_value = 1.0 if f_stat <= 0 else 0.049
    else:
        p_value = float(1.0 - f_dist.cdf(f_stat, df_num, df_den))
    return {"p_value": p_value, "f_statistic": float(max(0.0, f_stat)), "is_causal": p_value < 0.05}


def _lead_lift_for_buy(buy_time: datetime, price_series: list[tuple[datetime, float]]) -> tuple[float, bool]:
    after = [(ts, price) for ts, price in price_series if ts >= buy_time]
    if not after:
        return 0.0, False
    entry_price = after[0][1]
    window_end = buy_time + timedelta(hours=24)
    within_window = [price for ts, price in after if ts <= window_end]
    if not within_window or entry_price <= 0:
        return 0.0, False
    peak = max(within_window)
    lift = peak / entry_price
    return lift, lift >= 2.0


def calculate_lead_lag_score(
    wallet_address: str,
    historical_buys: list[dict],
    price_history: dict[str, list],
) -> float:
    per_token_scores: list[float] = []
    causality_penalty = 1.0

    for token_mint, series in price_history.items():
        token_buys = [
            buy for buy in historical_buys
            if buy.get("wallet_address") == wallet_address and buy.get("token_mint") == token_mint
        ]
        if not token_buys or not series:
            continue

        buy_times = [buy["event_time"] for buy in token_buys if buy.get("event_time")]
        xcorr = compute_cross_correlation(buy_times, series)

        lifts = []
        preceded_2x = 0
        for buy_time in buy_times:
            lift, did_precede = _lead_lift_for_buy(buy_time, series)
            lifts.append(lift)
            preceded_2x += 1 if did_precede else 0

        llr = max(0.0, min(2.0, xcorr["llr"]))
        llt_component = max(0.0, min(1.0, (-xcorr["peak_lag_minutes"]) / 60.0))
        llc_component = max(0.0, min(1.0, xcorr["peak_correlation"]))
        lead_lift = min(1.0, ((sum(lifts) / len(lifts)) - 1.0)) if lifts else 0.0
        llr_component = preceded_2x / len(buy_times) if buy_times else 0.0

        wallet_series, price_returns = _build_series(buy_times, series)
        granger = granger_causality_test(wallet_series.tolist(), price_returns.tolist())
        if float(granger["p_value"]) > 0.1:
            causality_penalty = min(causality_penalty, 0.5)

        score = 0.40 * llt_component + 0.30 * lead_lift + 0.30 * llr_component
        score *= max(0.5, min(1.0, llc_component + (llr / 2.0)))
        per_token_scores.append(score * 100.0)

    if not per_token_scores:
        return 0.0
    return max(0.0, min(100.0, (sum(per_token_scores) / len(per_token_scores)) * causality_penalty))
