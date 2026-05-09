"""DexScreener public API client."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

BASE_URL = "https://api.dexscreener.com"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def get_token_pairs(
    token_mint: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Return all DEX pairs for a Solana token mint."""
    url = f"{BASE_URL}/tokens/v1/solana/{token_mint}"
    async with (client or httpx.AsyncClient(timeout=15)) as c:
        resp = await c.get(url)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("pairs", [])


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def get_token_profile(
    token_mint: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any] | None:
    url = f"{BASE_URL}/token-profiles/latest/v1"
    async with (client or httpx.AsyncClient(timeout=15)) as c:
        resp = await c.get(url, params={"chainId": "solana", "tokenAddress": token_mint})
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        results = resp.json()
        return results[0] if results else None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def get_paid_orders(
    token_mint: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Check whether the token has paid for promotions — a mild risk signal."""
    url = f"{BASE_URL}/orders/v1/solana/{token_mint}"
    async with (client or httpx.AsyncClient(timeout=10)) as c:
        resp = await c.get(url)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json()
