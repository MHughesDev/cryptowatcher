# Subsystem 2 — Token Watcher

## Purpose

Convert tracked-wallet buy events into watched tokens, manage each token's
lifecycle, and trigger data collection and AI evaluation at the right moments.

A token becomes WATCHED the instant any tracked wallet buys it. The token
watcher then orchestrates what happens next: data collection, AI calls,
and eventual RECOMMENDED or EXPIRED outcome.

---

## Entry — how tokens enter the watch list

A token enters WATCHED state when:
- A tracked wallet (from Subsystem 1) buys it, AND
- It passes the hard pre-screen (below)

### Hard pre-screen (code-level, no AI involved)

These checks run immediately on entry. Any failure → token is silently skipped.
These are minimum existence checks, not quality filters — quality is Claude's job.

| Check | Fail condition |
|---|---|
| Sell route exists | Jupiter returns no route at any size |
| LP exists | No liquidity pool found on any DEX |
| Mint authority | Still active (rug risk, non-negotiable) |
| Freeze authority | Still active (rug risk, non-negotiable) |
| Not a known stablecoin/wrapped asset | SOL, USDC, USDT, wSOL |
| Token age | Older than 7 days (signal is stale) |
| Token age | Younger than 30 seconds (too fresh, data unavailable) |

Tokens that fail the pre-screen are logged as SKIPPED with reason.
They are never surfaced again unless the wallet tracker processes a separate event.

---

## Token lifecycle (state machine)

```
              [wallet buys]
                    │
                    ▼
             ┌──────────────┐
             │   PRE-SCREEN │  (hard safety checks — code only)
             └──────┬───────┘
                    │ passes            fails
                    ▼                    ▼
             ┌──────────────┐      ┌──────────┐
             │   WATCHED    │      │  SKIPPED │
             └──────┬───────┘      └──────────┘
                    │
        [data collection begins, AI evaluated]
                    │
            ┌───────┴───────┐
            │               │
      AI: RECOMMEND     AI: WATCH
            │               │
            ▼               │
     ┌─────────────┐        │
     │ RECOMMENDED │        │ [continues collecting]
     └─────────────┘        │
                            │
                    [after 7 days or
                     AI: PASS or
                     liquidity collapse]
                            │
                            ▼
                     ┌──────────┐
                     │  EXPIRED │
                     └──────────┘
```

---

## Signals that elevate a token's priority

The more tracked wallets buy a token, and the tighter their timing, the more
urgently Claude should be called and the more prominently it should appear
in Claude's context.

| Wallet count | Timing spread | Priority |
|---|---|---|
| 1 wallet | any | STANDARD — collect data, evaluate next cycle |
| 2 wallets | > 30 min apart | STANDARD |
| 2 wallets | < 30 min apart | ELEVATED — trigger immediate AI call |
| 3+ wallets | < 10 min apart | URGENT — immediate AI call, surface prominently |

Priority affects how quickly the AI is called, not what the AI decides.

---

## Data collection cadence

Once a token is WATCHED, data is pulled on this schedule:

| Time since first buy | Collection interval | Reason |
|---|---|---|
| 0 – 30 minutes | Every 1 minute | Fastest-moving phase; price/holders change rapidly |
| 30 min – 2 hours | Every 5 minutes | Still active but slowing |
| 2 – 6 hours | Every 15 minutes | Maturation phase |
| 6 – 24 hours | Every 30 minutes | Monitoring for continuation or collapse |
| 1 – 7 days | Every 2 hours | Long-tail monitoring |

Data collection stops when the token reaches RECOMMENDED or EXPIRED.

---

## AI evaluation schedule

Claude is called to evaluate watched tokens on this schedule:

| Trigger | When |
|---|---|
| First evaluation | After first complete data snapshot (t+60s to t+90s after entry) |
| Priority escalation | Immediately when a second wallet buys within 30 min |
| Routine re-evaluation | Every 30 minutes while in WATCHED/ACTIVE state |
| Force evaluation | When any tracked wallet sells the token (may indicate exit signal) |

Each AI evaluation receives the LATEST data snapshot plus the full history
of previous evaluations and their reasoning. This gives Claude context on
how the token has evolved.

---

## Token data model

```python
WatchedToken:
    token_mint: str              # Solana SPL mint address
    symbol: str | None
    name: str | None
    status: enum                 # WATCHED | ACTIVE | RECOMMENDED | EXPIRED | SKIPPED
    priority: enum               # STANDARD | ELEVATED | URGENT
    
    first_seen_at: datetime      # when first tracked wallet bought
    first_buyer_wallet: str      # which wallet triggered the watch
    
    # Wallet signal
    buying_wallet_count: int         # distinct tracked wallets that bought
    buying_wallet_addresses: list    # which ones
    first_buy_mc_usd: float | None   # market cap when first tracked wallet bought
    buy_time_spread_seconds: float   # spread between first and last tracked wallet buy
    
    # Lifecycle
    last_data_collected_at: datetime
    last_ai_evaluated_at: datetime | None
    ai_evaluation_count: int
    
    # Outcome
    recommended_at: datetime | None
    expired_at: datetime | None
    expiry_reason: str | None        # PASS | LIQUIDITY_COLLAPSE | TIMEOUT | HARD_VETO
```

---

## Automatic expiry conditions

A token is moved to EXPIRED without AI involvement when:

| Condition | Action |
|---|---|
| Liquidity drops below $3,000 USD | EXPIRED — LIQUIDITY_COLLAPSE |
| 7 days since first wallet buy | EXPIRED — TIMEOUT |
| Mint or freeze authority activated after entry | EXPIRED — HARD_VETO (flag as suspicious) |
| Token is flagged as honeypot by RugCheck | EXPIRED — HARD_VETO |

---

## What this subsystem does NOT do

- Does not decide if a token is good or bad (Claude does that)
- Does not pull data itself (Data Aggregator does that)
- Does not manage wallet quality (Wallet Tracker does that)
- Does not send Slack messages (Slack Delivery does that)

It only manages state transitions and triggers the right jobs at the right time.
