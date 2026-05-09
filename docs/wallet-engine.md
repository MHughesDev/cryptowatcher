# Wallet Engine

## Why wallet-led

Most new memecoins die. Scanning every token launch first produces too much noise.

The system tracks **wallet behavior** instead. High-quality wallet activity is the discovery layer. A candidate token only enters the system after a watched wallet, watched cluster, or discovered scout wallet interacts with it.

---

## Phase 1 — Wallet Universe Builder

### Purpose

Build and rank a set of wallets worth monitoring before live event ingestion begins.

### Seed sources

| Source | Method |
|---|---|
| Historical winner early buyers | Find wallets in the first 50 holders of tokens that became `TRADEABLE_RUNNER` or `HEAVY_HITTER`. |
| Pre-whale wallets | Find wallets that repeatedly buy the same token 5–60 minutes before a known whale wallet. |
| KOL pre-call wallets | Find wallets that buy a token 5–120 minutes before a public influencer posts about it. |
| Recurring survivors | Find wallets that appear in the early holder set of tokens that survived multiple liquidity cycles. |

### Wallet quality scoring

Eight sub-scores, each normalized 0–100.

#### `realized_pnl_score`

Profit from **closed** positions only. Unrealized marks are excluded — they don't prove exit liquidity existed.

```
realized_pnl_score = normalize(
    Σ tradable_return_per_trade / total_trades
    weighted by recency_decay(trade_date)
)
```

Where `tradable_return = estimated_sell_output_after_slippage_and_price_impact`, not raw price.

#### `early_entry_score`

Measures how early a wallet enters relative to the token's lifecycle events:

```
entry_percentile = rank_of_wallet_among_first_N_buyers / N

early_entry_score = normalize(1 - entry_percentile)
                  * liquidity_event_lead_bonus
                  * social_event_lead_bonus
```

- `liquidity_event_lead_bonus` > 1 if wallet entered before a major LP expansion.
- `social_event_lead_bonus` > 1 if wallet entered before measurable social velocity.

#### `lead_lag_score`

Full formula in the Lead-Lag section below.

#### `exit_quality_score`

Measures whether the wallet exits before major drawdowns.

```
exit_quality_score = normalize(
    Σ (drawdown_avoided_pct * position_size_weight)
)
```

- `drawdown_avoided_pct` = how much of the eventual peak-to-trough drop was avoided by the wallet's exit.
- Penalized if the wallet exits into zero liquidity (exits don't count as quality exits if price impact was >15%).

#### `rug_avoidance_score`

```
rug_avoidance_score = normalize(
    (rug_free_trades / total_trades)
    * (1 - avg_exposure_to_rugs)
)
```

Wallets that accidentally buy rugs but exit before collapse are partially credited.

#### `repeatability_score`

Shannon entropy of per-trade returns, normalized:

```
H = -Σ p(bucket) * log₂(p(bucket))
repeatability_score = normalize(H)
```

Higher entropy = wins spread across many trades, not concentrated in one outlier.

#### `independence_score`

Penalizes wallets that move in lock-step with other tracked wallets (potential cluster members).

```
independence_score = 1 - avg_cosine_similarity(wallet_buys, cluster_member_buys)
```

Cosine similarity computed over a binary buy-vector across the token universe.

#### `freshness_score`

Decaying weight on recency. A wallet that performed well 6 months ago but poorly recently should not be treated as high quality.

```
freshness_score = normalize(
    Σ (weekly_pnl_score[w] * exp(-λ * weeks_ago[w]))
)
```

λ = 0.1 (default decay constant — tune per market regime).

### Composite wallet quality formula

```
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

Weights are initial defaults. They should be updated via Bayesian inference as outcome data accumulates (see `docs/candidate-scoring.md` — Outcome Feedback Loop).

### Wallet rejection rules

Hard-reject or zero out wallets if:

- Most profit came from a single trade (repeatability_score < 10).
- Wallet is clearly an insider that dumps on retail (exits within first 2 minutes of every position).
- `independence_score` is near zero — wallet is simply mirroring another tracked wallet.
- Wallet's `realized_pnl_score` only looks good because of one token that is now labeled `HEAVY_HITTER` — the rest of its trades were rugs.

---

## Phase 2 — Lead-Lag Detection

### Purpose

Find wallets that **predict** other wallets or market events — not wallets that merely correlate with them after the fact.

The core insight: copying a known whale directly is often too slow. The better signal is the smaller wallet or cluster that consistently moves *before* the whale.

### Cross-correlation approach

For each wallet pair (A, B), compute a rolling cross-correlation between their buy-event time series over a lookback window W:

```
CCF(τ) = corr(buys_A(t), buys_B(t + τ))    for τ ∈ [-T, +T]
```

- If CCF peaks at τ < 0, wallet A leads wallet B.
- The lag value τ* = argmax CCF(τ) is the Lead-Lag Time (LLT).
- The magnitude at the peak is the Lead-Lag Correlation (LLC).
- The Lead-Lag Ratio (LLR) = LLC(τ<0) / LLC(τ>0) summarizes directionality.

### Granger causality test

For wallet pairs with strong cross-correlation, confirm with a Granger causality test:

1. Fit a VAR(p) model using only lagged values of B to predict B's buy events.
2. Fit a VAR(p) model using lagged values of both A and B to predict B's buy events.
3. Apply an F-test. If the inclusion of A's lags significantly improves the model, A Granger-causes B.

Use p = 4 lags (minutes or block intervals) for Solana's ~400ms block time.

**Important:** Granger causality is not true causality — it is predictive precedence. It is sufficient for this system's purpose.

### Lead-lag score formula

```
lead_lag_score(wallet_a, event_b) =
    P(event_b happens within T after wallet_a entry)   [empirical from history]
  * median_tradable_return_after_wallet_a_entry
  * exit_liquidity_success_rate_of_followers
  * independence_multiplier                            [penalize if A is in a cluster]
  * freshness_multiplier                               [recent windows weighted higher]
  * confidence_factor(sample_size)                     [shrink score if N < 30 samples]
  - rug_follow_penalty                                 [penalize if A precedes rugs]
  - crowding_penalty                                   [penalize if A's signal is now widely copied]
```

T is configurable per wallet type — for scout wallets, T = 30 minutes; for known KOL-precall wallets, T = 2 hours.

### Lead-lag graph edges

| Edge | Meaning |
|---|---|
| `WALLET_PRECEDES_WALLET` | A consistently enters before B, validated by CCF and Granger test. |
| `WALLET_PRECEDES_TREND` | A enters before measurable social velocity on the token. |
| `WALLET_PRECEDES_LIQUIDITY_EXPANSION` | A enters before a significant LP event on the token. |
| `WALLET_PRECEDES_WHALE` | A enters before a known large wallet. |

---

## Phase 3 — Wallet Cluster Detection

### Purpose

Identify coordinated wallet groups (cabals, bot farms, insider clusters, dev networks) so their collective activity is counted as one signal rather than many independent ones.

### Graph construction

Build a **bipartite co-purchase graph**:

- **Nodes**: All tracked wallets + all token mints they have ever bought.
- **Edges**: `wallet → token` with weight = `amount_usd * recency_weight`.

Project to a **wallet-wallet graph**:

- Two wallets are connected if they co-purchased the same tokens.
- Edge weight = number of co-purchases, adjusted for timing tightness.

### Louvain community detection

Apply the **Louvain algorithm** to the wallet-wallet graph:

1. **Phase 1** — Assign each wallet to its own community. For each wallet, test moving it to each neighbor's community and compute the modularity gain:
   ```
   ΔQ = [Σ_in + 2k_i_in] / [2m] - [(Σ_tot + k_i) / (2m)]²
      - [Σ_in / 2m] - [Σ_tot / (2m)]² - [k_i / (2m)]²
   ```
   Move the wallet to the community yielding the highest ΔQ > 0. Repeat until no improvement.

2. **Phase 2** — Aggregate communities into single super-nodes. Rebuild the graph. Repeat Phase 1.

3. Stop when modularity Q converges (typically Q > 0.4 suggests meaningful community structure).

Use the **Leiden algorithm** for better-connected results if Louvain produces disconnected communities.

### Cluster suspicion scoring

After community detection, score each cluster's suspicion level:

| Signal | Weight |
|---|---|
| Tight buy timing (median inter-wallet delta < 10 seconds) | 0.30 |
| Shared funding source (common ancestor wallet) | 0.25 |
| High co-purchase rate across many different tokens | 0.20 |
| Synchronized exits (sells within same 30-second window) | 0.15 |
| Low linguistic diversity in associated social accounts | 0.10 |

```
cluster_suspicion =
    0.30 * timing_tightness_score
  + 0.25 * shared_funding_score
  + 0.20 * co_purchase_rate_score
  + 0.15 * synchronized_exit_score
  + 0.10 * social_diversity_score
```

Clusters with suspicion > 0.70 are labeled `CABAL_SUSPECT` or `BOT_FARM`. All members in a suspected cluster share a single vote in convergence scoring.

### Cluster types

| Type | Pattern |
|---|---|
| `SMART_MONEY` | Independent wallets converging — positive signal. |
| `CABAL_SUSPECT` | Tight timing + shared funding. Counts as 1 vote. |
| `DEV_SUSPECT` | Cluster includes creator wallet or early pre-launch funding. |
| `BOT_FARM` | High buy frequency, many tokens, near-zero exit slippage. |
| `KOL_SUSPECT` | Buys happen within seconds of KOL posts — may be front-running. |

---

## Wallet lifecycle

```
DISCOVERED → ACTIVE → DEGRADED → RETIRED
```

| State | Condition |
|---|---|
| DISCOVERED | Added to seed set or found via historical replay. |
| ACTIVE | Being monitored via Helius webhooks. Quality score ≥ 50. |
| DEGRADED | Quality score dropped to 25–49. Still watched but weighted lower. |
| RETIRED | Quality score < 25 or no relevant activity in 30 days. Kept in history for outcome attribution. |

Wallet scores are refreshed every 6 hours. The `freshness_score` sub-component captures drift automatically — a wallet that was excellent 6 months ago but poor recently converges toward DEGRADED without manual intervention.
