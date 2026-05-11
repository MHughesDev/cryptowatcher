# Architecture — WIGS

## Core design principle

```text
Wallets nominate tokens.
Evidence confirms or rejects tokens.
Outcomes update wallet quality.
```

That feedback loop is the main edge. A wallet is not "good" because it once bought a token that went up. A wallet earns trust only if it repeatedly enters before **tradable** upside, avoids rugs better than average, exits profitably, and is not part of an insider trap.

## Pipeline

```text
┌──────────────────────────────────────────┐
│ 1. Wallet Universe Builder               │
│ Finds and ranks wallets worth watching   │
└─────────────────────┬────────────────────┘
                      ↓
┌──────────────────────────────────────────┐
│ 2. Wallet Event Ingestor                 │
│ Watches seed/scout/whale/KOL wallets     │
└─────────────────────┬────────────────────┘
                      ↓
┌──────────────────────────────────────────┐
│ 3. Candidate Mint Extractor              │
│ Converts wallet swaps into token mints   │
└─────────────────────┬────────────────────┘
                      ↓
┌──────────────────────────────────────────┐
│ 4. Evidence Graph Builder                │
│ Links wallets, tokens, pools, creators,  │
│ clusters, socials, and outcomes          │
└─────────────────────┬────────────────────┘
                      ↓
┌──────────────────────────────────────────┐
│ 5. Market + Liquidity Verifier           │
│ Confirms price, volume, liquidity, route │
│ sellability, and price impact            │
└─────────────────────┬────────────────────┘
                      ↓
┌──────────────────────────────────────────┐
│ 6. Safety Veto Engine                    │
│ Rejects rugs, honeypots, risky           │
│ authorities, fake liquidity, clusters    │
└─────────────────────┬────────────────────┘
                      ↓
┌──────────────────────────────────────────┐
│ 7. Social/Narrative Verifier             │
│ Confirms whether a real trend exists     │
│ outside the wallet activity              │
└─────────────────────┬────────────────────┘
                      ↓
┌──────────────────────────────────────────┐
│ 8. Evidence Fusion Scorer                │
│ Produces AVOID / WATCH / STRONG_WATCH    │
│ / STRONG_CANDIDATE (API enums)           │
└─────────────────────┬────────────────────┘
                      ↓
┌──────────────────────────────────────────┐
│ 9. Alert + Audit Ledger                  │
│ Stores every decision for backtesting    │
└─────────────────────┬────────────────────┘
                      ↓
┌──────────────────────────────────────────┐
│ 10. Outcome Labeler + Wallet Re-ranker   │
│ Measures result and improves wallet      │
│ rankings                                 │
└──────────────────────────────────────────┘
```

## Repo structure

```text
wigs/
├── README.md
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── .env.example
├── src/
│   └── wigs/
│       ├── __init__.py
│       ├── app.py            # FastAPI entrypoint — health, webhooks, score endpoints
│       ├── config.py         # Typed settings via Pydantic
│       ├── clients.py        # Helius, RPC, DexScreener, Jupiter, Birdeye, social APIs
│       ├── models.py         # SQLAlchemy ORM + Pydantic domain schemas
│       ├── repositories.py   # Database read/write layer
│       ├── pipeline.py       # Main event-to-alert orchestration
│       ├── algorithms.py     # Wallet scoring, safety vetoes, evidence fusion
│       ├── workers.py        # Background polling and scheduled jobs
│       └── alerts.py         # Telegram/Discord/log notification layer
├── tests/
│   ├── test_algorithms.py
│   └── test_pipeline.py
└── docs/
    ├── architecture.md
    ├── wallet-engine.md
    ├── candidate-scoring.md
    ├── data-sources.md
    ├── data-models.md
    ├── pseudocode.md
    └── references.md
```

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.12+ |
| API server | FastAPI |
| ORM | SQLAlchemy 2.x async |
| Validation | Pydantic v2 |
| Migrations | Alembic |
| Database | PostgreSQL |
| Cache/queue | Redis |
| Container | Docker + docker-compose |
