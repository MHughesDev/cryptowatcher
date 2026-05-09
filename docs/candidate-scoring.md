# Candidate Scoring

This document covers everything that happens after a watched wallet buys a token: detection, enrichment, safety veto, social confirmation, evidence fusion, alerting, and outcome labeling.

---

## Phase 3 — Candidate Mint Detection

A candidate token is created when a tracked wallet executes a buy.

### Required event fields

| Field | Type | Description |
|---|---|---|
| `tx_signature` | string | Solana transaction signature. |
| `wallet_address` | string | Tracked wallet that triggered the event. |
| `token_mint` | string | SPL mint address of the bought token. |
| `event_time` | datetime | Chain event time. |
| `amount_sol` | decimal | SOL notional. |
| `amount_usd` | decimal | USD notional. |
| `dex_or_program` | string | Raydium, PumpSwap, Jupiter, etc. |
| `pool_address` | string | Pool if known. |
| `detected_latency_ms` | int | Time from chain event to system detection. |

### Candidate states

```text
PENDING         → just created, not yet enriched
ENRICHING       → market/safety/social data being fetched
REJECTED        → hard veto triggered or data shows not worth scoring
WATCH           → scored 45–59
STRONG_WATCH    → scored 60–74
STRONG_CANDIDATE → scored 75+
```

---

## Phase 4 — Market and Liquidity Verification

### Required checks

| Check | Description |
|---|---|
| Current liquidity | USD-equivalent liquidity across main pools. |
| Liquidity side estimate | SOL/USDC side depth if available. |
| Price | Current price from DexScreener, GeckoTerminal, Birdeye, Jupiter. |
| Volume | 5m, 1h, 6h, 24h volume. |
| Buy/sell flow | Net buy pressure and unique buyers/sellers in recent windows. |
| Pool age | How long the primary pool has existed. |
| Market cap / FDV | Basic valuation context. |
| Route quality | Whether Jupiter can quote a realistic route. |
| Sellability | Whether a token → SOL/USDC route exists. |
| Price impact | Estimated output at 0.25 SOL, 1 SOL, and 5 SOL sell sizes. |

### Liquidity realism score

```text
liquidity_realism =
    normalized_liquidity_usd
  + stable_or_SOL_side_depth_score
  + sell_quote_success_score
  + route_count_score
  - price_impact_penalty
  - liquidity_drop_penalty
```

---

## Phase 5 — Safety Veto Engine

A veto is stronger than a score. If a token trips a hard veto, it is rejected regardless of how good the wallet or social signal looks.

### Hard vetoes

| Veto | Meaning |
|---|---|
| `NO_SELL_ROUTE` | Jupiter cannot find a viable sell route. |
| `LIQUIDITY_TOO_LOW` | Pool liquidity below configured threshold. |
| `PRICE_IMPACT_TOO_HIGH` | 1 SOL or 5 SOL sell impact is unacceptable. |
| `ACTIVE_MINT_AUTHORITY` | Token can mint more supply. |
| `ACTIVE_FREEZE_AUTHORITY` | Token accounts may be frozen. |
| `TOP_HOLDER_TOO_CONCENTRATED` | Top holders control too much supply. |
| `DEV_DUMP_DETECTED` | Creator/dev wallet is selling into buys. |
| `COPYCAT_MINT` | Token name/ticker resembles a known token but mint or social identity does not match. |
| `SOCIAL_DRAINER_LINK` | Social links resolve to suspicious domains or wallet-drainer patterns. |

### Soft penalties

Soft penalties reduce the score but do not hard-reject the candidate.

| Penalty | Meaning |
|---|---|
| `POOL_TOO_NEW` | Very new pool with insufficient evidence. |
| `VOLUME_TOO_BOTLIKE` | High volume with low unique buyers or holder growth. |
| `SOCIAL_TOO_THIN` | No independent online trend signal. |
| `SINGLE_WALLET_SIGNAL` | Only one wallet triggered the candidate. |
| `CLUSTER_NOT_INDEPENDENT` | Multiple wallets bought but appear connected. |
| `KOL_ALREADY_CALLED` | Public influencer call already happened; entry window may be closed. |

---

## Phase 6 — Social and Narrative Verification

### Goal

Confirm that the token maps to a real meme, event, trend, community, or narrative — not just to coordinated wallet behavior.

### Signals

| Signal | Meaning |
|---|---|
| `ticker_mention_velocity` | Mentions of the token symbol across tracked channels. |
| `name_mention_velocity` | Mentions of the token name. |
| `mint_mention_velocity` | Direct mint address sharing. |
| `unique_source_count` | Independent sources discussing it. |
| `reddit_velocity` | Posts/comments in target communities. |
| `telegram_velocity` | Mentions in tracked groups/channels. |
| `discord_velocity` | Mentions in authorized servers. |
| `youtube_velocity` | Video/short/title/description mentions. |
| `gdelt_relevance` | Connection to a real-world news or culture event. |
| `organic_ratio` | Mentions from varied accounts vs repeated bot spam. |

### Social score formula

```text
social_score =
    0.25 * mention_velocity
  + 0.20 * unique_source_count
  + 0.15 * social_acceleration
  + 0.15 * real_world_event_match
  + 0.10 * mint_address_mentions
  + 0.10 * organic_ratio
  + 0.05 * content_quality
```

---

## Phase 7 — Evidence Fusion Scoring

### Component scores

| Score | What it measures |
|---|---|
| `wallet_score` | Triggering wallet quality, independent wallet count, lead-lag strength, cluster risk. |
| `market_score` | Liquidity, volume, price route, tradeability. |
| `risk_score` | Safety after veto and penalty evaluation. |
| `social_score` | Real social/narrative confirmation. |
| `history_score` | Creator history, early holder quality, pool age, prior creator launches. |
| `execution_score` | Whether a realistic entry and exit would be possible. |

### Final score formula

```text
total_score =
    0.30 * wallet_score
  + 0.20 * market_score
  + 0.20 * risk_score
  + 0.15 * social_score
  + 0.10 * history_score
  + 0.05 * execution_score
```

### Decision thresholds

| Score range | Decision |
|---:|---|
| `< 45` | `AVOID` |
| `45–59` | `WATCH` |
| `60–74` | `STRONG_WATCH` |
| `75+` | `STRONG_CANDIDATE` |

Hard vetoes override the score and produce `AVOID` regardless of total.

---

## Phase 8 — Outcome Labeling

The system must learn from its own alerts. Every alert is replayed at fixed intervals to measure what actually happened.

### Outcome labels

| Label | Meaning |
|---|---|
| `RUG` | Liquidity pulled, supply dumped, or major safety failure. |
| `DEAD_ON_ARRIVAL` | No meaningful liquidity or volume after the alert. |
| `ONE_CYCLE_PUMP` | Pumped once, then permanently died. |
| `TRADEABLE_RUNNER` | Had realistic upside and exit liquidity. |
| `SURVIVOR` | Survived multiple cycles with active community and liquidity. |
| `HEAVY_HITTER` | Became a large, durable, highly liquid meme asset. |

### Forward-return windows

```text
5 minutes
15 minutes
30 minutes
1 hour
4 hours
24 hours
3 days
7 days
```

### Key metric: tradable return

Do not only measure max price. Measure:

```text
tradable_return = estimated_sell_output_after_slippage_and_price_impact
```

A token that wicked 10x but had no exit liquidity is not a win.

---

## Phase 9 — Wallet Feedback Loop

After enough outcomes, wallet scores are updated.

### Upgrade wallets when

- They enter before tokens that become tradeable runners.
- They avoid rugs.
- Their entries produce reachable exit liquidity.
- They exit before major drawdowns.
- Their edge persists over recent time windows.

### Downgrade wallets when

- They repeatedly buy rugs.
- They consistently enter late.
- They bait copy traders.
- They only win in hindsight with execution that was never realistic.
- Their signals become crowded.

---

## Risk mitigations

| Risk | Mitigation |
|---|---|
| Blind copy-trading disadvantage | Use wallet signal as candidate discovery, not an instant buy trigger. |
| Scout-wallet bait | Require cluster independence and post-entry evidence before scoring up. |
| Insider/cabal trap | Graph funding links, entry timing, and shared exit behavior. |
| Fake volume | Compare volume to unique holders, net buyers, liquidity growth, and social velocity. |
| Rug pull | Hard veto authority risks, holder concentration, bad sell quote, and liquidity removability. |
| MEV/sandwich | Avoid high slippage and low liquidity; use quote simulation; alert-only MVP removes execution risk entirely. |
| Copycat token | Verify mint address, social links, and token profile consistency. |
| Social spam | Require unique-source growth and organic ratio checks. |
| Overfitting | Backtest by market period; apply recency decay to wallet scores. |
