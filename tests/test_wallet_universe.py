from types import SimpleNamespace

import pytest

from wigs.algorithms import wallet_universe


class FakeHeliusClient:
    def __init__(self, responses):
        self.responses = responses

    async def get_transactions_for_address(self, address, limit=100):
        return self.responses.get(address, [])


class FakeSolanaRpcClient:
    def __init__(self, responses):
        self.responses = responses

    async def get_signatures_for_address(self, address, limit=100):
        return self.responses.get(address, [])


@pytest.mark.asyncio
async def test_discover_from_historical_winners_collects_early_wallets():
    client = FakeHeliusClient(
        {
            "mint1": [
                {"owner": "w1", "blockTime": 1_700_000_000, "max_multiple": 4.0},
                {"owner": "w2", "blockTime": 1_700_000_600, "max_multiple": 3.5},
                {"owner": "late", "blockTime": 1_700_003_000, "max_multiple": 5.0},
            ]
        }
    )
    wallets = await wallet_universe.discover_from_historical_winners(["mint1"], client)
    assert wallets == ["w1", "w2"]


@pytest.mark.asyncio
async def test_discover_pre_whale_wallets_collects_prior_entries():
    rpc = FakeSolanaRpcClient(
        {
            "mint1": [
                {"owner": "w1", "blockTime": 1_700_000_000, "amount_usd": 1000},
                {"owner": "w2", "blockTime": 1_700_000_100, "amount_usd": 2000},
                {"owner": "whale", "blockTime": 1_700_000_200, "amount_usd": 100000},
            ]
        }
    )
    wallets = await wallet_universe.discover_pre_whale_wallets(["mint1"], rpc)
    assert wallets == ["w1", "w2"]


@pytest.mark.asyncio
async def test_build_seed_wallet_set_persists_candidates(monkeypatch):
    persisted = []

    async def fake_upsert(db, address, label=None, source="manual", wallet_type="UNKNOWN"):
        persisted.append((address, source, wallet_type))
        return SimpleNamespace(wallet_address=address)

    monkeypatch.setattr("wigs.algorithms.wallet_universe.wallet_repo.upsert_tracked_wallet", fake_upsert)

    helius = FakeHeliusClient(
        {
            "mint1": [{"owner": "w1", "blockTime": 1_700_000_000, "max_multiple": 4.0}],
            "kol1": [{"token_mint": "mint2", "blockTime": 1_700_001_000}],
            "mint2": [{"owner": "w2", "blockTime": 1_700_000_900}],
        }
    )
    rpc = FakeSolanaRpcClient({"mint1": [{"owner": "whale", "blockTime": 1_700_000_200, "amount_usd": 100000}]})

    wallets = await wallet_universe.build_seed_wallet_set(["mint1"], ["kol1"], helius, rpc, db=object())

    assert set(wallets) == {"w1", "w2"}
    assert all(source == "seed_builder" for _, source, _ in persisted)


@pytest.mark.asyncio
async def test_discover_kol_precall_wallets_requires_repeated_leads(monkeypatch):
    monkeypatch.setattr(wallet_universe.settings, "kol_precall_min_hits", 2)
    monkeypatch.setattr(wallet_universe.settings, "kol_precall_wallet_blocklist", [])
    monkeypatch.setattr(wallet_universe.settings, "kol_precall_min_lead_seconds", 60)
    monkeypatch.setattr(wallet_universe.settings, "kol_precall_max_lead_seconds", 21_600)

    helius = FakeHeliusClient(
        {
            "kol1": [
                {"token_mint": "mintA", "blockTime": 1_700_001_000},
                {"token_mint": "mintB", "blockTime": 1_700_002_000},
            ],
            "mintA": [{"owner": "lead1", "blockTime": 1_700_000_800}],
            "mintB": [{"owner": "lead1", "blockTime": 1_700_001_800}],
        }
    )

    wallets = await wallet_universe.discover_kol_precall_wallets(["kol1"], helius)
    assert wallets == ["lead1"]


@pytest.mark.asyncio
async def test_discover_kol_precall_wallets_filters_blocklist_and_infra(monkeypatch):
    monkeypatch.setattr(wallet_universe.settings, "kol_precall_min_hits", 1)
    monkeypatch.setattr(wallet_universe.settings, "kol_precall_wallet_blocklist", ["blocked1"])
    monkeypatch.setattr(wallet_universe.settings, "kol_precall_min_lead_seconds", 60)
    monkeypatch.setattr(wallet_universe.settings, "kol_precall_max_lead_seconds", 21_600)

    helius = FakeHeliusClient(
        {
            "kol1": [{"token_mint": "mintA", "blockTime": 1_700_001_000}],
            "mintA": [
                {"owner": "blocked1", "blockTime": 1_700_000_800},
                {"owner": "jup-router", "blockTime": 1_700_000_790},
                {"owner": "good1", "blockTime": 1_700_000_780},
            ],
        }
    )

    wallets = await wallet_universe.discover_kol_precall_wallets(["kol1"], helius)
    assert wallets == ["good1"]
