# 01 — Architecture and Repo Map

## Architecture name

**WIGS — Wallet Intelligence Graph Scanner**

This is a new design. It is not a simple “wallet event → token score” pipeline. It is an evidence-graph pipeline where wallets, tokens, pools, social mentions, creator accounts, DEX venues, and outcomes are all linked as graph entities.

## Core design principle

```text
Wallets nominate tokens.
Evidence confirms or rejects tokens.
Outcomes update wallet quality.
```

That feedback loop is the main edge.

A wallet is not considered “good” because it once bought a token that went up. A wallet is considered useful only if it repeatedly enters before **tradable** upside, avoids rugs better than average, exits profitably, and is not merely part of an insider trap.

## High-level architecture

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
│ Links wallets, tokens, pools, creators   │
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
│ Rejects obvious rugs, honeypots, risky   │
│ authorities, fake liquidity, concentration│
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
│ Produces AVOID / WATCH / STRONG WATCH    │
│ / STRONG CANDIDATE                       │
└─────────────────────┬────────────────────┘
                      ↓
┌──────────────────────────────────────────┐
│ 9. Alert + Audit Ledger                  │
│ Stores every decision for backtesting    │
└─────────────────────┬────────────────────┘
                      ↓
┌──────────────────────────────────────────┐
│ 10. Outcome Labeler + Wallet Re-ranker   │
│ Measures future result and improves      │
│ wallet rankings                          │
└──────────────────────────────────────────┘
```

## Recommended minimal repo structure

```text
memecoin-alpha-radar/
├── README.md
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── .env.example
├── src/
│   └── memecoin_alpha/
│       ├── __init__.py
│       ├── app.py
│       ├── config.py
│       ├── clients.py
│       ├── models.py
│       ├── repositories.py
│       ├── pipeline.py
│       ├── algorithms.py
│       ├── workers.py
│       └── alerts.py
├── tests/
│   ├── test_algorithms.py
│   └── test_pipeline.py
└── docs/
    ├── 01_ARCHITECTURE_AND_REPO_MAP.md
    ├── 02_DATA_PIPELINE_AND_ALGORITHMS.md
    ├── 03_DATA_SOURCES_AND_APIS.md
    ├── 04_ORM_AND_DATA_MODELS.md
    ├── 05_PSEUDOCODE.md
    └── 06_RESEARCH_SOURCES.md
```

## AI description table

| Type | Name | AI description | Purpose / short description | Software category |
|---|---|---|---|---|
| Folder | `memecoin-alpha-radar/` | Root repository for the Solana memecoin wallet-intelligence system. | Contains Dockerized Python application, docs, tests, and operational config. | repository, dockerized application |
| File | `README.md` | Human entrypoint for the project. | Explains system goal, project layout, and run path. | documentation |
| File | `Dockerfile` | Container image definition for the Python API/worker application. | Builds the application runtime. | Docker, deployment |
| File | `docker-compose.yml` | Local multi-container runtime. | Runs API worker, PostgreSQL, Redis, and optional scheduler. | Docker, orchestration, local development |
| File | `pyproject.toml` | Python dependency and package metadata. | Defines Python version, dependencies, lint/test tooling. | Python packaging, dependency management |
| File | `.env.example` | Safe template for local configuration. | Lists required API keys, DB URLs, thresholds, and feature flags. | configuration, secrets template |
| Folder | `src/` | Source-code root. | Keeps application code separated from docs/tests. | source code |
| Folder | `src/memecoin_alpha/` | Python package root. | Contains all business logic for WIGS. | Python package, backend application |
| File | `src/memecoin_alpha/__init__.py` | Python package marker. | Makes the directory importable as a package. | Python package |
| File | `src/memecoin_alpha/app.py` | FastAPI application entrypoint. | Exposes health checks, webhook receiver, token-score endpoints, and admin/test endpoints. | API server, FastAPI |
| File | `src/memecoin_alpha/config.py` | Typed settings module. | Loads environment variables and system thresholds into typed configuration. | configuration, Pydantic settings |
| File | `src/memecoin_alpha/clients.py` | External API clients. | Helius, Solana RPC, DexScreener, Jupiter, Birdeye, GeckoTerminal, Reddit, Telegram, Discord, GDELT, YouTube. | API integrations, HTTP clients |
| File | `src/memecoin_alpha/models.py` | ORM and domain models. | Defines SQLAlchemy ORM tables and typed domain objects. | database, ORM, domain models |
| File | `src/memecoin_alpha/repositories.py` | Data-access layer. | Isolates database reads/writes from pipeline logic. | database, repository pattern |
| File | `src/memecoin_alpha/pipeline.py` | Main event-processing pipeline. | Handles wallet events, candidate mint extraction, enrichment, risk checks, and scoring. | ETL, data pipeline, orchestration |
| File | `src/memecoin_alpha/algorithms.py` | Scoring and detection algorithms. | Wallet score, lead-lag score, trend score, risk vetoes, liquidity realism, outcome labeling. | analytics, scoring, algorithms |
| File | `src/memecoin_alpha/workers.py` | Background workers. | Runs wallet polling, candidate scoring, outcome refresh, social trend collection, and scheduled backtests. | workers, async processing |
| File | `src/memecoin_alpha/alerts.py` | Notification layer. | Sends ranked candidates and risk summaries to Telegram/Discord/email/logs. | alerting, notification |
| Folder | `tests/` | Automated tests. | Validates algorithms and pipeline behavior. | testing |
| File | `tests/test_algorithms.py` | Unit tests for scoring/risk logic. | Prevents scoring regressions. | testing, analytics validation |
| File | `tests/test_pipeline.py` | Pipeline integration tests. | Verifies event-to-alert flow with mocked API responses. | testing, integration |
| Folder | `docs/` | Architecture and design docs. | Stores AI-readable system specs. | documentation, specs |
| File | `docs/01_ARCHITECTURE_AND_REPO_MAP.md` | Architecture and repo map. | Defines high-level architecture and AI description table. | documentation, architecture |
| File | `docs/02_DATA_PIPELINE_AND_ALGORITHMS.md` | Data pipeline and algorithms. | Defines the full data pipeline, strategy engine, risk engine, wallet discovery, and optimization loops. | documentation, data engineering, algorithms |
| File | `docs/03_DATA_SOURCES_AND_APIS.md` | API/source catalog. | Lists free-tier/public APIs and exactly what each contributes. | documentation, API integration |
| File | `docs/04_ORM_AND_DATA_MODELS.md` | ORM/data model design. | Defines PostgreSQL tables and relationships. | documentation, database schema |
| File | `docs/05_PSEUDOCODE.md` | End-to-end pseudocode. | High-level Python class/function map for implementation. | documentation, pseudocode |
| File | `docs/06_RESEARCH_SOURCES.md` | Source reference list. | Lists research sources used for system design. | documentation, references |
