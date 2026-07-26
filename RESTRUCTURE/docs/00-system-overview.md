# System Overview — WIGS v2

## Architecture diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     SUBSYSTEM 1: WALLET TRACKER                     │
│  24/7 autonomous loop — completely independent from everything else  │
│                                                                     │
│  Discovery (6h) ──► Candidate wallets                               │
│  Health check (1h) ──► Remove failing wallets                       │
│  Webhook events (real-time) ──► Update wallet stats                 │
│                                                                     │
│  Output: tracked_wallets table (active set of quality wallets)      │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ "wallet bought token X"
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     SUBSYSTEM 2: TOKEN WATCHER                      │
│  Any tracked wallet buy → token becomes WATCHED                     │
│                                                                     │
│  Entry gate: passes hard safety pre-screen?                         │
│  State machine: WATCHED → ACTIVE → RECOMMENDED or EXPIRED           │
│  Data collection: aggressive (1m) → cooling (5m) → maintenance (30m)│
│                                                                     │
│  Output: watched_tokens table with full data snapshots              │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ "token data snapshot ready"
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   SUBSYSTEM 3: DATA AGGREGATOR                      │
│  Pulls from: Helius, Solana RPC, DexScreener, Birdeye,             │
│             GeckoTerminal, Jupiter, RugCheck, Twitter,              │
│             Reddit, on-chain bundle/snipe detection                 │
│                                                                     │
│  Assembles: structured TokenDataPacket for AI consumption           │
│  Stored: per-snapshot in DB; latest always queryable               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ TokenDataPacket
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SUBSYSTEM 4: AI RECOMMENDER                      │
│  Model: Claude claude-sonnet-4-6 (Anthropic API)                           │
│  Role: reason about data, decide RECOMMEND / WATCH / PASS           │
│                                                                     │
│  Guardrails checked BEFORE calling Claude (code-level hard vetoes)  │
│  Claude receives: full TokenDataPacket + system prompt              │
│  Claude outputs: structured JSON decision + Slack message           │
│  All decisions logged with full reasoning                           │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ RECOMMEND
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   SUBSYSTEM 5: SLACK DELIVERY                       │
│  Formats recommendation message                                     │
│  Posts to #recommendations channel                                  │
│  Includes: token, CA, MC, why, risks, wallet count, confidence      │
└─────────────────────────────────────────────────────────────────────┘
```

## Subsystem responsibilities

### Subsystem 1 — Wallet Tracker
- Maintains the active set of quality wallets the system watches
- Runs completely independently; no other subsystem should modify wallet state
- See `01-wallet-tracker.md`

### Subsystem 2 — Token Watcher
- Converts wallet buy events into watched tokens
- Manages token lifecycle (WATCHED → ACTIVE → RECOMMENDED / EXPIRED)
- Triggers data collection and AI evaluation at the right moments
- See `02-token-watcher.md`

### Subsystem 3 — Data Aggregator
- Responsible for collecting, refreshing, and storing all token data
- Assembles the TokenDataPacket that Claude receives
- Never makes decisions — only collects data
- See `03-data-aggregation.md`

### Subsystem 4 — AI Recommender
- The only decision-maker in the system
- Called after hard guardrails pass (code enforces non-negotiables)
- Uses Claude claude-sonnet-4-6 via Anthropic API with prompt caching
- Logs every decision and reasoning permanently
- See `04-ai-recommender.md`

### Subsystem 5 — Slack Delivery
- Sends Claude's formatted recommendation to Slack
- Only fires on RECOMMEND decisions
- See `05-slack-delivery.md`

## Key design principles

**AI decides, code enforces safety.**
Hard vetoes (mint authority active, no LP lock, dev holding >25%) are caught in
code before Claude is ever called. Claude handles judgment calls, not safety
checks. This means guardrail violations never cost an API call.

**Wallet tracking is its own world.**
No other subsystem adds or removes wallets. The wallet tracker is the only
authority. This prevents feedback loops, data corruption, and coupling bugs.

**Every decision is explainable.**
Claude's reasoning is stored alongside every RECOMMEND, WATCH, and PASS
decision. You can always answer "why did the system recommend this token?"

**Data freshness is the product.**
If the data aggregator is stale, the AI makes bad decisions. Freshness SLAs
are defined per data type and enforced with monitoring.

**One output channel.**
All recommendations go to Slack. No Telegram, Discord, or email. Simple,
auditable, one place to check.

## Data flow timing

```
Wallet buys token
       │
       ├─ t+0s:   Event received via Helius webhook
       ├─ t+5s:   Hard safety pre-screen runs (code)
       ├─ t+10s:  Token enters WATCHED state, data collection begins
       ├─ t+60s:  First full data snapshot assembled
       ├─ t+90s:  AI called for first evaluation
       │
       │  If WATCH decision → continue collecting
       │
       ├─ t+5m:   Second snapshot + AI evaluation
       ├─ t+15m:  Third snapshot + AI evaluation
       └─ t+30m+: Every 30m until RECOMMENDED, PASS, or 7-day expiry
```

## What v2 is NOT

- Not an auto-trader. Never opens a position.
- Not a price predictor. Claude reasons about signals, not prices.
- Not a replacement for your own due diligence. It's a recommendation engine.
- Not real-time chat. Slack notifications are one-way.
