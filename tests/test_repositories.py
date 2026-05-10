from dataclasses import dataclass, field
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from wigs.pipeline import load_convergence_buyers
from wigs.repositories import alert_repo, token_repo, wallet_repo


class _ScalarResult:
    def __init__(self, one=None, many=None):
        self._one = one
        self._many = many or []

    def scalar_one_or_none(self):
        return self._one

    def scalar_one(self):
        return self._one

    def scalars(self):
        return self

    def all(self):
        return self._many


@dataclass
class _FakeEvent:
    wallet_address: str
    tx_signature: str
    token_mint: str
    event_type: str
    amount_sol: float | None = None
    amount_usd: float | None = None
    amount_token: float | None = None
    dex_or_program: str | None = None
    pool_address: str | None = None
    event_time: datetime = field(default_factory=datetime.utcnow)
    raw_payload: dict = field(default_factory=dict)


@pytest.mark.asyncio
async def test_save_wallet_event_adds_model_instance():
    db = SimpleNamespace(add=AsyncMock(), flush=AsyncMock())
    added = []
    db.add = added.append

    event = _FakeEvent(
        wallet_address="wallet-1",
        tx_signature="sig-1",
        token_mint="mint-1",
        event_type="BUY",
    )

    saved = await wallet_repo.save_wallet_event(db, event)

    assert saved.wallet_address == "wallet-1"
    assert saved.tx_signature == "sig-1"
    assert len(added) == 1
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_token_score_adds_score_row():
    db = SimpleNamespace(add=AsyncMock(), flush=AsyncMock())
    added = []
    db.add = added.append
    result = SimpleNamespace(
        wallet_score=70,
        market_score=60,
        risk_score=90,
        social_score=50,
        history_score=40,
        execution_score=100,
        total_score=72,
        decision="WATCH",
        risk_level="MEDIUM",
        convergence_independent_count=3,
        convergence_time_spread_s=45.0,
        threshold_adjustment=10,
        score_reasons={"vetoes": [], "penalties": []},
    )

    saved = await token_repo.save_token_score(db, result, "mint-1")

    assert saved.token_mint == "mint-1"
    assert saved.total_score == 72
    assert len(added) == 1
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_outcome_adds_outcome_row():
    db = SimpleNamespace(add=AsyncMock(), flush=AsyncMock())
    added = []
    db.add = added.append

    saved = await alert_repo.save_outcome(
        db,
        token_mint="mint-1",
        alert_id="alert-1",
        label="SURVIVOR",
        measurement_complete=True,
    )

    assert saved.token_mint == "mint-1"
    assert saved.label == "SURVIVOR"
    assert len(added) == 1
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_load_convergence_buyers_uses_repository_layer(monkeypatch):
    event_time = datetime.utcnow()
    events = [SimpleNamespace(wallet_address="wallet-1", event_time=event_time)]

    async def fake_get_wallet_events_for_token(db, token_mint, event_type="BUY"):
        assert token_mint == "mint-1"
        assert event_type == "BUY"
        return events

    async def fake_get_wallet_score(db, address):
        return SimpleNamespace(wallet_quality=88)

    async def fake_get_wallet_cluster_member(db, address):
        return SimpleNamespace(cluster_id="cluster-1")

    async def fake_get_wallet_cluster(db, address):
        return SimpleNamespace(cluster_type="SMART_MONEY")

    async def fake_get_cluster_member_count(db, cluster_id):
        return 4

    monkeypatch.setattr(wallet_repo, "get_wallet_events_for_token", fake_get_wallet_events_for_token)
    monkeypatch.setattr(wallet_repo, "get_wallet_score", fake_get_wallet_score)
    monkeypatch.setattr("wigs.pipeline.graph_repo.get_wallet_cluster_member", fake_get_wallet_cluster_member)
    monkeypatch.setattr("wigs.pipeline.graph_repo.get_wallet_cluster", fake_get_wallet_cluster)
    monkeypatch.setattr("wigs.pipeline.graph_repo.get_cluster_member_count", fake_get_cluster_member_count)

    buyers = await load_convergence_buyers("mint-1", db=object())

    assert len(buyers) == 1
    assert buyers[0].wallet_address == "wallet-1"
    assert buyers[0].wallet_quality == 88
    assert buyers[0].cluster_id == "cluster-1"
    assert buyers[0].cluster_type == "SMART_MONEY"
    assert buyers[0].cluster_size == 4
