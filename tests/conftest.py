"""Shared test fixtures."""

import pytest


@pytest.fixture
def sample_buy_records():
    """Three independent high-quality wallet buy records with tight timing."""
    from datetime import datetime, timedelta
    from wigs.algorithms.convergence import BuyRecord

    now = datetime.utcnow()
    return [
        BuyRecord(wallet_address="wallet_A", wallet_quality=80, event_time=now - timedelta(seconds=30), cluster_id=None, cluster_type=None),
        BuyRecord(wallet_address="wallet_B", wallet_quality=70, event_time=now - timedelta(seconds=60), cluster_id=None, cluster_type=None),
        BuyRecord(wallet_address="wallet_C", wallet_quality=65, event_time=now - timedelta(seconds=90), cluster_id=None, cluster_type=None),
    ]


@pytest.fixture
def cabal_buy_records():
    """Three wallets from the same cabal cluster — should count as 0 independent votes."""
    from datetime import datetime, timedelta
    from wigs.algorithms.convergence import BuyRecord

    now = datetime.utcnow()
    return [
        BuyRecord(wallet_address="cabal_A", wallet_quality=80, event_time=now - timedelta(seconds=10), cluster_id="cluster-1", cluster_type="CABAL_SUSPECT", cluster_size=3),
        BuyRecord(wallet_address="cabal_B", wallet_quality=75, event_time=now - timedelta(seconds=15), cluster_id="cluster-1", cluster_type="CABAL_SUSPECT", cluster_size=3),
        BuyRecord(wallet_address="cabal_C", wallet_quality=70, event_time=now - timedelta(seconds=20), cluster_id="cluster-1", cluster_type="CABAL_SUSPECT", cluster_size=3),
    ]
