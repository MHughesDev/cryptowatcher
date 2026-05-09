# Candidate Scoring

Everything that happens after a watched wallet buys a token: detection, wallet convergence, market verification, safety veto, social confirmation, evidence fusion, alerting, and outcome labeling.

---

## Phase 1 — Candidate Mint Detection

A candidate token enters the system when a tracked wallet executes a buy. Tracking starts at the moment of detection, not at token launch — so detection latency matters and is measured.

### Trigger event fields

| Field | Type | Description |
|---|---|---|
| `tx_signature` | string | Solana transaction signature. |
| `wallet_address` | string | Tracked wallet that triggered the event. |
| `token_mint` | string | SPL mint address. |
| `event_time` | datetime | Chain event time. |
| `amount_sol` | decimal | SOL notional. |
| `amount_usd` | decimal | USD notional. |
| `dex_or_program` | string | Raydium, PumpSwap, Jupiter, etc. |
| `pool_address` | string | Pool if known. |
| `detected_latency_ms` | int | Time from chain event to system detection. |

### Candidate state machine

```
PENDING
  ↓ (enrichment starts)
ENRICHING
  ↓                    ↓
SCORED             REJECTED (hard veto during enrichment)
  ↓
WATCH / STRONG_WATCH / STRONG_CANDIDATE
```

Every state transition is logged with a timestamp and the reason for the transition.

---

## Phase 2 — Wallet Convergence Scoring

**This is the most important scoring phase.** A single wallet buying a token is a weak signal. Multiple independent high-quality wallets converging on the same token within a short window is a very strong signal.

The convergence score is computed as a **weighted, independence-adjusted, time-compressed vote** across all tracked wallets that have bought the token.

### Convergence score formula

```
convergence_score(token) =
    (Σ wallet_quality[i] * recency_weight[i] * independence_weight[i])
    * time_compression_factor
    * independence_confidence
```

#### Term definitions

**`wallet_quality[i]`** — The composite 0–100 wallet quality score from the wallet engine.

**`recency_weight[i]`** — Exponential decay from the time of entry:

```
recency_weight[i] = exp(-λ * minutes_since_entry[i])
λ = 0.05    (half-life ~14 minutes — tune based on observed alpha decay)
```

Buys that happened 30 minutes ago have less signal value than buys 5 minutes ago.

**`independence_weight[i]`** — Penalizes wallets from the same cluster. Only one vote per confirmed cluster:

```
if wallet[i] is in a CABAL_SUSPECT or BOT_FARM cluster:
    independence_weight[i] = 0                    # excluded entirely
elif wallet[i] is in a SMART_MONEY cluster:
    independence_weight[i] = 1 / cluster_size     # distributed vote
else:
    independence_weight[i] = 1.0                  # full independent vote
```

**`time_compression_factor`** — Boosts the signal when wallets buy close together in time. Multiple wallets buying within seconds of each other is a much stronger signal than the same wallets buying hours apart.

```
time_spread_seconds = std_dev(entry_times_of_all_buyers)

time_compression_factor =
    1.0                              if time_spread > 30 minutes
    1.0 + (1 - time_spread/1800)     if 5 min < time_spread ≤ 30 min
    2.0                              if time_spread ≤ 5 minutes
```

**`independence_confidence`** — Shrinks the score if there are too few samples to trust independence assessment:

```
independence_confidence = min(1.0, verified_independent_buyers / 3)
```

Reaches 1.0 (no shrinkage) once 3 confirmed independent wallets have bought.

### Convergence multiplier on total score

The convergence score feeds into `wallet_score`, but the **number of independent wallets** also acts as a direct multiplier on the final candidate decision threshold:

| Independent wallet count | Score threshold adjustment |
|---:|---|
| 1 | No adjustment. |
| 2 | Thresholds reduced by 5 points (easier to reach WATCH). |
| 3 | Thresholds reduced by 10 points. |
| 4 | Thresholds reduced by 15 points. |
| 5+ | Thresholds reduced by 20 points (max reduction). |

This means a token that would normally score 58 (WATCH) with 5 independent buyers effectively qualifies as STRONG_WATCH (≥60 equivalent).

### Convergence alert upgrade

If convergence happens fast enough, the system upgrades the alert tier regardless of other scores:

```
if independent_buyers ≥ 3
   and time_spread ≤ 10 minutes
   and no hard veto active:
       minimum_decision = STRONG_WATCH
```

This ensures that a rapid multi-wallet convergence event is never silently demoted to WATCH just because the social or market scores haven't had time to populate yet.

---

## Phase 3 — Market and Liquidity Verification

### Required checks

| Check | Description |
|---|---|
| Current liquidity | USD-equivalent across all known pools for this mint. |
| Liquidity side depth | SOL/USDC side depth — tells if the buy side is real or thin. |
| Price | Cross-reference DexScreener, GeckoTerminal, Birdeye, Jupiter. |
| Volume | 5m, 1h, 6h, 24h absolute and buy/sell decomposition. |
| Unique buyers | Distinct buyer count in the last 5m and 1h — filters bot volume. |
| Pool age | How long the primary pool has existed. |
| Market cap / FDV | Basic valuation context. |
| Route quality | Jupiter can quote a realistic buy route. |
| Sellability | Token → SOL/USDC route exists and doesn't produce catastrophic slippage. |
| Price impact | Simulated output at 0.25 SOL, 1 SOL, and 5 SOL sell sizes. |

### Volume authenticity check

Raw volume is not a reliable signal — bots can manufacture it. Validate with:

```
volume_authenticity_ratio = unique_buyers_5m / (total_volume_5m / avg_trade_size)
```

Low ratio = few buyers generating high volume = likely wash trading. Apply `VOLUME_TOO_BOTLIKE` soft penalty if ratio < 0.2.

Additionally compare volume growth to holder count growth. Real organic growth shows both growing together. Volume growing without holder count growth is suspicious.

### Liquidity realism score

```
liquidity_realism =
    normalize(liquidity_usd) * 0.30
  + stable_or_sol_side_depth_score * 0.25
  + sell_quote_success_score * 0.20
  + route_count_score * 0.15
  - price_impact_penalty * 0.10
```

Where:
- `sell_quote_success_score` = 1.0 if all three sell-size simulations (0.25, 1, 5 SOL) return valid quotes without excessive slippage.
- `route_count_score` = normalize(number of routes Jupiter finds for the sell side).
- `price_impact_penalty` = linear penalty starting when 1 SOL sell impact exceeds 5%.

### Market score formula

```
market_score =
    0.35 * liquidity_realism
  + 0.25 * volume_authenticity_ratio
  + 0.20 * price_stability_score      [low volatility = more trustworthy liquidity]
  + 0.20 * pool_maturity_score        [older pool = more trusted; very new = penalty]
```

---

## Phase 4 — Safety Veto Engine

A veto is **categorical** — it overrides score entirely. A token that trips a hard veto is `REJECTED` regardless of wallet signal strength.

### Hard vetoes

| Veto | Detection method |
|---|---|
| `NO_SELL_ROUTE` | Jupiter quote API returns no valid route token → SOL/USDC. |
| `LIQUIDITY_TOO_LOW` | Total liquidity_usd < configured minimum (default: $5,000). |
| `PRICE_IMPACT_TOO_HIGH` | 1 SOL sell simulates >15% impact OR 5 SOL sell simulates >40% impact. |
| `ACTIVE_MINT_AUTHORITY` | Solana RPC confirms mint authority is not null/revoked. |
| `ACTIVE_FREEZE_AUTHORITY` | Solana RPC confirms freeze authority is not null/revoked. |
| `TOP_HOLDER_TOO_CONCENTRATED` | Top 10 holders control >60% of supply. |
| `DEV_DUMP_DETECTED` | Creator wallet or known dev wallet is selling into buy pressure. |
| `COPYCAT_MINT` | Token name/ticker matches a known token but mint address, creator, and social links do not. |
| `SOCIAL_DRAINER_LINK` | Social URLs in token metadata resolve to wallet drainer patterns. |

### Holder concentration algorithms

Two metrics computed in parallel:

**Gini coefficient:**
```
G = (2 * Σ (rank[i] * balance[i])) / (N * Σ balance[i]) - (N+1)/N
```

Healthy memecoins in early growth: G ≈ 0.60–0.75.
Extreme concentration / likely insider control: G > 0.90.

**Herfindahl-Hirschman Index (HHI):**
```
HHI = Σ (balance[i] / total_supply)²
```

- HHI > 0.25 → high concentration, apply `TOP_HOLDER_TOO_CONCENTRATED` if combined with other flags.
- HHI < 0.10 → reasonably distributed.

Both are computed and stored in `token_risk_snapshots`. Either exceeding the threshold contributes to the veto decision.

### Dev dump detection

Monitor the creator wallet address (extracted from the token's mint transaction) for outgoing swaps during the same window as the wallet convergence event:

```
dev_dump_detected = (
    creator_wallet in active_sellers
    AND creator_sell_amount > creator_buy_amount * 0.5
    AND time_since_launch < 4_hours
)
```

### Soft penalties

These reduce `risk_score` but do not veto the token.

| Penalty | Condition | Score reduction |
|---|---|---|
| `POOL_TOO_NEW` | Pool age < 10 minutes. | -15 |
| `VOLUME_TOO_BOTLIKE` | Volume authenticity ratio < 0.2. | -20 |
| `SOCIAL_TOO_THIN` | `social_score` < 20 and social data has had > 30 minutes to populate. | -10 |
| `SINGLE_WALLET_SIGNAL` | Only 1 wallet triggered the candidate. | -10 |
| `CLUSTER_NOT_INDEPENDENT` | Multiple buyers but cluster analysis puts them in the same group. | -20 |
| `KOL_ALREADY_CALLED` | A tracked KOL has already publicly posted about this token. | -15 |
| `HIGH_DEV_HOLDING` | Dev wallet still holds > 10% of supply but no active dump detected yet. | -10 |

### Risk score computation

```
risk_score = 100 - Σ(penalty_values)

if any hard veto is active:
    risk_score = 0
    decision = AVOID   [override]
```

---

## Phase 5 — Social and Narrative Verification

### Goal

Confirm that the token maps to a real meme, event, narrative, or community — not just coordinated wallet activity. A token with wallet convergence but zero social traction is a potential insider trap.

### Search term construction

```python
search_terms = [
    token.token_mint,           # mint address (most specific)
    token.symbol,               # ticker
    token.name,                 # full name
    normalize(token.symbol),    # lowercase, no punctuation
    normalize(token.name),
]
```

The mint address match is the strongest signal — it means someone is sharing the actual contract address, not just a similar name.

### Per-channel signals

| Channel | Window | Signal |
|---|---|---|
| Reddit | 24h | Post count, comment count in target subs. |
| Telegram | 6h | Message count in monitored groups/channels. |
| Discord | 6h | Message count in authorized servers. |
| YouTube | 7d | Video/short/title/description mentions. |
| GDELT | 7d | News article link to a real-world event matching the token's narrative. |

### Mention velocity (not absolute count)

Raw mention count is noisy. Track the **rate of change** (velocity acceleration):

```
velocity_5m = mentions_last_5m - mentions_5m_to_10m_ago
velocity_acceleration = velocity_5m - velocity_last_5m
```

A sharp, accelerating rise on multiple independent platforms is a strong signal.
A flat or declining velocity, even at high absolute volume, is a weak signal.

### Bot / coordination detection — Novelty Score

Detect coordinated inauthentic social campaigns using cosine similarity between consecutive post embeddings:

```
novelty_score = 1 - avg_cosine_similarity(embedding[post_i], embedding[post_i+1])
```

Computed over a rolling 30-minute window of posts about the token. Low novelty (< 0.35) means posts are near-identical in language → likely bot campaign or coordinated spam. High novelty means organic diverse discussion.

Encode posts using a lightweight embedding model (sentence-transformers or CryptoBERT). CryptoBERT is pre-trained on 3.2M crypto social posts and outperforms generic BERT on crypto-specific jargon.

### Unique source diversity

Count independent origin domains/accounts:

```
unique_source_score = normalize(distinct_accounts_or_domains_mentioning_token)
```

50 posts from 50 accounts beats 50 posts from 2 accounts. Weight accounts by:
- Account age > 30 days: +1
- Account history mentioning crypto topics: +0.5
- Account created < 7 days ago: 0 weight (new accounts excluded)

### Narrative classification

Run the token's name, ticker, and social context through a simple classifier:

| Narrative type | Examples | Signal quality |
|---|---|---|
| Real-world event map | "POPE", "TARIFF", "QUAKE" | Strong — verifiable external event. |
| Animal / meme culture | "DOGE", "SHIB variants" | Moderate — depends on freshness. |
| AI / tech narrative | "GPT", "CLAUDE", "AGI" | Moderate. |
| Celebrity / political | Person names | Moderate — high velocity potential. |
| Derivative / copycat | "DOGE2", "SHIB killer" | Weak — apply `COPYCAT_MINT` check. |
| Unknown / random | No clear mapping | Weak. |

Tokens that map to a verifiable real-world event (GDELT match) get a bonus on `gdelt_relevance`.

### Social score formula

```
social_score =
    0.25 * velocity_acceleration_score    [rate of growth, not absolute count]
  + 0.20 * unique_source_diversity_score  [independent origins]
  + 0.15 * novelty_score                 [organic vs. bot campaign]
  + 0.15 * gdelt_real_world_match_score  [verifiable external event]
  + 0.10 * mint_address_mention_score    [direct contract address sharing]
  + 0.10 * cross_platform_score          [mentions on 3+ different platforms]
  + 0.05 * content_quality_score         [accounts with history, age, engagement]
```

---

## Phase 6 — Evidence Fusion Scoring

### Component scores summary

| Score | Source | Weight |
|---:|---|---|
| `wallet_score` | Convergence score + lead-lag strength. | 0.35 |
| `market_score` | Liquidity, volume, tradeability, pool quality. | 0.20 |
| `risk_score` | Safety veto + penalty aggregate. | 0.20 |
| `social_score` | Velocity, novelty, unique sources, event match. | 0.15 |
| `history_score` | Creator history, early holder quality, launch context. | 0.07 |
| `execution_score` | Sellability, price impact, route quality. | 0.03 |

Wallet score weight is raised to 0.35 (from the original 0.30) because convergence is now a rich multi-dimensional signal, not just a single wallet quality check.

### History score

```
history_score =
    0.40 * creator_reputation_score     [past launches, rug rate, survival rate]
  + 0.30 * early_holder_quality_score   [avg wallet_quality of first 50 holders]
  + 0.20 * launch_context_score         [Pump.fun bonding curve vs. direct DEX, etc.]
  + 0.10 * pool_creation_context_score  [abnormal pre-launch activity = red flag]
```

### Execution score

```
execution_score =
    0.50 * sell_route_exists_score     [binary: 1.0 if route exists, 0 if not]
  + 0.30 * price_impact_score          [0.25 SOL to 5 SOL range]
  + 0.20 * route_depth_score           [how many competitive routes Jupiter finds]
```

### Final score formula

```
total_score =
    0.35 * wallet_score
  + 0.20 * market_score
  + 0.20 * risk_score
  + 0.15 * social_score
  + 0.07 * history_score
  + 0.03 * execution_score
```

### Decision thresholds (base)

| Score range | Decision |
|---:|---|
| `< 45` | `AVOID` |
| `45–59` | `WATCH` |
| `60–74` | `STRONG_WATCH` |
| `75+` | `STRONG_CANDIDATE` |

These thresholds are adjusted downward when independent wallet convergence count ≥ 2 (see Phase 2).

Hard vetoes override the score and force `AVOID` regardless of total.

### Dempster-Shafer combination for safety vetoes

Safety vetoes are combined using Dempster-Shafer Evidence Theory rather than simple boolean logic. This handles cases where multiple partial signals each independently raise risk without any single one triggering the hard threshold.

Each veto condition produces a basic probability assignment (BPA):

```
m({SAFE}) = P(condition is false)
m({RISKY}) = P(condition is true)
m({SAFE, RISKY}) = uncertainty
```

Combined via Dempster's rule:

```
m(A) = Σ m₁(B) * m₂(C) for B ∩ C = A, normalized by (1 - K)
K = Σ m₁(B) * m₂(C) for B ∩ C = ∅    [conflict term]
```

The combined belief in RISKY triggers a soft or hard veto depending on the threshold:
- Belief(RISKY) > 0.6 → soft penalty applied.
- Belief(RISKY) > 0.85 → hard veto applied.

This allows partial signals (borderline concentration + moderately low liquidity + slightly suspicious timing) to accumulate into a veto even when no single condition would trigger it alone.

---

## Phase 7 — Outcome Labeling

The system must learn from its own alerts. Every alert is replayed at fixed time windows to measure what actually happened.

### Outcome labels

| Label | Condition |
|---|---|
| `RUG` | Liquidity pulled > 50% within 24h, OR supply dumped, OR sell route disappears. |
| `DEAD_ON_ARRIVAL` | No meaningful volume or holder growth after alert. Token still exists but is dormant. |
| `ONE_CYCLE_PUMP` | Clear pump visible in price data, followed by permanent collapse. |
| `TRADEABLE_RUNNER` | Had realistic upside and measurable exit liquidity across a reasonable window. |
| `SURVIVOR` | Survived multiple cycles. Still has active community and liquidity 7 days post-alert. |
| `HEAVY_HITTER` | Became a large, durable, highly liquid meme asset. |

### Forward-return windows

Snapshot market data at each interval after alert:

```
5 min, 15 min, 30 min, 1h, 4h, 24h, 3d, 7d
```

### Tradable return (the correct metric)

Do not measure max price. Measure:

```
tradable_return(t) = estimated_sell_output_after_slippage_and_price_impact(t)
```

Simulate a sell of a fixed notional (e.g., 1 SOL equivalent) at each measurement window using Jupiter quote API. A token that wicked 10x but had 90% price impact on a 1 SOL sell is not a real win.

---

## Phase 8 — Wallet Feedback Loop

After outcome labeling, wallet scores are updated using **Thompson Sampling** over a Beta distribution:

### Thompson Sampling per wallet

Each wallet maintains a Beta(α, β) posterior over its signal quality:

```
Initial prior: Beta(2, 2)    [weakly uncertain, no strong prior]

On TRADEABLE_RUNNER or HEAVY_HITTER outcome:
    α += 1    [success]

On RUG, DEAD_ON_ARRIVAL, or ONE_CYCLE_PUMP outcome:
    β += 1    [failure]

On SURVIVOR or ONE_CYCLE_PUMP (exit was profitable):
    α += 0.5  [partial credit]
```

To decide whether to increase or decrease a wallet's live weight:

```
sample = Beta(α, β).sample()
if sample > 0.6: increase wallet trust weight
elif sample < 0.4: decrease wallet trust weight
```

This naturally explores new or uncertain wallets (high uncertainty = wide distribution = more likely to get a high sample occasionally) while exploiting proven wallets.

### Wallet quality formula update

After 50+ outcomes per wallet, re-fit the sub-score weights in the `wallet_quality` formula using gradient boosting regression (XGBoost) with the labeled outcome as the target:

```
target = tradable_return_1h (continuous) or outcome_label (categorical)
features = [realized_pnl_score, early_entry_score, lead_lag_score, ...]
```

The fitted feature importances replace the hard-coded weights (0.22, 0.18, etc.) with data-derived weights.

### Upgrade wallets when

- They enter before tokens that become `TRADEABLE_RUNNER` or `HEAVY_HITTER`.
- `tradable_return_1h` > 0 consistently.
- They avoid rugs (entry on tokens that later become `DEAD_ON_ARRIVAL` or `RUG`).
- Their entries produce reachable exit liquidity.
- Their edge persists in recent time windows (freshness check).

### Downgrade wallets when

- Repeatedly buying tokens labeled `RUG` or `DEAD_ON_ARRIVAL`.
- Consistently late entry (after the pump has already happened).
- Baiting copy traders (entering early, exiting fast, leaving followers in).
- Winning only in hindsight — the exit liquidity was never there.

---

## Risk mitigations summary

| Risk | Mitigation |
|---|---|
| Blind copy-trading | Wallet signal is candidate discovery only. No auto-trade. |
| Scout-wallet bait | Convergence independence check + post-entry enrichment required. |
| Insider/cabal trap | Cluster detection via Louvain + funding link graph + synchronized exit check. |
| Fake volume | Volume authenticity ratio: unique buyers / (volume / avg trade size). |
| Rug pull | Hard veto: authority checks, Gini/HHI concentration, LP depth, sell quote. |
| MEV/sandwich risk | Execution score penalizes low-liquidity, high-impact routes. Alert-only MVP. |
| Copycat token | Mint address verified; name/ticker similarity alone does not produce signal. |
| Social spam | Novelty score via cosine similarity detects near-duplicate coordinated posts. |
| Overfitting | Backtest by market period; freshness decay on wallet scores; Thompson Sampling. |
