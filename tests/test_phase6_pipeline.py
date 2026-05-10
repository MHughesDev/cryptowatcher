from types import SimpleNamespace

import pytest

from wigs.pipeline import (
    detect_kol_already_called,
    has_social_drainer_link,
    is_copycat_mint,
    update_candidate_relationships,
)


class _ScalarResult:
    def __init__(self, one=None, rows=None):
        self._one = one
        self._rows = rows or []

    def scalar_one(self):
        return self._one

    def all(self):
        return self._rows


@pytest.mark.asyncio
async def test_detect_kol_already_called_true():
    db = SimpleNamespace(execute=None)

    async def fake_execute(stmt):
        return _ScalarResult(one=1)

    db.execute = fake_execute
    result = await detect_kol_already_called("mint1", db)
    assert result is True


@pytest.mark.asyncio
async def test_is_copycat_mint_detects_near_match():
    db = SimpleNamespace(execute=None)

    async def fake_execute(stmt):
        return _ScalarResult(rows=[("PEPEE", "Pepee"), ("DOGE", "Doge")])

    db.execute = fake_execute
    result = await is_copycat_mint("PEPE", "Pepe", db)
    assert result is True


@pytest.mark.asyncio
async def test_has_social_drainer_link_detects_malicious_text():
    posts = [
        "normal post",
        "free mint now, connect wallet at wallet-connect-bonus.example",
    ]
    assert await has_social_drainer_link(posts) is True


@pytest.mark.asyncio
async def test_update_candidate_relationships_delegates(monkeypatch):
    called = {}

    async def fake_add(db, wallet_address, token_mint, event_time):
        called["wallet"] = wallet_address
        called["token"] = token_mint

    monkeypatch.setattr("wigs.pipeline.graph_repo.add_wallet_token_edge", fake_add)
    await update_candidate_relationships("mint1", "wallet1", SimpleNamespace(), object())
    assert called == {"wallet": "wallet1", "token": "mint1"}
