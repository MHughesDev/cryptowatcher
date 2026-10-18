# Technical Architecture — WIGS v2

## Repository structure (new)

```
cryptowatcher/
├── src/
│   └── wigs/
│       ├── config.py                 # Settings, env vars, feature flags
│       ├── database.py               # Async SQLAlchemy engine + session
│       ├── models.py                 # ORM table definitions
│       ├── filters.py                # All hard guardrails and gate constants
│       │
│       ├── wallet_tracker/           # Subsystem 1 — completely independent
│       │   ├── __init__.py
│       │   ├── criteria.py           # Add/remove wallet criteria functions
│       │   ├── discovery.py          # Sources for finding new wallets
│       │   ├── health.py             # Health check loop — remove failing wallets
│       │   └── loops.py              # APScheduler job definitions for this subsystem
│       │
│       ├── token_watcher/            # Subsystem 2 — lifecycle management
│       │   ├── __init__.py
│       │   ├── entry.py              # Token entry gate + pre-screen
│       │   ├── state.py              # State machine (WATCHED→RECOMMENDED|EXPIRED)
│       │   └── scheduler.py          # Data collection trigger scheduling
│       │
│       ├── aggregator/               # Subsystem 3 — data collection
│       │   ├── __init__.py
│       │   ├── chain.py              # On-chain data (RPC calls)
│       │   ├── market.py             # DexScreener, GeckoTerminal, Jupiter
│       │   ├── safety.py             # RugCheck, LP lock, bundle detection
│       │   ├── social.py             # Twitter, Reddit
│       │   ├── wallet_signal.py      # Pulls wallet signal from DB
│       │   └── assembler.py          # Combines all sources → TokenDataPacket
│       │
│       ├── ai/                       # Subsystem 4 — Claude integration
│       │   ├── __init__.py
│       │   ├── guardrails.py         # Hard veto checks (code-level)
│       │   ├── prompt.py             # System prompt + data packet formatter
│       │   ├── recommender.py        # Claude API call + response parser
│       │   └── logger.py             # AI decision logging
│       │
│       ├── delivery/                 # Subsystem 5 — Slack
│       │   ├── __init__.py
│       │   ├── formatter.py          # Message formatting (pure functions)
│       │   └── slack.py              # Slack SDK integration
│       │
│       ├── clients/                  # External API clients
│       │   ├── helius.py
│       │   ├── solana_rpc.py
│       │   ├── dexscreener.py
│       │   ├── geckoterminal.py
│       │   ├── jupiter.py
│       │   ├── birdeye.py
│       │   ├── rugcheck.py           # NEW
│       │   ├── twitter.py            # twikit wrapper
│       │   └── reddit.py
│       │
│       └── app.py                    # FastAPI: webhook endpoint + health check
│
├── tests/
├── alembic/
├── RESTRUCTURE/                      # This folder — reference only, not shipped
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## Database schema (new)

### `tracked_wallets`
```sql
wallet_address        TEXT PRIMARY KEY
status                TEXT NOT NULL          -- ACTIVE | RETIRING | REMOVED
added_at              TIMESTAMPTZ NOT NULL
added_reason          TEXT
source                TEXT                   -- HISTORICAL_WINNER | PEER_NETWORK | LEADERBOARD | KOL_PRECALL

-- Performance (updated by health check)
trade_count_30d       INT DEFAULT 0
qualifying_plays_30d  INT DEFAULT 0
win_rate_30d          FLOAT DEFAULT 0
realized_pnl_30d_usd  FLOAT DEFAULT 0
avg_trade_size_usd    FLOAT DEFAULT 0
max_trade_size_usd    FLOAT DEFAULT 0
last_active_at        TIMESTAMPTZ

-- Removal tracking
retiring_since        TIMESTAMPTZ
removed_at            TIMESTAMPTZ
removed_reason        TEXT
```

### `watched_tokens`
```sql
token_mint            TEXT PRIMARY KEY
symbol                TEXT
name                  TEXT
status                TEXT NOT NULL          -- WATCHED | ACTIVE | RECOMMENDED | EXPIRED | SKIPPED
priority              TEXT NOT NULL DEFAULT 'STANDARD'  -- STANDARD | ELEVATED | URGENT

first_seen_at         TIMESTAMPTZ NOT NULL
first_buyer_wallet    TEXT NOT NULL
buying_wallet_count   INT DEFAULT 1
buying_wallet_addresses  JSONB              -- list of addresses
first_buy_mc_usd      FLOAT
buy_time_spread_s     FLOAT DEFAULT 0

last_data_collected_at   TIMESTAMPTZ
last_ai_evaluated_at     TIMESTAMPTZ
ai_evaluation_count      INT DEFAULT 0

recommended_at        TIMESTAMPTZ
expired_at            TIMESTAMPTZ
expiry_reason         TEXT
skipped_reason        TEXT
```

### `token_snapshots`
```sql
id                    BIGSERIAL PRIMARY KEY
token_mint            TEXT NOT NULL REFERENCES watched_tokens(token_mint)
snapshot_at           TIMESTAMPTZ NOT NULL

-- Supply & distribution
holder_count          INT
holder_growth_1h      FLOAT
top_10_holders_pct    FLOAT
top_20_holders_pct    FLOAT
gini_coefficient      FLOAT
hhi                   FLOAT

-- Dev & insiders
creator_holding_pct   FLOAT
insider_holding_pct   FLOAT
bundled_supply_pct    FLOAT
sniper_supply_pct     FLOAT
hostile_supply_pct    FLOAT

-- Liquidity
liquidity_usd         FLOAT
lp_locked             BOOLEAN
lp_lock_days          FLOAT
price_impact_1_sol    FLOAT
sell_route_exists     BOOLEAN

-- Authorities
mint_authority_active   BOOLEAN
freeze_authority_active BOOLEAN

-- Market
price_usd             FLOAT
market_cap_usd        FLOAT
volume_1h_usd         FLOAT
buy_sell_ratio_5m     FLOAT
unique_buyers_1h      INT
volume_authenticity   FLOAT
price_change_1h_pct   FLOAT

-- Social
twitter_quality_mentions_1h  INT
reddit_mentions_24h           INT
bot_mention_pct               FLOAT
coordinated_shilling          BOOLEAN
sentiment_score               FLOAT

-- Safety
rugcheck_score        INT
is_honeypot           BOOLEAN

-- Full packet (for AI replay)
full_packet_json      JSONB
```

### `ai_evaluations`
```sql
id                    BIGSERIAL PRIMARY KEY
token_mint            TEXT NOT NULL REFERENCES watched_tokens(token_mint)
evaluated_at          TIMESTAMPTZ NOT NULL

decision              TEXT NOT NULL         -- RECOMMEND | WATCH | PASS | HARD_VETO
confidence            TEXT                  -- HIGH | MEDIUM | LOW
strongest_signal      TEXT
biggest_risk          TEXT
reasoning             TEXT
watch_for             TEXT
slack_message         TEXT

-- Context snapshot
mc_at_evaluation      FLOAT
wallet_count          INT
holder_count          INT

-- API cost tracking
input_tokens          INT
output_tokens         INT
cache_read_tokens     INT
cache_creation_tokens INT
veto_reason           TEXT                  -- populated if HARD_VETO (no AI call)
```

### `wallet_events`
```sql
id                    BIGSERIAL PRIMARY KEY
wallet_address        TEXT NOT NULL REFERENCES tracked_wallets(wallet_address)
token_mint            TEXT NOT NULL
event_type            TEXT NOT NULL         -- BUY | SELL
tx_signature          TEXT UNIQUE NOT NULL
event_time            TIMESTAMPTZ NOT NULL
amount_sol            FLOAT
amount_usd            FLOAT
market_cap_at_event   FLOAT
entry_percentile      FLOAT                 -- buyer position at time of buy
```

---

## Services

| Service | Tech | Purpose |
|---|---|---|
| API server | FastAPI + uvicorn | Helius webhook receiver, health endpoint |
| Wallet tracker | APScheduler | Discovery (6h) + health check (1h) loops |
| Token watcher | APScheduler + event-driven | Data collection + AI evaluation triggers |
| Database | PostgreSQL 15 | All persistent state |
| Cache | Redis | Rate limiter token buckets, deduplication |

All services run in the same Python process (single uvicorn process with APScheduler).
This is fine for the scale of this system (< 300 watched tokens at any time).
Split into separate services only if needed later.

---

## Environment variables (new .env.example)

```bash
# ── Anthropic (AI) ──────────────────────────────────────────────────
ANTHROPIC_API_KEY=

# ── Slack ───────────────────────────────────────────────────────────
SLACK_WEBHOOK_URL=                     # #recommendations channel
SLACK_WATCHLIST_WEBHOOK_URL=           # #watchlist channel (optional)
SLACK_SYSTEM_LOG_WEBHOOK_URL=          # #system-log channel (optional)

# ── Helius ──────────────────────────────────────────────────────────
HELIUS_API_KEY=
HELIUS_WEBHOOK_SECRET=

# ── Solana ──────────────────────────────────────────────────────────
SOLANA_RPC_URL=https://mainnet.helius-rpc.com/?api-key=

# ── Market data ─────────────────────────────────────────────────────
BIRDEYE_API_KEY=
# DexScreener, GeckoTerminal, Jupiter: no key needed

# ── Safety ──────────────────────────────────────────────────────────
RUGCHECK_API_KEY=                      # optional, increases rate limits

# ── Social ──────────────────────────────────────────────────────────
TWITTER_USERNAME=
TWITTER_PASSWORD=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=wigs/2.0 by /u/youruser

# ── Supplemental wallet discovery ───────────────────────────────────
BIRDEYE_API_KEY=                       # also used for PnL leaderboards
CIELO_API_KEY=                         # optional
GMGN_API_KEY=                          # optional

# ── Infrastructure ───────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://wigs:wigs@localhost:5432/wigs
REDIS_URL=redis://localhost:6379/0

# ── Feature flags ───────────────────────────────────────────────────
ENABLE_TWITTER=false
ENABLE_REDDIT=true
ENABLE_RUGCHECK=true
ENABLE_WATCHLIST_SLACK=false           # post to #watchlist channel?
ENABLE_SYSTEM_LOG_SLACK=true           # post ops events to #system-log?

# ── Wallet tracker config ────────────────────────────────────────────
WALLET_DISCOVERY_INTERVAL_HOURS=6
WALLET_HEALTH_CHECK_INTERVAL_HOURS=1
WALLET_MAX_TRADE_SIZE_USD=15000        # above this = whale, not tracked

# ── Token watcher config ─────────────────────────────────────────────
TOKEN_MAX_WATCH_DAYS=7                 # expire tokens after this
TOKEN_MIN_LIQUIDITY_USD=3000           # expire if liquidity falls below this

# ── AI config ────────────────────────────────────────────────────────
AI_MODEL=claude-sonnet-4-6
AI_MAX_TOKENS=1024
AI_EVALUATION_INTERVAL_MINUTES=30     # how often to re-evaluate watched tokens
```

---

## What is deleted from v1

The following v1 files/concepts are no longer needed:

| v1 component | Reason removed |
|---|---|
| `algorithms/convergence.py` | AI reasons about convergence from data; no numeric formula needed |
| `algorithms/evidence_fusion.py` | AI does the fusion |
| `algorithms/safety_veto.py` | Replaced by `ai/guardrails.py` (simpler, clearer) |
| `algorithms/social_verifier.py` | Social data is in the data packet; AI interprets it |
| `algorithms/market_verifier.py` | Market data is in the data packet |
| `algorithms/lead_lag.py` | Wallet timing data is in the packet; AI reasons about it |
| `algorithms/clustering.py` | Wallet independence is a wallet tracker concern, not a scoring algorithm |
| `algorithms/feedback.py` | Replaced by wallet tracker health check |
| `algorithms/outcome_labeler.py` | Replaced by wallet tracker health check |
| `algorithms/wallet_quality.py` | Wallet scoring lives in wallet_tracker/criteria.py |
| `algorithms/history_analyzer.py` | Creator history is a data aggregation field |
| `algorithms/execution_verifier.py` | Jupiter price impact is a data field |
| `algorithms/wallet_universe.py` | Wallet discovery lives in wallet_tracker/discovery.py |
| `alerts.py` | Replaced by `delivery/slack.py` |
| `workers.py` | Replaced by per-subsystem schedulers |
| `filters.py` | Mostly replaced by `ai/guardrails.py`; numeric thresholds become config |
| Telegram/Discord clients | Slack only |

Keep: `config.py`, `database.py`, `models.py` (rewrite schema), `clients/` (most of them), `app.py` (rewrite)
