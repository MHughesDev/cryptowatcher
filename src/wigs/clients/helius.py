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


async def _request_json(
    method: str,
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    **kwargs: Any,
) -> Any | None:
    try:
        if client is not None:
            resp = await client.request(method, url, **kwargs)
        else:
            async with httpx.AsyncClient(timeout=15 if method == "POST" else 30) as c:
                resp = await c.request(method, url, **kwargs)
        if 400 <= resp.status_code < 600:
            return None
        return resp.json()
    except httpx.HTTPError:
        return None


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
    data = await _request_json("POST", url, client=client, json=payload, headers=_headers())
    if not data:
        return ""
    return data.get("webhookID", "")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def parse_transaction(
    signature: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Parse a single transaction signature into an enhanced transaction object."""
    url = f"{PARSE_URL}/?api-key={settings.helius_api_key}"
    results = await _request_json(
        "POST",
        url,
        client=client,
        json={"transactions": [signature]},
        headers=_headers(),
    )
    if not results:
        return {}
    return results[0] if isinstance(results, list) else {}


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
    results = await _request_json("GET", url, client=client, params=params)
    return results if isinstance(results, list) else []


def verify_webhook_signature(
    payload_bytes: bytes,
    signature_header: str,
    secret: str | None = None,
) -> bool:
    """Verify the HMAC-SHA256 signature Helius attaches to webhook requests."""
    shared_secret = secret if secret is not None else settings.helius_webhook_secret
    if not shared_secret:
        return True  # Skip verification if secret not configured (dev mode)
    expected = hmac.new(
        shared_secret.encode(),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)
