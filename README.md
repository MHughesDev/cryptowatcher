# Memecoin Alpha Radar

A wallet-led Solana memecoin intelligence system.

This repo is designed around one core idea:

> Do not scan every memecoin first. Track the wallets first. Let high-signal wallet movement nominate candidate token mints, then verify those mints through market, liquidity, safety, and social-trend evidence.

## System objective

The system should find **watchlist-grade Solana memecoins** by combining:

1. **Wallet evidence** — scout wallets, pre-whale wallets, smart-money wallets, KOL-precall wallets, dev-adjacent wallets, and wallet clusters.
2. **Market evidence** — price, liquidity, volume, DEX pool age, route quality, spread, volatility, and sell quote realism.
3. **Safety evidence** — holder concentration, mint/freeze authority, creator activity, suspicious clusters, sellability, liquidity depth, and rug-risk rules.
4. **Social evidence** — Reddit, Telegram, Discord, YouTube, GDELT/news, and community/ticker/mint-address mention velocity.
5. **Historical feedback** — every alert is replayed later to measure whether the wallet signal actually produced tradable upside.

The MVP should output:

```text
AVOID
WATCH
STRONG WATCH
STRONG CANDIDATE
```

It should not start by automatically trading. It should start as a **ranked candidate and alert engine**.

## Downloaded document set

| File | Purpose |
|---|---|
| `docs/01_ARCHITECTURE_AND_REPO_MAP.md` | New architecture, repo mapping, and AI description table. |
| `docs/02_DATA_PIPELINE_AND_ALGORITHMS.md` | End-to-end data pipeline, strategies, wallet-selection methods, scoring, and risk reduction logic. |
| `docs/03_DATA_SOURCES_AND_APIS.md` | Free-tier/public APIs and exactly what each is used for. |
| `docs/04_ORM_AND_DATA_MODELS.md` | PostgreSQL ORM/data model plan. |
| `docs/05_PSEUDOCODE.md` | High-level Python class/function pseudocode for the whole system. |
| `docs/06_RESEARCH_SOURCES.md` | Sources used while designing the system. |

## System name

**WIGS** — Wallet Intelligence Graph Scanner.

The system is not a basic copy-trader. It is an evidence graph that tries to answer:

> Which wallets predict future token demand, and which token mints have enough confirmation to deserve attention?
