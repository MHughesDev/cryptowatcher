"""GeckoTerminal public API client."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

BASE_URL = "https://api.geckoterminal.com/api/v2"
HEADERS = {"Accept": "application/json;version=20230302"}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def get_token_pools(
    token_mint: str,
    *,
    network: str = "solana",
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    url = f"{BASE_URL}/networks/{network}/tokens/{token_mint}/pools"
    async with (client or httpx.AsyncClient(timeout=15)) as c:
        resp = await c.get(url, headers=HEADERS)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json().get("data", [])


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def get_ohlcv(
    pool_address: str,
    timeframe: str = "minute",
    *,
    network: str = "solana",
    limit: int = 60,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """timeframe: 'minute', 'hour', 'day'."""
    url = f"{BASE_URL}/networks/{network}/pools/{pool_address}/ohlcv/{timeframe}"
    async with (client or httpx.AsyncClient(timeout=15)) as c:
        resp = await c.get(url, params={"limit": limit}, headers=HEADERS)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json().get("data", {}).get("attributes", {}).get("ohlcv_list", [])
