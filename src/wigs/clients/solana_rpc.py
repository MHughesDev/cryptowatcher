"""Solana JSON-RPC client — ground truth for supply, holders, transactions."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from wigs.config import get_settings

settings = get_settings()


class SolanaRpcError(Exception):
    pass


async def _rpc(
    method: str,
    params: list[Any],
    *,
    client: httpx.AsyncClient | None = None,
) -> Any:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    async with (client or httpx.AsyncClient(timeout=20)) as c:
        resp = await c.post(settings.helius_rpc_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise SolanaRpcError(f"RPC error: {data['error']}")
        return data["result"]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def get_token_supply(token_mint: str) -> dict[str, Any]:
    result = await _rpc("getTokenSupply", [token_mint])
    return result["value"]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def get_token_largest_accounts(token_mint: str) -> list[dict[str, Any]]:
    result = await _rpc("getTokenLargestAccounts", [token_mint])
    return result["value"]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def get_transaction(signature: str) -> dict[str, Any] | None:
    result = await _rpc(
        "getTransaction",
        [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
    )
    return result


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def get_signatures_for_address(
    address: str,
    *,
    limit: int = 100,
    before: str | None = None,
) -> list[dict[str, Any]]:
    opts: dict[str, Any] = {"limit": limit}
    if before:
        opts["before"] = before
    return await _rpc("getSignaturesForAddress", [address, opts])


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def get_account_info(address: str) -> dict[str, Any] | None:
    result = await _rpc("getAccountInfo", [address, {"encoding": "jsonParsed"}])
    return result["value"]
