#!/usr/bin/env python
from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request
import json


def main() -> int:
    parser = argparse.ArgumentParser(description="Register Helius webhook endpoint")
    parser.add_argument("--url", required=True, help="Public webhook URL, e.g. https://api.example.com/webhook/helius")
    parser.add_argument("--webhook-id", default="", help="Optional existing webhook id to edit")
    args = parser.parse_args()

    api_key = os.getenv("HELIUS_API_KEY", "")
    if not api_key:
        print("HELIUS_API_KEY is required", file=sys.stderr)
        return 1

    endpoint = "https://api.helius.xyz/v0/webhooks"
    if args.webhook_id:
        endpoint = f"{endpoint}/{args.webhook_id}"

    payload = {
        "webhookURL": args.url,
        "transactionTypes": ["SWAP", "TRANSFER"],
        "accountAddresses": [],
        "webhookType": "enhanced",
    }
    data = json.dumps(payload).encode()
    method = "PUT" if args.webhook_id else "POST"
    req = urllib.request.Request(f"{endpoint}?api-key={api_key}", data=data, method=method)
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode()
    except urllib.error.HTTPError as exc:
        print(f"Helius API error {exc.code}: {exc.read().decode()}", file=sys.stderr)
        return 1

    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
