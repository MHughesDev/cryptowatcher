# 02 — Data Pipeline, Strategies, and Algorithms

## Fundamental goal

The system should find Solana memecoins that satisfy three conditions:

```text
1. High-quality wallets are entering early.
2. Market/liquidity data says the token is actually tradable.
3. Independent social or real-world trend evidence confirms attention is forming.
```

The tool should mitigate risk by rejecting tokens that are likely rugs, fake-volume traps, honeypots, copycat mints, liquidity traps, or insider-distribution events.

## Why this system is wallet-led

Most new memecoins die. Scanning every token launch first produces too much noise.

Instead, the system should track **wallet behavior** first.

High-quality wallet behavior is the discovery layer. The candidate token only exists in the system after a watched wallet, watched cluster, or discovered scout wallet interacts with it.

## Pipeline overview

```text
Seed wallets
  ↓
Historical replay
  ↓
Wallet quality ranking
  ↓
Live wallet tracking
  ↓
Candidate mint detection
  ↓
Evidence graph construction
  ↓
Market/liquidity verification
  ↓
Safety/rug veto
  ↓
Social/narrative confirmation
  ↓
Scoring
  ↓
Alert
  ↓
Outcome labeling
  ↓
Wallet ranking update
```

## Phase 1 — Wallet universe builder

### Purpose

Find wallets worth tracking before live trading begins.

### Inputs

- Known whale wallets.
- Known smart-money wallets.
- Early buyers of historical winners.
- Wallets that bought before major liquidity expansion.
- Wallets that bought before social trend expansion.
- Wallets that repeatedly appear before KOL calls.
- Wallets that repeatedly enter tokens that survive more than one pump.

### Metrics

| Metric | Meaning |
|---|---|
| `realized_pnl_score` | Profit from completed trades, not unrealized wallet-mark values. |
| `early_entry_score` | How early the wallet enters relative to pool creation, first 100 holders, first liquidity jump, or first social breakout. |
| `lead_lag_score` | Whether the wallet enters before whales, KOLs, liquidity expansion, or social velocity. |
| `exit_quality_score` | Whether the wallet exits before major drawdowns rather than after them. |
| `rug_avoidance_score` | Whether the wallet avoids tokens later labeled as rugs/dead-on-arrival. |
| `repeatability_score` | Whether returns come from many trades, not one lucky outlier. |
| `independence_score` | Whether the wallet is not merely a duplicate of another tracked cluster. |
| `freshness_score` | Whether the wallet has performed well recently, not only months ago. |

### Wallet score formula

```text
wallet_quality =
    0.22 * realized_pnl_score
  + 0.18 * early_entry_score
  + 0.18 * lead_lag_score
  + 0.14 * exit_quality_score
  + 0.12 * rug_avoidance_score
  + 0.08 * repeatability_score
  + 0.05 * independence_score
  + 0.03 * freshness_score
```

### Wallet rejection rules

Reject or downgrade wallets if:

- Most profit came from one single trade.
- Wallet frequently buys honeypots or dead-on-arrival launches.
- Wallet is only profitable because it is clearly an insider wallet that dumps on retail.
- Wallet enters after the pump, not before it.
- Wallet usually exits before followers can realistically enter.
- Wallet has extreme copy-trader crowding.
- Wallet is part of a cluster that only creates fake volume.

## Phase 2 — Lead-lag wallet graph

### Purpose

Find wallets that predict other wallets or market events.

This is the **pre-whale strategy** formalized.

### Graph nodes

- Wallets.
- Token mints.
- DEX pools.
- Creator wallets.
- Social mentions.
- KOL channels.
- News/trend entities.
- Outcomes.

### Graph edges

| Edge | Meaning |
|---|---|
| `WALLET_BOUGHT_TOKEN` | Wallet bought a token. |
| `WALLET_SOLD_TOKEN` | Wallet sold a token. |
| `WALLET_FUNDED_WALLET` | One wallet funded another wallet. |
| `WALLET_PRECEDES_WALLET` | Wallet A commonly enters before Wallet B. |
| `WALLET_PRECEDES_TREND` | Wallet enters before social velocity expands. |
| `TOKEN_HAS_POOL` | Token trades on a pool. |
| `TOKEN_HAS_SOCIAL_MENTION` | Token/ticker/mint appears socially. |
| `TOKEN_LABELED_OUTCOME` | Token later became rug/dead/survivor/runner. |

### Lead-lag score

```text
lead_lag_score(wallet_a, event_b) =
    P(event_b happens after wallet_a entry within T)
  * median_forward_return_after_wallet_a
  * exit_liquidity_success_rate
  * independence_multiplier
  * freshness_multiplier
  * sample_size_confidence
  - rug_follow_penalty
  - crowding_penalty
```

### Why this matters

Copying a whale directly is often too late. The better signal is often the smaller wallet or cluster that moves before the whale.

## Phase 3 — Candidate mint detection

### Trigger event

A candidate token is created when a tracked wallet buys a token.

Required event data:

- `tx_signature`
- `wallet_address`
- `token_mint`
- `event_time`
- `amount_sol`
- `amount_usd`
- `base_asset`
- `dex_or_program`
- `pool_address`
- `route_source`
- `detected_latency_ms`

### Candidate state

```text
CANDIDATE_PENDING
CANDIDATE_ENRICHING
CANDIDATE_REJECTED
CANDIDATE_WATCH
CANDIDATE_STRONG_WATCH
CANDIDATE_STRONG_CANDIDATE
```

## Phase 4 — Market and liquidity verification

### Required checks

| Check | Description |
|---|---|
| Current liquidity | USD-equivalent liquidity across main pools. |
| Liquidity side estimate | Estimate SOL/USDC side depth if available. |
| Price | Current price from DexScreener/Gecko/Birdeye/Jupiter. |
| Volume | 5m, 1h, 6h, 24h volume. |
| Buy/sell flow | Recent net buy pressure and unique buyers/sellers. |
| Pool age | How long the primary pool has existed. |
| Market cap / FDV | Basic valuation context. |
| Route quality | Whether Jupiter can quote a realistic route. |
| Sellability | Whether token → SOL/USDC route exists. |
| Price impact | Estimate output at 0.25 SOL, 1 SOL, 5 SOL. |

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

## Phase 5 — Safety veto engine

A veto is stronger than a score.

If a token trips a hard veto, the system should not alert it as a candidate even if wallet/social signals look good.

### Hard vetoes

| Veto | Meaning |
|---|---|
| `NO_SELL_ROUTE` | Jupiter/market APIs cannot find a viable sell route. |
| `LIQUIDITY_TOO_LOW` | Pool liquidity below configured threshold. |
| `PRICE_IMPACT_TOO_HIGH` | 1 SOL or 5 SOL sell impact is unacceptable. |
| `ACTIVE_MINT_AUTHORITY` | Token can potentially mint more supply. |
| `ACTIVE_FREEZE_AUTHORITY` | Token accounts may be frozen. |
| `TOP_HOLDER_TOO_CONCENTRATED` | Top holders control too much supply. |
| `DEV_DUMP_DETECTED` | Creator/dev wallet is selling into buys. |
| `COPYCAT_MINT` | Token name/ticker resembles known token but mint/social identity mismatch. |
| `SOCIAL_DRainer_LINK` | Social links resolve to suspicious domains or wallet-drainer patterns. |

### Soft penalties

| Penalty | Meaning |
|---|---|
| `POOL_TOO_NEW` | Very new pool without enough evidence. |
| `VOLUME_TOO_BOTLIKE` | High volume with low unique buyers/holder growth. |
| `SOCIAL_TOO_THIN` | No independent online trend signal. |
| `SINGLE_WALLET_SIGNAL` | Only one wallet triggered the candidate. |
| `CLUSTER_NOT_INDEPENDENT` | Multiple wallets bought but appear connected. |
| `KOL_ALREADY_CALLED` | Public influencer call already happened; entry may be late. |

## Phase 6 — Social/narrative verification

### Goal

Confirm that the token maps to a real meme, event, trend, community, or narrative.

### Signals

| Signal | Meaning |
|---|---|
| `ticker_mention_velocity` | Mentions of token symbol across tracked channels. |
| `name_mention_velocity` | Mentions of token name. |
| `mint_mention_velocity` | Direct mint address sharing. |
| `unique_source_count` | Independent sources discussing it. |
| `reddit_velocity` | Posts/comments in selected communities. |
| `telegram_velocity` | Mentions in tracked groups/channels. |
| `discord_velocity` | Mentions inside authorized servers. |
| `youtube_velocity` | YouTube videos/shorts/title/description mentions. |
| `gdelt_relevance` | Connection to a real-world news/culture event. |
| `organic_ratio` | Mentions from varied accounts vs repeated bot spam. |

### Narrative confirmation score

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

## Phase 7 — Evidence fusion scoring

### Output scores

| Score | Purpose |
|---|---|
| `wallet_score` | Strength of wallet/cluster signal. |
| `market_score` | Liquidity, volume, price route, tradeability. |
| `risk_score` | Safety after veto/penalty evaluation. |
| `social_score` | Real social/narrative confirmation. |
| `history_score` | Creator, first buyers, pool age, prior creator launches. |
| `execution_score` | Whether a realistic entry/exit would be possible. |
| `total_score` | Weighted final score. |

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

| Score | Decision |
|---:|---|
| `< 45` | `AVOID` |
| `45–59` | `WATCH` |
| `60–74` | `STRONG_WATCH` |
| `75+` | `STRONG_CANDIDATE` |

Hard vetoes override score.

## Phase 8 — Outcome labeling

The system must learn from its own alerts.

### Outcome labels

| Label | Meaning |
|---|---|
| `RUG` | Liquidity pulled, supply dumped, or major safety failure. |
| `DEAD_ON_ARRIVAL` | No meaningful liquidity/volume after alert. |
| `ONE_CYCLE_PUMP` | Pumped once, then permanently died. |
| `TRADEABLE_RUNNER` | Had realistic upside and exit liquidity. |
| `SURVIVOR` | Survived multiple cycles with community/liquidity. |
| `HEAVY_HITTER` | Became large, durable, highly liquid meme asset. |

### Forward-return windows

Track performance after the alert at:

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

### Important metric

Do not only measure max price.

Measure:

```text
tradable_return = estimated_sell_output_after_slippage_and_price_impact
```

A token that wicked up 10x but had no exit liquidity should not be treated as a true win.

## Phase 9 — Wallet model feedback loop

After enough outcomes, update wallet scores.

### Upgrade wallets when

- They enter before tokens that become tradeable runners.
- They avoid rugs.
- Their entries produce reachable exit liquidity.
- They exit before major drawdown.
- Their edge persists over recent windows.

### Downgrade wallets when

- They repeatedly buy rugs.
- They are late.
- They bait copy traders.
- They only win in hindsight with impossible execution.
- Their signals become crowded.

## Key risk mitigations

| Risk | Mitigation |
|---|---|
| Blind copy-trading disadvantage | Use wallet signal as candidate discovery, not instant buy. |
| Scout-wallet bait | Require cluster independence and post-entry evidence. |
| Insider/cabal trap | Graph funding links, timing links, and shared exit behavior. |
| Fake volume | Compare volume to unique holders, net buyers, liquidity growth, and social velocity. |
| Rug pull | Hard veto authority risks, concentration, bad sell quote, liquidity removability. |
| MEV/sandwich | Avoid high slippage, avoid low liquidity, use quote simulation, alert-only MVP. |
| Copycat token | Verify mint address, social links, and token profile consistency. |
| Social spam | Require unique-source growth and organic ratio. |
| Overfitting | Backtest by market period and keep recent-performance decay. |
