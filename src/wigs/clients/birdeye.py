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


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def get_price(
    token_mint: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any] | None:
    async with (client or httpx.AsyncClient(timeout=10)) as c:
        resp = await c.get(
            f"{BASE_URL}/defi/price",
            params={"address": token_mint},
            headers=_headers(),
        )
        if resp.status_code in (404, 400):
            return None
        resp.raise_for_status()
        return resp.json().get("data")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def get_token_security(
    token_mint: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any] | None:
    """Returns mint authority, freeze authority, holder concentration, etc."""
    async with (client or httpx.AsyncClient(timeout=10)) as c:
        resp = await c.get(
            f"{BASE_URL}/defi/token_security",
            params={"address": token_mint},
            headers=_headers(),
        )
        if resp.status_code in (404, 400):
            return None
        resp.raise_for_status()
        return resp.json().get("data")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def get_token_overview(
    token_mint: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any] | None:
    async with (client or httpx.AsyncClient(timeout=10)) as c:
        resp = await c.get(
            f"{BASE_URL}/defi/token_overview",
            params={"address": token_mint},
            headers=_headers(),
        )
        if resp.status_code in (404, 400):
            return None
        resp.raise_for_status()
        return resp.json().get("data")
