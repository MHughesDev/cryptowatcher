# Data Sources — API Catalog

Every external API used by WIGS v2. Sorted by priority.

---

## Tier 1 — Non-negotiable (system cannot run without these)

### Helius
- **What it provides:** Real-time wallet event webhooks, enhanced transaction parsing
- **Key endpoints:** `POST /webhooks` (register), enhanced TX events (webhook payload), `GET /v0/addresses/{address}/transactions`
- **Auth:** API key in query param or header
- **Free tier:** Available, limited webhook addresses and requests
- **Rate limits:** Varies by plan — monitor via dashboard
- **Key use:** The only reliable real-time source for "wallet X bought token Y"
- **Env var:** `HELIUS_API_KEY`, `HELIUS_WEBHOOK_SECRET`

### Solana RPC (via Helius RPC or public)
- **What it provides:** Raw chain state — token supply, holder list, account data
- **Key endpoints:** `getTokenLargestAccounts`, `getTokenSupply`, `getAccountInfo`, `getSignaturesForAddress`, `getTransaction`
- **Auth:** API key (Helius RPC) or public (rate-limited)
- **Free tier:** Public RPC exists but is heavily rate-limited; use Helius RPC
- **Key use:** Holder distribution, authority status, on-chain supply facts
- **Env var:** `SOLANA_RPC_URL`

### DexScreener
- **What it provides:** DEX market data — price, liquidity, volume, pools, token pairs
- **Key endpoints:** `/tokens/v1/solana/{mint}`, `/token-pairs/v1/solana/{mint}`, `/dex/pairs/solana/{pairAddress}`
- **Auth:** None (public API)
- **Rate limits:** ~300 req/min — use with care in tight loops
- **Key use:** Primary source for market data (price, volume, liquidity, pool age)
- **Env var:** None needed

### Jupiter Quote API
- **What it provides:** Route availability, price impact at exact sell sizes
- **Key endpoints:** `/quote?inputMint=...&outputMint=SOL&amount=X`
- **Auth:** None (public API)
- **Rate limits:** Generous public limits
- **Key use:** Sell route existence, price impact at 0.1/0.5/1/5 SOL sizes
- **Env var:** None needed

---

## Tier 2 — Strongly recommended (significantly improves data quality)

### Birdeye
- **What it provides:** Token security data, wallet PnL, OHLCV, top traders
- **Key endpoints:** `/defi/token_security`, `/defi/token_overview`, `/trader/token-stat`, `/trader/gainers-losers`
- **Auth:** API key in header
- **Free tier:** Limited compute units; ~1 req/sec on free plan
- **Key use:** Mint/freeze authority status, dev holding detection, wallet PnL for wallet tracker scoring
- **Env var:** `BIRDEYE_API_KEY`

### RugCheck
- **What it provides:** Aggregated safety score + specific risk flags per token
- **Key endpoints:** `GET /v1/tokens/{mint}/report`
- **Auth:** None (public beta) or API key for higher limits
- **Rate limits:** Unknown — implement with backoff
- **Key use:** `rugcheck_score`, `rugcheck_risks`, honeypot detection
- **Env var:** `RUGCHECK_API_KEY` (optional)

### GeckoTerminal
- **What it provides:** Independent second opinion on pools, OHLCV, volume
- **Key endpoints:** `/api/public/networks/solana/tokens/{address}/pools`, `/ohlcv`
- **Auth:** None (public)
- **Rate limits:** ~30 calls/min
- **Key use:** Cross-verify DexScreener data, pool age confirmation
- **Env var:** None needed

---

## Tier 3 — Social signals (important but optional to start)

### twikit (Twitter/X unofficial)
- **What it provides:** Tweet search by keyword/cashtag, user metadata (follower count, account age)
- **Auth:** X account username + password (no API key)
- **Status:** Unofficial; uses X's internal API. Can break when X changes endpoints.
- **Key use:** Twitter mention velocity, account age verification, sentiment, bot detection, official account discovery
- **Env var:** `TWITTER_USERNAME`, `TWITTER_PASSWORD`
- **Feature flag:** `ENABLE_TWITTER=true` (default false)

### Reddit Data API
- **What it provides:** Post/comment search in crypto subreddits
- **Key endpoints:** OAuth token → `/r/{subreddit}/search`
- **Auth:** OAuth client credentials
- **Rate limits:** 100 requests/min per client
- **Key use:** Reddit mention count, community discussion volume
- **Env var:** `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`

---

## Tier 4 — Supplemental (add when above sources are stable)

### Cielo Finance
- **What it provides:** Wallet PnL leaderboards, wallet performance scoring
- **Key use:** Source for discovering high-PnL wallets for the wallet tracker
- **Auth:** API key
- **Env var:** `CIELO_API_KEY`

### GMGN
- **What it provides:** On-chain smart money tracking, wallet copy-trade tools
- **Key use:** Alternative source for high-quality wallet discovery
- **Auth:** API key or scraping
- **Env var:** `GMGN_API_KEY`

### Bitquery GraphQL
- **What it provides:** pump.fun launch data, early trade history, bonding curve context
- **Key use:** Confirming pump.fun graduation, early bundle detection
- **Auth:** API key
- **Free tier:** Very limited
- **Env var:** `BITQUERY_API_KEY`

---

## Bundle/snipe detection — on-chain approach (no external API needed)

Bundle detection does not require a paid API. It works by:

1. Fetching the first 20 transactions of a token's life from Helius/Solana RPC
2. Grouping them by block number
3. Within each block: wallets that all buy in the same block with a shared funding source = bundle
4. Funding source trace: follow `getTransaction` backwards to find common origin wallet or CEX withdrawal

This is compute-intensive but accurate and free. Run once at token entry,
refresh every 30 minutes while token is WATCHED.

---

## LP lock detection — on-chain approach

Most LP locks on Solana use Streamflow, Unicrypt, or simple time-locks.

Detection:
1. Fetch LP token holder list (the LP token is itself an SPL token)
2. If a recognized locker program holds LP tokens → LP is locked
3. Read lock account to get unlock timestamp → `lp_lock_duration_days`

Known locker programs to check:
- Streamflow: `strmRqUCoQUgGUan5YhzUZa6KqdzwX5L6FpUxfmKg5m`
- Unicrypt: check their Solana program IDs
- Manual time-lock programs: verify by reading account data

---

## Rate limit management

All API calls go through a central rate limiter. Rules:

- Each API client has a token bucket with its documented limit
- Calls are queued if the bucket is empty
- Exponential backoff on 429 responses (2s, 4s, 8s, max 60s)
- Circuit breaker: if an API fails 5 times in 2 minutes, pause for 10 minutes and log

Priority ordering for data collection (most critical first):
1. Helius webhooks (event-driven, no rate limit concern)
2. Jupiter (sell route check — must have before AI call)
3. Solana RPC (authority status, holder distribution)
4. DexScreener (market data)
5. RugCheck (safety score)
6. Birdeye (enrichment)
7. Social APIs (Twitter, Reddit)
