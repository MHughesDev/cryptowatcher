from datetime import datetime, timedelta

from wigs.algorithms.lead_lag import (
    calculate_lead_lag_score,
    compute_cross_correlation,
    granger_causality_test,
)


def test_compute_cross_correlation_detects_lead():
    start = datetime(2026, 1, 1, 0, 0, 0)
    wallet_buys = [start + timedelta(minutes=idx) for idx in (2, 5, 8)]
    prices = []
    price = 1.0
    for minute in range(12):
        if minute in (4, 7, 10):
            price += 0.8
        prices.append((start + timedelta(minutes=minute), price))

    result = compute_cross_correlation(wallet_buys, prices, max_lag_minutes=5)
    assert result["peak_lag_minutes"] <= 0
    assert result["peak_correlation"] >= 0


def test_granger_causality_test_returns_valid_shape():
    wallet = [0, 1, 0, 1, 0, 1, 0, 1, 0, 1]
    price = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]
    result = granger_causality_test(wallet, price, max_lag=2)
    assert "p_value" in result
    assert "f_statistic" in result
    assert isinstance(result["is_causal"], bool)


def test_calculate_lead_lag_score_positive_for_preceding_wallet():
    start = datetime(2026, 1, 1, 0, 0, 0)
    buys = [
        {"wallet_address": "wallet-1", "token_mint": "mint1", "event_time": start + timedelta(minutes=1)},
        {"wallet_address": "wallet-1", "token_mint": "mint1", "event_time": start + timedelta(minutes=2)},
    ]
    prices = {
        "mint1": [
            (start + timedelta(minutes=0), 1.0),
            (start + timedelta(minutes=1), 1.0),
            (start + timedelta(minutes=2), 1.1),
            (start + timedelta(minutes=3), 1.6),
            (start + timedelta(minutes=4), 2.2),
            (start + timedelta(minutes=5), 2.4),
        ]
    }
    score = calculate_lead_lag_score("wallet-1", buys, prices)
    assert score > 0
