from wigs.algorithms.wallet_quality import (
    calculate_freshness_score,
    calculate_independence_score,
    calculate_realized_pnl_score,
    calculate_repeatability_score,
    score_wallet,
)


def test_realized_pnl_score_increases_with_profit():
    small = calculate_realized_pnl_score([{"pnl_usd": 100.0}])
    large = calculate_realized_pnl_score([{"pnl_usd": 5_000.0}])
    assert large > small > 0


def test_independence_score_penalizes_overlap():
    wallet = {"token_history": ["A", "B", "C"]}
    cluster_members = [
        {"token_history": ["A", "B", "C"]},
        {"token_history": ["A", "B"]},
    ]
    score = calculate_independence_score(wallet, cluster_members)
    assert 0 <= score < 40


def test_freshness_score_decays():
    recent = calculate_freshness_score(0)
    stale = calculate_freshness_score(140)
    assert recent > stale


def test_repeatability_score_rewards_distribution():
    concentrated = calculate_repeatability_score([3.0, 3.0, 3.0, 3.0])
    distributed = calculate_repeatability_score([-1.0, -0.25, 0.25, 0.75, 1.5, 3.0])
    assert distributed > concentrated


def test_score_wallet_returns_component_map():
    trades = [
        {
            "token_mint": "mint1",
            "pnl_usd": 1_000,
            "entry_percentile": 0.1,
            "drawdown_avoided_pct": 0.8,
            "tradable_return_pct": 1.2,
            "lead_lag_score": 70,
        },
        {
            "token_mint": "mint2",
            "pnl_usd": 500,
            "entry_percentile": 0.15,
            "drawdown_avoided_pct": 0.6,
            "tradable_return_pct": 0.5,
            "lead_lag_score": 80,
        },
    ]
    cluster_members = [{"token_history": ["mint3", "mint4"]}]
    result = score_wallet("wallet-1", trades, cluster_members, last_active_days_ago=3)
    assert 0 <= result["wallet_quality"] <= 100
    assert result["lead_lag_score"] == 75.0
    assert result["early_entry_score"] > 0
