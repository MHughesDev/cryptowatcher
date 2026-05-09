# Wallet Engine

## Why wallet-led

Most new memecoins die. Scanning every token launch first produces too much noise.

The system tracks **wallet behavior** instead. High-quality wallet activity is the discovery layer. A candidate token only enters the system after a watched wallet, watched cluster, or discovered scout wallet interacts with it.

---

## Phase 1 — Wallet Universe Builder

### Purpose

Find wallets worth tracking before live event ingestion begins.

### Seed sources

- Known whale wallets.
- Known smart-money wallets.
- Early buyers of historical winner tokens.
- Wallets that bought before major liquidity expansion events.
- Wallets that bought before social trend expansion.
- Wallets that repeatedly appear before KOL calls.
- Wallets that repeatedly enter tokens that survive more than one pump.

### Quality metrics

| Metric | Meaning |
|---|---|
| `realized_pnl_score` | Profit from completed trades, not unrealized wallet-mark values. |
| `early_entry_score` | How early the wallet enters relative to pool creation, first 100 holders, first liquidity jump, or first social breakout. |
| `lead_lag_score` | Whether the wallet enters before whales, KOLs, liquidity expansion, or social velocity. |
| `exit_quality_score` | Whether the wallet exits before major drawdowns rather than after them. |
| `rug_avoidance_score` | Whether the wallet avoids tokens later labeled as rugs or dead-on-arrival. |
| `repeatability_score` | Whether returns come from many trades, not one lucky outlier. |
| `independence_score` | Whether the wallet is not merely a duplicate of another tracked cluster. |
| `freshness_score` | Whether the wallet has performed well recently, not only months ago. |

### Wallet quality formula

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

- Most profit came from a single trade.
- Wallet frequently buys honeypots or dead-on-arrival launches.
- Wallet is profitable only because it is an insider wallet that dumps on retail.
- Wallet enters after the pump, not before it.
- Wallet usually exits before followers can realistically enter.
- Wallet has extreme copy-trader crowding.
- Wallet is part of a cluster that creates fake volume.

---

## Phase 2 — Lead-Lag Wallet Graph

### Purpose

Find wallets that *predict* other wallets or market events.

This is the pre-whale strategy formalized. Copying a whale directly is often too late. The better signal is usually a smaller wallet or cluster that moves before the whale.

### Graph nodes

- Wallets
- Token mints
- DEX pools
- Creator wallets
- Social mentions
- KOL channels
- News/trend entities
- Outcomes

### Graph edges

| Edge | Meaning |
|---|---|
| `WALLET_BOUGHT_TOKEN` | Wallet bought a token. |
| `WALLET_SOLD_TOKEN` | Wallet sold a token. |
| `WALLET_FUNDED_WALLET` | One wallet funded another wallet. |
| `WALLET_PRECEDES_WALLET` | Wallet A commonly enters before Wallet B. |
| `WALLET_PRECEDES_TREND` | Wallet enters before social velocity expands. |
| `TOKEN_HAS_POOL` | Token trades on a pool. |
| `TOKEN_HAS_SOCIAL_MENTION` | Token/ticker/mint appears in social data. |
| `TOKEN_LABELED_OUTCOME` | Token was later labeled as rug, dead, survivor, or runner. |

### Lead-lag score formula

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

### Cluster detection signals

| Signal | Method |
|---|---|
| Funding links | Wallet A sent SOL to Wallet B before activity. |
| Co-entry | Wallets repeatedly buy the same token within a short window. |
| Co-exit | Wallets repeatedly sell into the same window. |
| Timing similarity | Entry/exit time distributions are statistically similar. |

Cluster membership suppresses `independence_score` for all wallets in the cluster. A cluster that looks like a cabal or bot farm is penalized as a unit.

---

## Wallet lifecycle

```text
DISCOVERED → ACTIVE → DEGRADED → RETIRED
```

- **DISCOVERED** — in the seed set or found via historical replay.
- **ACTIVE** — being monitored via Helius webhooks.
- **DEGRADED** — score has dropped; still watched but lower trust weight.
- **RETIRED** — wallet is no longer monitored; kept in history for outcome attribution.

Wallet scores are refreshed every 6 hours. Wallet quality drift is tracked over time so a wallet that was excellent six months ago but mediocre recently can be caught early.
