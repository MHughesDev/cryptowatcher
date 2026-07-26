# Subsystem 3 — Data Aggregation

## Purpose

Collect every meaningful data point about a watched token and assemble it
into a structured TokenDataPacket for Claude. This is the most important
subsystem to get right. Better data = better AI decisions.

The aggregator never decides anything. It collects and organizes.

---

## TokenDataPacket — complete data specification

This is the exact structure Claude receives. Every field matters.

---

### Section 1 — Identity & basics

```
token_mint:          str    # SPL mint address (primary key)
symbol:              str    # ticker symbol (untrusted — display only)
name:                str    # full name (untrusted — display only)
token_age_minutes:   float  # how old is this token
dex:                 str    # primary DEX (Raydium, PumpSwap, Orca, etc.)
launch_platform:     str    # pump.fun | direct | unknown
graduated_pump_fun:  bool   # did it migrate off pump.fun bonding curve?
```

**Why:** Claude needs to know what it's looking at and how mature/new the token is.
Very new tokens (<5 min) are higher risk. pump.fun graduates have different
dynamics than direct launches.

---

### Section 2 — On-chain supply and distribution

```
total_supply:             float   # total token supply
circulating_supply:       float   # estimated circulating (excl. locked/burned)
holder_count:             int     # total unique holder addresses
holder_growth_rate_1h:    float   # % change in holder count over last hour

top_10_holders_pct:       float   # % of supply held by top 10 addresses
top_20_holders_pct:       float   # % of supply held by top 20 addresses
top_50_holders_pct:       float   # % of supply held by top 50 addresses

# Gini coefficient — measures distribution inequality
# 0.0 = perfectly equal, 1.0 = one wallet holds everything
gini_coefficient:         float

# HHI — Herfindahl-Hirschman Index (concentration measure)
# 0.0 = perfect competition, 1.0 = monopoly
hhi:                      float
```

**Why:** The single most important structural safety signal. A token where 10 wallets
hold 80% is a rug waiting to happen. Claude needs exact numbers, not a boolean.

---

### Section 3 — Dev and insider holdings

```
creator_wallet:                str     # deployer/creator wallet address
creator_current_holding_pct:   float   # what % of supply does creator still hold?
creator_initial_holding_pct:   float   # what % did creator hold at launch?
creator_sold_pct:              float   # how much has creator sold since launch?
creator_sell_events_count:     int     # how many sell transactions has creator made?
creator_last_sell_at:          datetime | None

# Insider detection: wallets funded by same source as creator,
# or that bought in the first 5 blocks and are connected to creator
insider_wallet_count:          int
insider_total_holding_pct:     float  # combined insider holdings

# Dev wallet activity in last hour
creator_active_last_1h:        bool
creator_transferred_last_1h:   bool
```

**Why:** Creator still holding 30%+ is an existential rug risk. Creator selling
after the first 10 minutes is a major red flag. Claude should know exactly what
the creator is doing with their position in real time.

---

### Section 4 — Bundle and snipe detection

```
# "Bundled" supply = tokens bought in same block as launch by multiple wallets
# controlled by the same entity, coordinated to look like organic demand
bundled_wallet_count:      int     # wallets that participated in launch bundle
bundled_supply_pct:        float   # % of supply held by bundle wallets
bundle_still_holding_pct:  float   # how much of bundle supply has NOT been sold

# Snipers = bots that buy in blocks 1-3 of launch
sniper_wallet_count:       int
sniper_supply_pct:         float   # % of supply held by snipers
snipers_still_holding_pct: float   # how much sniper supply is still held (sell risk)

# Combined "hostile supply" — insider + bundle + sniper, deduplicated
hostile_supply_pct:        float   # total % that could dump at any moment
```

**Why:** Bundled supply is one of the most common hidden rug mechanisms.
If 15 wallets bundled 40% of supply and are still holding, that's a landmine.
Claude needs to know the real "sellable" distribution, not the nominal one.

---

### Section 5 — Liquidity and pool health

```
liquidity_usd:               float  # total LP liquidity in USD
liquidity_sol:               float  # LP liquidity denominated in SOL
pool_age_minutes:            float  # how old is the main liquidity pool
pool_address:                str

# LP lock status — is the liquidity locked from being removed?
lp_locked:                   bool
lp_lock_duration_days:       float | None  # how long is it locked
lp_lock_pct:                 float | None  # what % of LP is locked
lp_locker:                   str | None    # who/what locked it (e.g. Streamflow)

# Price impact — how much does a sell move the price?
price_impact_01_sol:         float | None  # 0.1 SOL sell impact
price_impact_05_sol:         float | None  # 0.5 SOL sell impact
price_impact_1_sol:          float | None  # 1 SOL sell impact
price_impact_5_sol:          float | None  # 5 SOL sell impact

sell_route_exists:           bool          # can you actually sell?
```

**Why:** LP lock is one of the hardest safety signals. Unlocked LP = rug in seconds.
Price impact tells Claude how liquid exits actually are, not just what the
liquidity number says.

---

### Section 6 — Token authority status

```
mint_authority_active:    bool  # can more tokens be minted? (CRITICAL — always false for safety)
freeze_authority_active:  bool  # can wallets be frozen? (CRITICAL — always false for safety)
update_authority_active:  bool  # can token metadata be changed?
```

**Why:** These are non-negotiable hard vetoes in the pre-screen, but they're
included in the data packet so Claude's reasoning log explains WHY a token was
safe or unsafe even when it wasn't the deciding factor.

---

### Section 7 — Market dynamics

```
price_usd:               float
price_sol:               float
market_cap_usd:          float  # current
fdv_usd:                 float  # fully diluted valuation
ath_mc_usd:              float | None  # all-time high MC since launch
ath_mc_reached_at:       datetime | None

# Volume
volume_5m_usd:           float
volume_15m_usd:          float
volume_1h_usd:           float
volume_6h_usd:           float
volume_24h_usd:          float
volume_to_mc_ratio_1h:   float  # high ratio = active trading

# Buy/sell pressure
buys_5m:                 int     # number of buy transactions in 5 min
sells_5m:                int     # number of sell transactions in 5 min
buy_sell_ratio_5m:       float   # buys / sells — >1.0 = more buying pressure
unique_buyers_1h:        int     # distinct wallet addresses buying in 1h
unique_sellers_1h:       int

# Price action (change percentages)
price_change_5m_pct:     float
price_change_1h_pct:     float
price_change_6h_pct:     float

# Volume authenticity — estimated % of volume that is real (not wash traded)
volume_authenticity_pct: float  # 0-100, higher = more authentic
```

**Why:** Claude needs to understand what's happening right now in the market.
Is there genuine buying pressure? Is volume authentic? Is the price running
or has it already pumped and is now distributing?

---

### Section 8 — Wallet signal quality

```
# The tracked wallets that triggered this token entering the system
triggering_wallets: list[{
    wallet_address: str
    wallet_win_rate_30d: float      # this wallet's 30-day win rate
    wallet_realized_pnl_30d_usd: float
    wallet_qualifying_plays_30d: int
    wallet_avg_trade_size_usd: float
    buy_time: datetime              # when this wallet bought
    buy_mc_usd: float               # market cap at time of this wallet's buy
    entry_percentile: float         # what % of holders existed before this wallet bought
                                    # 0.05 = top 5% = very early; 0.90 = very late
    amount_sol: float               # how much SOL this wallet spent
}]

# Aggregate signal metrics
total_watching_wallet_count: int
buy_time_spread_seconds:     float   # spread between first and last tracked wallet buy
median_entry_percentile:     float   # median entry timing across all watching wallets
avg_watching_wallet_win_rate: float
avg_buy_mc_usd:              float   # average MC across all wallet buys (signal quality gate)
```

**Why:** This is the core signal. Claude needs to know not just that wallets bought,
but HOW GOOD those wallets are, HOW EARLY they got in, and at WHAT MARKET CAP.
A 3x winner buying a $50k MC token at 2% holder depth is a very different signal
from a mediocre wallet buying a $500k MC token at 80% holder depth.

---

### Section 9 — Creator and project history

```
# Creator's previous tokens on Solana
creator_prior_token_count:     int
creator_prior_rug_count:       int     # tokens that rugpulled
creator_prior_success_count:   int     # tokens that 5x+ and survived 7 days
creator_prior_median_outcome:  str     # RUG | DEAD | PUMP | SURVIVOR | WINNER

# Associated wallets — did any wallets connected to this creator launch tokens before?
associated_wallet_rug_count:   int

# Is this a copycat / clone of a recent token?
is_copycat:                    bool
copycat_of:                    str | None
```

**Why:** Serial ruggers almost always rug again. A creator with 5 previous tokens
all of which rugged within 24h is a near-certain repeat. Claude needs this context.

---

### Section 10 — Social presence and momentum

```
# Twitter / X
twitter_handle:              str | None
twitter_followers:           int | None
twitter_account_age_days:    int | None
twitter_verified:            bool | None
twitter_created_same_day_as_token: bool  # red flag if true

# Recent mention velocity
twitter_mentions_1h:         int    # raw mention count (all accounts)
twitter_mentions_6h:         int
twitter_quality_mentions_1h: int    # mentions from accounts >30 days old, >100 followers
twitter_cashtag_volume_1h:   int    # $SYMBOL mentions specifically
twitter_sentiment_score:     float  # -1.0 (bearish) to 1.0 (bullish)

reddit_mentions_24h:         int
reddit_quality_mentions_24h: int    # from accounts >90 days old

# Is there obvious coordinated shilling? (same text copy-pasted across accounts)
coordinated_shilling_detected: bool
bot_mention_pct:              float  # estimated % of mentions from bot accounts

# Viral content
has_viral_content:            bool   # has any single tweet/post >1k engagements
viral_content_age_minutes:    float | None  # how old is the viral content

# Narrative type
narrative_type: str  # ANIMAL | AI_TECH | MEME_CULTURE | REAL_WORLD_EVENT | DERIVATIVE | UNKNOWN
narrative_strength: str  # WEAK | MODERATE | STRONG (subjective, Claude assesses)
```

**Why:** Social context is crucial for memecoins — they run on narrative.
Claude needs to distinguish organic excitement from paid shilling from bot spam.
A viral tweet from a real account with 100k followers is fundamentally different
from 500 bot accounts copy-pasting the same message.

---

### Section 11 — Safety scoring

```
# Third-party risk scores
rugcheck_score:       int | None    # 0-100, higher = safer (rugcheck.xyz)
rugcheck_risks:       list[str]     # specific risk flags from rugcheck

# Honeypot check
is_honeypot:          bool          # can't sell at all?
honeypot_reason:      str | None
```

**Why:** RugCheck aggregates many safety signals into a single score and provides
specific risk labels. Claude can use these as a fast summary of known risks.

---

### Section 12 — Evaluation history (context for Claude)

```
# All previous AI evaluations on this token (most recent first)
previous_evaluations: list[{
    evaluated_at: datetime
    decision: str          # RECOMMEND | WATCH | PASS
    confidence: str        # HIGH | MEDIUM | LOW
    reasoning: str         # Claude's full reasoning from that evaluation
    mc_at_evaluation: float
}]

# How has the token evolved since first watched?
mc_change_since_first_watch_pct:  float  # how much has MC changed?
holder_change_since_first_watch:  int    # how many new holders?
liquidity_change_since_first_watch_pct: float
```

**Why:** Claude should know if it has seen this token before and what it thought.
This prevents Claude from contradicting itself and gives it a trajectory to reason
about ("this token is growing steadily" vs "this token is dumping").

---

## Data source mapping

| Data section | Primary source | Fallback |
|---|---|---|
| Identity | Helius Enhanced TX | DexScreener |
| Supply & distribution | Solana RPC getTokenLargestAccounts | Birdeye |
| Dev holdings | Solana RPC + on-chain trace | Helius |
| Bundle/snipe detection | On-chain block analysis | Birdeye security |
| Liquidity & pool | DexScreener | GeckoTerminal |
| LP lock status | On-chain (Streamflow, etc.) | RugCheck |
| Authority status | Solana RPC getAccountInfo | Birdeye security |
| Market dynamics | DexScreener + Birdeye | GeckoTerminal |
| Wallet signal | Internal DB (from wallet tracker) | — |
| Creator history | Internal DB + Helius | — |
| Social | twikit (Twitter) + Reddit | — |
| Safety scores | RugCheck API | — |
| Evaluation history | Internal DB | — |

See `06-data-sources.md` for full API specs.

---

## Data freshness requirements

| Data type | Max age when Claude is called |
|---|---|
| Market dynamics (price, volume) | 60 seconds |
| Holder count and distribution | 5 minutes |
| Dev wallet holdings | 5 minutes |
| Bundle/snipe detection | Computed once at entry, refreshed every 30 min |
| LP lock status | 5 minutes |
| Social mentions | 5 minutes |
| Wallet signal | Real-time (event-driven) |
| Creator history | Computed once at entry |
| Safety scores | 10 minutes |

If any critical field is stale beyond its limit when Claude is called,
the AI call is delayed until fresh data is available, with a max wait of 60 seconds.
If still unavailable → call Claude with the field marked as `"DATA_UNAVAILABLE"`.
