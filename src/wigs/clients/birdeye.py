"""Birdeye Data Services client."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from wigs.config import get_settings

settings = get_settings()
BASE_URL = "https://public-api.birdeye.so"


def _headers() -> dict[str, str]:
    return {
        "X-API-KEY": settings.birdeye_api_key,
        "x-chain": "solana",
    }


async def _get_json(
    path: str,
    *,
    params: dict[str, Any],
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any] | None:
    try:
        if client is not None:
            resp = await client.get(f"{BASE_URL}{path}", params=params, headers=_headers())
        else:
            async with httpx.AsyncClient(timeout=10) as c:
                resp = await c.get(f"{BASE_URL}{path}", params=params, headers=_headers())
        if resp.status_code in (400, 404):
            return None
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError:
        return None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def get_price(
    token_mint: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any] | None:
    data = await _get_json("/defi/price", params={"address": token_mint}, client=client)
    return data.get("data") if data else None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def get_token_security(
    token_mint: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any] | None:
    """Returns mint authority, freeze authority, holder concentration, etc."""
    data = await _get_json("/defi/token_security", params={"address": token_mint}, client=client)
    return data.get("data") if data else None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def get_token_overview(
    token_mint: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any] | None:
    data = await _get_json("/defi/token_overview", params={"address": token_mint}, client=client)
    return data.get("data") if data else None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def get_token_trades(
    mint: str,
    limit: int = 50,
    tx_type: str = "buy",
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    if tx_type not in {"buy", "sell", "all"}:
        raise ValueError("tx_type must be one of: buy, sell, all")

    data = await _get_json(
        "/defi/txs/token",
        params={"address": mint, "offset": 0, "limit": limit, "tx_type": tx_type},
        client=client,
    )
    if not data:
        return []

    trades = data.get("data")
    if isinstance(trades, list):
        return trades
    if isinstance(trades, dict):
        items = trades.get("items") or trades.get("txs") or trades.get("transactions") or []
        return items if isinstance(items, list) else []
    return []
