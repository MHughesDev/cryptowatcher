import hashlib
import hmac

import httpx
import pytest

from wigs.clients import birdeye, discord, helius, solana_rpc, telegram


@pytest.mark.asyncio
async def test_birdeye_get_token_trades_returns_list(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://public-api.birdeye.so/defi/txs/token?address=mint123&offset=0&limit=2&tx_type=buy",
        json={"data": {"items": [{"txHash": "abc"}, {"txHash": "def"}]}},
    )

    trades = await birdeye.get_token_trades("mint123", limit=2)

    assert [trade["txHash"] for trade in trades] == ["abc", "def"]


@pytest.mark.asyncio
async def test_birdeye_get_token_trades_handles_not_found(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://public-api.birdeye.so/defi/txs/token?address=missing&offset=0&limit=50&tx_type=buy",
        status_code=404,
    )

    trades = await birdeye.get_token_trades("missing")

    assert trades == []


@pytest.mark.asyncio
async def test_telegram_scan_authorized_channels_filters_matches(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://api.telegram.org/bottoken123/getUpdates?limit=60&timeout=0",
        json={
            "ok": True,
            "result": [
                {
                    "channel_post": {
                        "message_id": 10,
                        "date": 1_700_000_000,
                        "text": "Mint123 is moving",
                        "chat": {"id": -1001},
                        "from": {"id": 77},
                    }
                },
                {
                    "channel_post": {
                        "message_id": 11,
                        "date": 1_700_000_100,
                        "text": "unrelated",
                        "chat": {"id": -1001},
                        "from": {"id": 88},
                    }
                },
            ],
        },
    )

    matches = await telegram.scan_authorized_channels("token123", ["-1001"], "mint123")

    assert len(matches) == 1
    assert matches[0]["channel_id"] == "-1001"
    assert matches[0]["message_id"] == 10


@pytest.mark.asyncio
async def test_discord_scan_authorized_servers_filters_matches(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://discord.com/api/v10/channels/chan-1/messages?limit=5",
        json=[
            {
                "id": "m1",
                "content": "mint123 spotted",
                "timestamp": "2026-05-09T17:00:00Z",
                "author": {"id": "user-1"},
            },
            {
                "id": "m2",
                "content": "other token",
                "timestamp": "2026-05-09T17:01:00Z",
                "author": {"id": "user-2"},
            },
        ],
    )

    matches = await discord.scan_authorized_servers("bot-token", ["chan-1"], "mint123", limit=5)

    assert len(matches) == 1
    assert matches[0]["message_id"] == "m1"
    assert matches[0]["author_id"] == "user-1"


@pytest.mark.asyncio
async def test_helius_parse_transaction_returns_empty_dict_on_404(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.helius.xyz/v0/transactions/?api-key=",
        status_code=404,
    )

    parsed = await helius.parse_transaction("sig123")

    assert parsed == {}


@pytest.mark.asyncio
async def test_solana_rpc_get_signatures_handles_rpc_error(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://mainnet.helius-rpc.com",
        json={"error": {"message": "bad request"}},
    )

    signatures = await solana_rpc.get_signatures_for_address("wallet123")

    assert signatures == []


def test_verify_webhook_signature_accepts_explicit_secret():
    payload = b'{"hello":"world"}'
    secret = "top-secret"
    signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    assert helius.verify_webhook_signature(payload, signature, secret) is True
