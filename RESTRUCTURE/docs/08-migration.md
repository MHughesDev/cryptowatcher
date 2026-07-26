# Migration Plan — v1 → v2

## Strategy

Do NOT try to refactor v1 into v2 incrementally. The two systems have
fundamentally different philosophies. The right move is:

1. Keep v1 running as-is (don't break what's working)
2. Build v2 in a clean branch alongside v1
3. Swap when v2 is operational end-to-end

---

## Build order

Build in this exact order. Each phase produces a testable vertical slice.

### Phase 1 — Infrastructure foundation
**Goal:** Database, config, and API skeleton running locally

1. Rewrite `models.py` with the v2 schema (see `07-architecture.md`)
2. Generate and run Alembic migration
3. Update `config.py` with new env vars
4. Update `app.py` to just `GET /health` + `POST /webhook/helius` stub
5. Update `docker-compose.yml` (no changes needed)
6. Update `.env.example` with all new vars

**Done when:** `docker compose up -d && alembic upgrade head && curl /health` works

---

### Phase 2 — API clients
**Goal:** All data sources callable with tested clients

1. Keep all existing clients (helius, solana_rpc, dexscreener, geckoterminal, jupiter, birdeye, reddit, twitter)
2. Add `clients/rugcheck.py` — new
3. Verify each client against live API
4. Write basic smoke tests for each

**Done when:** Every client can be called with real credentials and returns expected data

---

### Phase 3 — Wallet tracker (Subsystem 1)
**Goal:** 24/7 loop running, wallets being added and removed autonomously

1. Build `wallet_tracker/criteria.py` — wallet scoring functions
2. Build `wallet_tracker/discovery.py` — three discovery sources
3. Build `wallet_tracker/health.py` — removal logic
4. Build `wallet_tracker/loops.py` — APScheduler jobs
5. Wire loops into `app.py` startup
6. Seed with 20 manually verified quality wallets to start
7. Test: run for 24h, verify adds/removes make sense

**Done when:** System maintains a live set of tracked wallets with log evidence of decisions

---

### Phase 4 — Data aggregator (Subsystem 3)
**Goal:** Given a token mint, produce a complete TokenDataPacket

1. Build `aggregator/chain.py` — on-chain data (supply, distribution, authorities)
2. Build `aggregator/market.py` — DexScreener + GeckoTerminal + Jupiter
3. Build `aggregator/safety.py` — RugCheck + LP lock + bundle detection
4. Build `aggregator/social.py` — Twitter + Reddit
5. Build `aggregator/wallet_signal.py` — pull from DB
6. Build `aggregator/assembler.py` — combine all → TokenDataPacket
7. Test: manually provide a known token mint, verify the packet looks correct

**Done when:** `assemble_packet(token_mint)` returns a complete, accurate TokenDataPacket

---

### Phase 5 — Token watcher (Subsystem 2)
**Goal:** Helius webhook events create watched tokens and trigger data collection

1. Implement `token_watcher/entry.py` — pre-screen + WATCHED state creation
2. Implement `token_watcher/state.py` — state machine transitions
3. Implement `token_watcher/scheduler.py` — data collection cadence scheduler
4. Wire Helius webhook in `app.py` → entry.py
5. Test: send a simulated wallet buy event, verify token enters WATCHED state

**Done when:** Real wallet events flow in and tokens appear in DB with data snapshots

---

### Phase 6 — AI recommender (Subsystem 4)
**Goal:** Claude evaluates a TokenDataPacket and returns a structured decision

1. Build `ai/guardrails.py` — hard veto functions
2. Build `ai/prompt.py` — system prompt + data packet formatter
3. Build `ai/recommender.py` — Anthropic API call + JSON response parser
4. Build `ai/logger.py` — store evaluation + usage in DB
5. Wire into token watcher: after each data collection, call AI if cadence says so
6. Test: manually trigger evaluation on a known watched token, verify JSON output

**Done when:** Claude returns valid JSON decisions and they're logged to DB

---

### Phase 7 — Slack delivery (Subsystem 5)
**Goal:** RECOMMEND decisions appear in Slack

1. Build `delivery/formatter.py` — message formatting functions (pure, testable)
2. Build `delivery/slack.py` — Slack webhook client
3. Wire into recommender: if decision == RECOMMEND → send Slack message
4. Test: trigger a test RECOMMEND, verify Slack message format is correct

**Done when:** A recommendation appears in #recommendations with the right format

---

### Phase 8 — End-to-end validation
**Goal:** Full pipeline works in production with real data

1. Register Helius webhook pointing at your public URL (or ngrok)
2. Ensure wallet tracker has ≥20 active wallets
3. Monitor for 48 hours
4. Verify at least one token flows through WATCHED → RECOMMENDED → Slack
5. Check AI decision quality against actual token outcome 24h later
6. Tune the system prompt if decisions seem off

**Done when:** Real recommendations arrive in Slack and are defensible

---

## What to do with the old codebase

After v2 is live:

- Archive `src/wigs/algorithms/` — don't delete yet, may want to reference the math
- Archive `src/wigs/alerts.py`
- Archive `src/wigs/workers.py`
- Archive `src/wigs/filters.py`
- Remove Telegram and Discord clients
- Remove GDELT and YouTube clients (not needed in v2)

Keep the `RESTRUCTURE/` folder permanently as documentation.

---

## Risk log

| Risk | Mitigation |
|---|---|
| twikit breaks (X changes internal API) | `ENABLE_TWITTER=false` by default; system works without it |
| Claude returns malformed JSON | Retry up to 3 times; fallback to WATCH if all fail |
| Helius webhook misses events | Periodic catch-up scan every 10 minutes via `getSignaturesForAddress` |
| Too many tokens in WATCHED state at once | Cap at 50 simultaneously watched tokens; new entries queue |
| AI cost runaway | Daily budget alert via Anthropic dashboard; hard circuit breaker in code |
| Bundle detection false positives | Log all detections; manually verify first 10 to calibrate |
| Wallet set degrades (too aggressive removal) | Monitor set size daily; alert via Slack system log if <20 wallets |
