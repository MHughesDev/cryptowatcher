# Subsystem 1 — Wallet Tracker

## Purpose

Maintain a live, curated set of high-quality Solana wallets whose on-chain
behavior is worth watching. When these wallets buy a token, that is a signal.
The quality of that signal depends entirely on the quality of this wallet set.

This subsystem runs 24/7 and is completely independent. Nothing else in the
system can add or remove wallets. The wallet tracker is the sole authority.

---

## What makes a quality wallet

A quality wallet is a retail-sized smart-money trader with a verifiable track
record of finding winning tokens early, before price moves significantly.

### Must satisfy ALL of the following to be added

**1. Verified PnL track record**
- Realized PnL (not paper gains) of at least **5x average** across last 30 days
- Minimum **N=5 distinct qualifying token plays** in that period
- A "qualifying play" is: bought within first 20% of holders AND token 2x'd within 48h
- Win rate: at least 40% of plays must be qualifying

**2. Retail trade size (not a whale)**
- Max single trade size: **≤ $15,000 USD notional**
- Average trade size: **≤ $5,000 USD notional**
- Rationale: whales move price. We want wallets that find tokens BEFORE whales arrive.

**3. Recency**
- At least one qualifying buy in the **last 14 days**
- Prevents tracking dormant wallets that got lucky once

**4. Early entry pattern**
- Must be in the **top 15% of buyers by time** across at least 60% of qualifying plays
- A wallet that gets in early consistently is a signal; one that follows the crowd is noise

**5. Source independence**
- Funding source must NOT match more than 2 other tracked wallets
- Prevents tracking a coordinated cluster as if they are independent signals
- Checked via on-chain funding trace (CEX withdrawal address, bridge, etc.)

**6. Clean history**
- Must NOT be a known sniper bot (regular buys in block 1-3 of token launch)
- Must NOT have funded known rug developer wallets
- Must NOT show copy-trading signatures (identical buys to known bot clusters within same block)

---

## Criteria for removal

A wallet is removed when ANY of the following triggers:

| Trigger | Threshold | Rationale |
|---|---|---|
| Rolling 30-day win rate drops | Below 25% | Wallet has lost its edge |
| Trade size grows | Any single trade > $50k | Has become a whale — ruins signal |
| Inactive | No buys in 21 days | Signal source has gone dark |
| Coordinated pattern detected | Matches cluster behavior | No longer independent signal |
| Rug participation rate | >30% of plays are rugs | Wallet is compromised or malicious |
| PnL reverses | 30-day realized PnL negative | Lost its edge |

Removal is logged with reason. Wallets can be re-added if they recover.

---

## How new wallets are discovered

### Source 1 — Historical winner backtracing (primary)
- Take tokens that had strong outcomes (2x+ within 24h, $50k+ liquidity at peak)
- Find wallets that bought in the first 15% of holders on those tokens
- Score those wallets against all criteria above
- Add qualifying ones

### Source 2 — Peer network expansion
- For each currently tracked wallet, find OTHER wallets that frequently co-buy the
  same early tokens (without being the same cluster)
- Filter those through the same criteria
- This finds wallets that run in similar circles but are genuinely independent

### Source 3 — On-chain PnL leaderboards
- Birdeye, Cielo, and Solana on-chain tools publish top-performer wallet lists
- Pull these periodically, run them through criteria scoring
- Only add if they pass all gates (many leaderboard wallets are whales or bots)

### Source 4 — Social cross-reference
- When a KOL with a verified track record makes a call, find wallets that
  consistently bought the same token BEFORE that KOL called it
- These "KOL-precall" wallets have a demonstrable information edge

---

## Loop design

The wallet tracker runs three concurrent loops. These are independent jobs.

### Loop A — Discovery scan (every 6 hours)
```
1. Pull recent winning tokens (last 6h with >2x and >$30k liquidity peak)
2. For each: fetch early buyer list from Helius/Solana RPC
3. Score each buyer wallet against all criteria
4. Add qualifying wallets to tracked_wallets
5. Log discovery reason and score breakdown
```

### Loop B — Health check (every 1 hour)
```
1. Pull all active tracked wallets
2. For each: check removal triggers (recency, trade size, win rate, coordination)
3. Any wallet hitting a trigger → mark RETIRING
4. After 3 consecutive RETIRING marks → mark REMOVED
5. Log removal reason
```

### Loop C — Real-time event ingestion (continuous via Helius webhooks)
```
1. Receive buy event for tracked wallet
2. Update wallet stats (trade count, trade size, last active)
3. Record event for health check calculations
4. Pass event to Token Watcher (Subsystem 2)
```

---

## Wallet data model

```python
TrackedWallet:
    wallet_address: str          # Solana public key
    status: enum                 # ACTIVE | RETIRING | REMOVED
    added_at: datetime
    added_reason: str            # human-readable why this wallet was added
    source: enum                 # HISTORICAL_WINNER | PEER_NETWORK | LEADERBOARD | KOL_PRECALL
    
    # Performance metrics (updated by health check)
    trade_count_30d: int
    qualifying_plays_30d: int
    win_rate_30d: float          # 0.0 - 1.0
    realized_pnl_30d_usd: float
    avg_trade_size_usd: float
    max_trade_size_usd: float
    last_active_at: datetime
    
    # Removal tracking
    retiring_since: datetime | None
    removed_at: datetime | None
    removed_reason: str | None
```

---

## Wallet set size guidance

- **Minimum viable set**: 20 wallets (below this, convergence signals are too rare)
- **Sweet spot**: 50–150 wallets
- **Maximum recommended**: 300 wallets (above this, noise increases significantly)

Quality over quantity. 30 excellent wallets beat 200 mediocre ones.

---

## What this subsystem does NOT do

- Does not score tokens
- Does not call the AI
- Does not send Slack messages
- Does not care about social data

It only tracks wallets and maintains their quality state.
