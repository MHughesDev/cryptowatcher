"""Wallet discovery helpers for building the seed tracked-wallet set."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from wigs.repositories import wallet_repo


def _extract_wallet_from_trade(trade: dict[str, Any]) -> str | None:
    return trade.get("owner") or trade.get("wallet_address") or trade.get("buyer")


def _extract_time(trade: dict[str, Any]) -> datetime | None:
    value = trade.get("event_time") or trade.get("timestamp") or trade.get("blockTime")
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value)
    return None


async def discover_from_historical_winners(
    token_mints: list[str],
    helius_client,
    min_multiple: float = 3.0,
) -> list[str]:
    wallets: set[str] = set()
    for mint in token_mints:
        trades = await helius_client.get_transactions_for_address(mint, limit=200)
        first_window_wallets = []
        first_time = None
        for trade in trades:
            trade_time = _extract_time(trade)
            wallet = _extract_wallet_from_trade(trade)
            multiple = float(trade.get("max_multiple", trade.get("return_multiple", min_multiple)))
            if wallet is None or trade_time is None or multiple < min_multiple:
                continue
            if first_time is None:
                first_time = trade_time
            if (trade_time - first_time).total_seconds() <= 1800:
                first_window_wallets.append(wallet)
        wallets.update(first_window_wallets)
    return sorted(wallets)


async def discover_pre_whale_wallets(
    token_mints: list[str],
    solana_rpc_client,
    whale_threshold_usd: float = 50_000,
) -> list[str]:
    wallets: set[str] = set()
    for mint in token_mints:
        trades = await solana_rpc_client.get_signatures_for_address(mint, limit=200)
        whale_time = None
        for trade in trades:
            notional = float(trade.get("amount_usd", trade.get("value_usd", 0.0)))
            trade_time = _extract_time(trade)
            if whale_time is None and trade_time is not None and notional >= whale_threshold_usd:
                whale_time = trade_time
                break
        if whale_time is None:
            continue
        for trade in trades:
            wallet = _extract_wallet_from_trade(trade)
            trade_time = _extract_time(trade)
            if wallet and trade_time and trade_time < whale_time:
                wallets.add(wallet)
    return sorted(wallets)


async def discover_kol_precall_wallets(
    kol_wallet_addresses: list[str],
    helius_client,
    lookback_hours: int = 6,
) -> list[str]:
    wallets: set[str] = set()
    for kol_wallet in kol_wallet_addresses:
        kol_trades = await helius_client.get_transactions_for_address(kol_wallet, limit=100)
        for kol_trade in kol_trades:
            token_mint = kol_trade.get("token_mint") or kol_trade.get("mint")
            kol_time = _extract_time(kol_trade)
            if not token_mint or kol_time is None:
                continue
            prior_trades = await helius_client.get_transactions_for_address(token_mint, limit=200)
            lower_bound = kol_time - timedelta(hours=lookback_hours)
            for trade in prior_trades:
                trade_time = _extract_time(trade)
                wallet = _extract_wallet_from_trade(trade)
                if wallet and trade_time and lower_bound <= trade_time < kol_time:
                    wallets.add(wallet)
    return sorted(wallets)


async def build_seed_wallet_set(
    historical_winner_mints: list[str],
    kol_wallets: list[str],
    helius_client,
    solana_rpc_client,
    db,
) -> list[str]:
    winners = await discover_from_historical_winners(historical_winner_mints, helius_client)
    pre_whales = await discover_pre_whale_wallets(historical_winner_mints, solana_rpc_client)
    kol_precalls = await discover_kol_precall_wallets(kol_wallets, helius_client)

    final_wallets = sorted(set(winners) | set(pre_whales) | set(kol_precalls))
    for wallet in final_wallets:
        await wallet_repo.upsert_tracked_wallet(
            db,
            wallet,
            source="seed_builder",
            wallet_type="SCOUT",
        )
    return final_wallets
