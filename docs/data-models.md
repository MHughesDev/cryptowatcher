# Data Models

## Stack

```text
Database:   PostgreSQL
ORM:        SQLAlchemy 2.x async
Validation: Pydantic v2
Migrations: Alembic
```

## Entity relationship map

```text
TrackedWallet
  ├── WalletEvent
  ├── WalletScoreSnapshot
  └── WalletClusterMember

CandidateToken
  ├── TokenMarketSnapshot
  ├── TokenRiskSnapshot
  ├── SocialSnapshot
  ├── TokenScoreSnapshot
  ├── TokenOutcome
  ├── TokenPool
  └── TokenHolderSnapshot

WalletCluster
  ├── WalletClusterMember
  └── ClusterScoreSnapshot

Alert
  └── TokenScoreSnapshot
```

---

## Tables

### `tracked_wallets`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Internal ID. |
| `wallet_address` | string unique | Solana wallet address. |
| `wallet_type` | enum | SCOUT, WHALE, SMART_MONEY, KOL_PRECALL, DEV_ADJACENT, UNKNOWN. |
| `label` | string nullable | Human label. |
| `source` | string | How the wallet was discovered. |
| `is_active` | bool | Whether to monitor. |
| `created_at` | timestamp | Insert time. |
| `updated_at` | timestamp | Last update. |

### `wallet_events`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Internal ID. |
| `wallet_address` | string | Trigger wallet. |
| `tx_signature` | string unique | Solana transaction signature. |
| `token_mint` | string | Candidate mint. |
| `event_type` | enum | BUY, SELL, TRANSFER, LP_ADD, LP_REMOVE. |
| `amount_sol` | numeric nullable | SOL notional. |
| `amount_usd` | numeric nullable | USD notional. |
| `amount_token` | numeric nullable | Token units. |
| `dex_or_program` | string nullable | Venue/program. |
| `pool_address` | string nullable | Pool if known. |
| `event_time` | timestamp | Chain time. |
| `detected_at` | timestamp | System detection time. |
| `raw_payload` | jsonb | Original API payload. |

### `candidate_tokens`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Internal ID. |
| `token_mint` | string unique | SPL mint. |
| `symbol` | string nullable | Token symbol. |
| `name` | string nullable | Token name. |
| `creator_wallet` | string nullable | Creator/deployer if known. |
| `created_at_chain` | timestamp nullable | Chain creation time. |
| `first_seen_at` | timestamp | First time system saw this mint. |
| `launch_source` | enum nullable | PUMP_FUN, PUMPSWAP, RAYDIUM, METEORA, ORCA, UNKNOWN. |
| `status` | enum | PENDING, ENRICHING, WATCH, STRONG_WATCH, STRONG_CANDIDATE, REJECTED. |

### `token_pools`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Internal ID. |
| `token_mint` | string | Token mint. |
| `pool_address` | string | Pool address. |
| `dex` | string | Raydium, PumpSwap, Meteora, etc. |
| `quote_asset` | string | SOL, USDC, etc. |
| `created_at_chain` | timestamp nullable | Pool creation time. |
| `is_primary` | bool | Highest-quality pool for this token. |
| `last_seen_at` | timestamp | Last observed. |

### `token_market_snapshots`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Internal ID. |
| `token_mint` | string | Token mint. |
| `price_usd` | numeric nullable | Current price. |
| `market_cap` | numeric nullable | Market cap. |
| `fdv` | numeric nullable | Fully diluted valuation. |
| `liquidity_usd` | numeric | Total liquidity. |
| `volume_5m` | numeric nullable | 5-minute volume. |
| `volume_1h` | numeric nullable | 1-hour volume. |
| `volume_24h` | numeric nullable | 24-hour volume. |
| `buyers_5m` | int nullable | Recent buyers. |
| `sellers_5m` | int nullable | Recent sellers. |
| `buy_sell_ratio_5m` | numeric nullable | Recent flow. |
| `primary_pool_address` | string nullable | Pool. |
| `source` | string | DexScreener, Birdeye, GeckoTerminal, etc. |
| `captured_at` | timestamp | Snapshot time. |

### `token_risk_snapshots`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Internal ID. |
| `token_mint` | string | Token mint. |
| `mint_authority_active` | bool nullable | Mint-risk flag. |
| `freeze_authority_active` | bool nullable | Freeze-risk flag. |
| `top_10_holder_pct` | numeric nullable | Concentration. |
| `top_20_holder_pct` | numeric nullable | Concentration. |
| `dev_holding_pct` | numeric nullable | Creator/dev holdings. |
| `sell_quote_exists` | bool | Sell route exists. |
| `price_impact_1_sol` | numeric nullable | Exit impact at 1 SOL. |
| `price_impact_5_sol` | numeric nullable | Exit impact at 5 SOL. |
| `liquidity_drop_pct_15m` | numeric nullable | Liquidity rug signal. |
| `risk_flags` | jsonb | List of vetoes and penalties. |
| `captured_at` | timestamp | Snapshot time. |

### `social_snapshots`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Internal ID. |
| `token_mint` | string | Token mint. |
| `symbol` | string nullable | Ticker. |
| `name` | string nullable | Name. |
| `reddit_mentions` | int | Reddit mentions. |
| `telegram_mentions` | int | Telegram mentions. |
| `discord_mentions` | int | Discord mentions. |
| `youtube_mentions` | int | YouTube mentions. |
| `gdelt_mentions` | int | News/event mentions. |
| `unique_sources` | int | Independent source count. |
| `social_velocity_score` | int | 0–100. |
| `organic_ratio` | numeric nullable | Human/unique-source quality estimate. |
| `captured_at` | timestamp | Snapshot time. |

### `wallet_score_snapshots`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Internal ID. |
| `wallet_address` | string | Wallet address. |
| `realized_pnl_score` | int | 0–100. |
| `early_entry_score` | int | 0–100. |
| `lead_lag_score` | int | 0–100. |
| `exit_quality_score` | int | 0–100. |
| `rug_avoidance_score` | int | 0–100. |
| `repeatability_score` | int | 0–100. |
| `independence_score` | int | 0–100. |
| `freshness_score` | int | 0–100. |
| `wallet_quality` | int | 0–100 composite. |
| `captured_at` | timestamp | Snapshot time. |

### `wallet_clusters`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Internal ID. |
| `cluster_label` | string nullable | Human label. |
| `cluster_type` | enum | UNKNOWN, SMART_MONEY, CABAL_SUSPECT, DEV_SUSPECT, BOT_FARM, KOL_SUSPECT. |
| `confidence` | numeric | 0–1. |
| `created_at` | timestamp | Insert time. |

### `wallet_cluster_members`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Internal ID. |
| `cluster_id` | UUID FK | Cluster. |
| `wallet_address` | string | Wallet. |
| `membership_reason` | string | Funding link, co-entry, co-exit, timing, etc. |
| `confidence` | numeric | 0–1. |
| `created_at` | timestamp | Insert time. |

### `token_scores`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Internal ID. |
| `token_mint` | string | Token mint. |
| `wallet_score` | int | 0–100. |
| `market_score` | int | 0–100. |
| `risk_score` | int | 0–100. |
| `social_score` | int | 0–100. |
| `history_score` | int | 0–100. |
| `execution_score` | int | 0–100. |
| `total_score` | int | 0–100. |
| `decision` | enum | AVOID, WATCH, STRONG_WATCH, STRONG_CANDIDATE. |
| `risk_level` | enum | LOW, MEDIUM, HIGH, CRITICAL. |
| `score_reasons` | jsonb | Human-readable reason codes. |
| `created_at` | timestamp | Score time. |

### `alerts`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Internal ID. |
| `token_mint` | string | Token. |
| `score_id` | UUID nullable | Linked score. |
| `channel` | enum | TELEGRAM, DISCORD, EMAIL, LOG. |
| `decision` | enum | WATCH, STRONG_WATCH, STRONG_CANDIDATE. |
| `message` | text | Alert content. |
| `sent_at` | timestamp | Send time. |
| `delivery_status` | enum | SENT, FAILED, SKIPPED. |

### `token_outcomes`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Internal ID. |
| `token_mint` | string | Token. |
| `alert_id` | UUID nullable | Linked alert. |
| `label` | enum | RUG, DEAD_ON_ARRIVAL, ONE_CYCLE_PUMP, TRADEABLE_RUNNER, SURVIVOR, HEAVY_HITTER. |
| `max_return_5m` | numeric nullable | Max forward return at 5m. |
| `max_return_1h` | numeric nullable | Max forward return at 1h. |
| `max_return_24h` | numeric nullable | Max forward return at 24h. |
| `tradable_return_1h` | numeric nullable | Exit-adjusted return at 1h. |
| `max_drawdown_24h` | numeric nullable | Risk measurement. |
| `exit_liquidity_success` | bool nullable | Could a realistic sell have exited? |
| `labeled_at` | timestamp | Label time. |

---

## Indexes

```text
wallet_events(wallet_address, event_time)
wallet_events(token_mint, event_time)
candidate_tokens(token_mint)
token_market_snapshots(token_mint, captured_at)
token_risk_snapshots(token_mint, captured_at)
social_snapshots(token_mint, captured_at)
wallet_score_snapshots(wallet_address, captured_at)
token_scores(token_mint, created_at)
token_outcomes(token_mint, labeled_at)
```

---

## Data retention

| Data | Retention |
|---|---|
| Raw wallet events | Keep indefinitely if storage allows; compress older payloads. |
| Market snapshots | Dense for 30 days; downsample after. |
| Social snapshots | Dense for 90 days; aggregate after. |
| Raw API payloads | Keep for audit; archive older JSONB. |
| Outcomes | Keep indefinitely. |
| Wallet scores | Keep indefinitely for performance drift analysis. |
