"""Helius API client — webhooks, enhanced transaction parsing."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from wigs.config import get_settings

settings = get_settings()

BASE_URL = "https://api.helius.xyz/v0"
PARSE_URL = "https://api.helius.xyz/v0/transactions"


class HeliusError(Exception):
    pass


def _headers() -> dict[str, str]:
    return {"Content-Type": "application/json"}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def create_wallet_webhook(
    wallet_addresses: list[str],
    webhook_url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Register a webhook to receive transaction events for the given wallet addresses.
    Returns the webhook ID."""
    payload = {
        "webhookURL": webhook_url,
        "transactionTypes": ["SWAP"],
        "accountAddresses": wallet_addresses,
        "webhookType": "enhanced",
    }
    url = f"{BASE_URL}/webhooks?api-key={settings.helius_api_key}"
    async with (client or httpx.AsyncClient(timeout=15)) as c:
        resp = await c.post(url, json=payload, headers=_headers())
        resp.raise_for_status()
        return resp.json()["webhookID"]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def parse_transaction(
    signature: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Parse a single transaction signature into an enhanced transaction object."""
    url = f"{PARSE_URL}/?api-key={settings.helius_api_key}"
    async with (client or httpx.AsyncClient(timeout=15)) as c:
        resp = await c.post(url, json={"transactions": [signature]}, headers=_headers())
        resp.raise_for_status()
        results = resp.json()
        if not results:
            raise HeliusError(f"No parse result for {signature}")
        return results[0]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def get_transactions_for_address(
    address: str,
    *,
    before: str | None = None,
    limit: int = 100,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Fetch enhanced transaction history for a wallet address."""
    params: dict[str, Any] = {"api-key": settings.helius_api_key, "limit": limit}
    if before:
        params["before"] = before
    url = f"{BASE_URL}/addresses/{address}/transactions"
    async with (client or httpx.AsyncClient(timeout=30)) as c:
        resp = await c.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def verify_webhook_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """Verify the HMAC-SHA256 signature Helius attaches to webhook requests."""
    if not settings.helius_webhook_secret:
        return True  # Skip verification if secret not configured (dev mode)
    expected = hmac.new(
        settings.helius_webhook_secret.encode(),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)
