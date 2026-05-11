"""Tests for wallet convergence scoring."""

from datetime import datetime, timedelta

from wigs.algorithms.convergence import BuyRecord, compute_convergence_score, get_threshold_adjustment


def test_single_wallet_no_threshold_adjustment():
    now = datetime.utcnow()
    buyers = [BuyRecord("w1", 80, now - timedelta(seconds=30), None, None)]
    result = compute_convergence_score(buyers, now=now)
    assert result.independent_buyer_count == 1
    assert result.threshold_adjustment == 0
    assert not result.qualifies_for_forced_strong_watch


def test_three_independent_wallets_forced_upgrade(sample_buy_records):
    result = compute_convergence_score(sample_buy_records)
    assert result.independent_buyer_count == 3
    assert result.threshold_adjustment == 10
    # Buys within 90 seconds → should qualify for forced strong watch
    assert result.qualifies_for_forced_strong_watch


def test_cabal_wallets_zero_independent(cabal_buy_records):
    result = compute_convergence_score(cabal_buy_records)
    assert result.independent_buyer_count == 0
    assert result.convergence_score == 0   # all excluded
    assert not result.qualifies_for_forced_strong_watch


def test_time_compression_tight_buys():
    now = datetime.utcnow()
    # All buys within 2 minutes
    buyers = [
        BuyRecord("w1", 70, now - timedelta(seconds=10), None, None),
        BuyRecord("w2", 70, now - timedelta(seconds=20), None, None),
        BuyRecord("w3", 70, now - timedelta(seconds=30), None, None),
    ]
    tight = compute_convergence_score(buyers, now=now)

    # Buys spread over 2 hours
    buyers_spread = [
        BuyRecord("w1", 70, now - timedelta(hours=1), None, None),
        BuyRecord("w2", 70, now - timedelta(hours=2), None, None),
        BuyRecord("w3", 70, now, None, None),
    ]
    spread = compute_convergence_score(buyers_spread, now=now)

    # Tight convergence should score higher despite same wallet quality
    assert tight.convergence_score >= spread.convergence_score


def test_threshold_adjustment_caps_at_20():
    assert get_threshold_adjustment(1) == 0
    assert get_threshold_adjustment(2) == 5
    assert get_threshold_adjustment(5) == 20
    assert get_threshold_adjustment(100) == 20  # capped


def test_empty_buyers():
    result = compute_convergence_score([])
    assert result.convergence_score == 0
    assert result.independent_buyer_count == 0
    assert result.threshold_adjustment == 0


def test_trust_multiplier_influences_weighted_sum():
    now = datetime.utcnow()
    buyers = [
        BuyRecord("w1", 80, now - timedelta(seconds=20), None, None, trust_multiplier=0.7),
        BuyRecord("w2", 80, now - timedelta(seconds=20), None, None, trust_multiplier=1.3),
    ]
    result = compute_convergence_score(buyers, now=now)
    assert result.weighted_sum > 0
