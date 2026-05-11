# WIGS — Wallet Intelligence Graph Scanner

A wallet-led Solana memecoin intelligence system.

> Do not scan every memecoin first. Track the wallets first. Let high-signal wallet movement nominate candidate token mints, then verify those mints through market, liquidity, safety, and social evidence.

## System objective

Find **watchlist-grade Solana memecoins** by combining:

1. **Wallet evidence** — scout wallets, pre-whale wallets, smart-money wallets, KOL-precall wallets, dev-adjacent wallets, and wallet clusters.
2. **Market evidence** — price, liquidity, volume, DEX pool age, route quality, spread, volatility, and sell quote realism.
3. **Safety evidence** — holder concentration, mint/freeze authority, creator activity, suspicious clusters, sellability, and rug-risk rules.
4. **Social evidence** — Reddit, Telegram, Discord, YouTube, GDELT/news, and mention velocity across community, ticker, and mint-address dimensions.
5. **Historical feedback** — every alert is replayed later to measure whether the wallet signal actually produced tradable upside.

## Output

Canonical API enum values:

```text
AVOID
WATCH
STRONG_WATCH
STRONG_CANDIDATE
```

Display labels may be presented with spaces (for example, `STRONG WATCH`) in human-facing UIs/messages.

This is an alert and ranking engine, not an auto-trader. No positions are opened automatically.

## Docs

| File | What it covers |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | System design, full pipeline diagram, repo layout. |
| [`docs/wallet-engine.md`](docs/wallet-engine.md) | Wallet universe builder, quality scoring model, lead-lag graph. |
| [`docs/candidate-scoring.md`](docs/candidate-scoring.md) | Candidate detection, enrichment, safety vetoes, social scoring, evidence fusion. |
| [`docs/data-sources.md`](docs/data-sources.md) | API catalog, free-tier status, MVP priority ranking, raw field specs. |
| [`docs/data-models.md`](docs/data-models.md) | PostgreSQL ORM tables, indexes, and data retention plan. |
| [`docs/pseudocode.md`](docs/pseudocode.md) | High-level Python pseudocode for the full system. |
| [`docs/references.md`](docs/references.md) | Research sources used in system design. |
| [`docs/runbook-staging.md`](docs/runbook-staging.md) | Staging bootstrap, migration, startup, webhook, smoke flow. |
| [`docs/runbook-prod.md`](docs/runbook-prod.md) | Production deployment and rollback checklist. |
| [`docs/production-readiness-checklist.md`](docs/production-readiness-checklist.md) | Production readiness gate and verification commands. |
