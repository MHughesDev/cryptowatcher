# WIGS — Wallet Intelligence Graph Scanner

A wallet-led Solana memecoin intelligence system.

> Do not scan every memecoin first. Track the wallets first. Let high-signal wallet movement nominate candidate token mints, then verify those mints through market, liquidity, safety, and social evidence.

## System objective

Find **watchlist-grade Solana memecoins** by combining:

1. **Wallet evidence** — scout wallets, pre-whale wallets, smart-money wallets, KOL-precall wallets, dev-adjacent wallets, and wallet clusters.
2. **Market evidence** — price, liquidity, volume, DEX pool age, route quality, spread, volatility, and sell quote realism.
3. **Safety evidence** — holder concentration, mint/freeze authority, creator activity, suspicious clusters, sellability, and rug-risk rules.
4. **Social evidence** — Reddit, Telegram, Discord, YouTube, GDELT/news, and mention velocity across community, ticker, and mint-address dimensions.
5. **Historical feedback** — every alert is replayed later to measure whether the wallet signal actually produced tradable upside.

## Output

Canonical API enum values:

```text
AVOID
WATCH
STRONG_WATCH
STRONG_CANDIDATE
```

Display labels may be presented with spaces (for example, `STRONG WATCH`) in human-facing UIs/messages.

This is an alert and ranking engine, not an auto-trader. No positions are opened automatically.

## Getting Started

### Prerequisites

- Python 3.12+
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for PostgreSQL + Redis)
- [ngrok](https://ngrok.com/) or a public URL (for receiving Helius webhooks locally)
- A [Helius](https://helius.dev/) account (free tier is sufficient to start)

---

### 1. Clone and install

```bash
git clone <repo-url>
cd cryptowatcher
pip install -e ".[dev]"
```

---

### 2. Configure environment

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

Open `.env` and fill in at minimum:

| Variable | Where to get it |
|---|---|
| `HELIUS_API_KEY` | [helius.dev](https://helius.dev/) → Dashboard → API Keys |
| `HELIUS_WEBHOOK_SECRET` | Any random string you generate; paste the same value in the Helius webhook settings |
| `BIRDEYE_API_KEY` | [birdeye.so](https://birdeye.so/) → Developer → API Keys (free tier available) |
| `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` | [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) → create a "script" app |
| `REDDIT_USER_AGENT` | Any descriptive string, e.g. `wigs/0.1 by /u/youruser` |
| `YOUTUBE_API_KEY` | [Google Cloud Console](https://console.cloud.google.com/) → APIs → YouTube Data API v3 |
| `TELEGRAM_BOT_TOKEN` | Telegram [@BotFather](https://t.me/BotFather) → `/newbot` |
| `TELEGRAM_ALERT_CHAT_ID` | The chat ID of the channel/group where alerts will be posted |
| `DISCORD_ALERT_WEBHOOK_URL` | Discord channel settings → Integrations → Webhooks → New Webhook |

The following have no API key — they work out of the box:
- **DexScreener**, **GeckoTerminal**, **Jupiter** — keyless public APIs
- **GDELT** — open data, no key needed

Optional sources (leave blank to disable):
- `BITQUERY_API_KEY` — Pump.fun context ([bitquery.io](https://bitquery.io/))
- `TWITTER_USERNAME` + `TWITTER_PASSWORD` — unofficial X/Twitter social scanning via `twikit` (see note below)

---

### 3. Start infrastructure

Start Docker Desktop, then run:

```bash
docker compose up -d
```

This spins up PostgreSQL and Redis. Confirm they're running:

```bash
docker compose ps
```

Apply the database schema:

```bash
alembic upgrade head
```

---

### 4. Seed wallets

Insert at least 10–20 known high-quality Solana wallet addresses into the `tracked_wallets` table. These are the wallets the system watches — everything flows from their on-chain activity.

```sql
INSERT INTO tracked_wallets (address, label, quality_score, is_active)
VALUES ('WALLET_ADDRESS_HERE', 'known-smart-money', 75, true);
```

Finding good seed wallets: look at the top traders on [Birdeye](https://birdeye.so/leaderboard) or wallets that were early on past winning Solana memecoins.

---

### 5. Register the Helius webhook

Start the app:

```bash
uvicorn wigs.app:app --reload --port 8000
```

For local development, expose it with ngrok:

```bash
ngrok http 8000
```

In the [Helius dashboard](https://dev.helius.xyz/dashboard/app), create a webhook:
- **URL**: `https://<your-ngrok-subdomain>.ngrok.io/webhook/helius`
- **Auth header / secret**: the same value you set for `HELIUS_WEBHOOK_SECRET`
- **Address list**: the wallet addresses you seeded in step 4
- **Transaction types**: `SWAP`

---

### 6. Verify it's working

```bash
# Health check
curl http://localhost:8000/health

# Watch logs for incoming events
uvicorn wigs.app:app --reload --log-level debug
```

Once a tracked wallet makes a swap on-chain, you should see the event flow through the pipeline and — if the token scores high enough — an alert posted to Telegram or Discord.

---

### Minimal setup (no social APIs)

To run with only on-chain data and skip all social scoring:

```env
ENABLE_SOCIAL_SCORING=false
ENABLE_GDELT=false
ENABLE_YOUTUBE=false
ENABLE_TWITTER=false
```

This disables Reddit, YouTube, Telegram channel scanning, GDELT, and Twitter — the system will still score tokens using wallet evidence, market data, safety checks, and execution quality.

---

### Twitter / X social scanning (optional)

The official X API no longer has a usable free tier. WIGS uses [`twikit`](https://github.com/d60/twikit), an unofficial client that requires no API key — just an X account username and password.

```env
TWITTER_USERNAME=your_x_username
TWITTER_PASSWORD=your_x_password
ENABLE_TWITTER=true
```

> **Note:** `twikit` uses X's internal API and is not officially supported. It may break without notice if X changes their internal endpoints. It is disabled by default (`ENABLE_TWITTER=false`). Use it for signal enrichment only — never as the sole source of truth for a scoring decision.
>
> Mentions are not filtered by account age or follower count at the collection level — all mentions within the time window are returned. The scorer weights them: a post from a 3-year-old account with 50k followers counts more than one from a day-old account with 2 followers, but both are included. This matters because many meme coins originate from brand-new throwaway accounts or small niche posters — dropping those at the client level would miss the origin signal entirely.

---

## Docs

| File | What it covers |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | System design, full pipeline diagram, repo layout. |
| [`docs/wallet-engine.md`](docs/wallet-engine.md) | Wallet universe builder, quality scoring model, lead-lag graph. |
| [`docs/candidate-scoring.md`](docs/candidate-scoring.md) | Candidate detection, enrichment, safety vetoes, social scoring, evidence fusion. |
| [`docs/data-sources.md`](docs/data-sources.md) | API catalog, free-tier status, MVP priority ranking, raw field specs. |
| [`docs/data-models.md`](docs/data-models.md) | PostgreSQL ORM tables, indexes, and data retention plan. |
| [`docs/pseudocode.md`](docs/pseudocode.md) | High-level Python pseudocode for the full system. |
| [`docs/references.md`](docs/references.md) | Research sources used in system design. |
| [`docs/runbook-staging.md`](docs/runbook-staging.md) | Staging bootstrap, migration, startup, webhook, smoke flow. |
| [`docs/runbook-prod.md`](docs/runbook-prod.md) | Production deployment and rollback checklist. |
| [`docs/production-readiness-checklist.md`](docs/production-readiness-checklist.md) | Production readiness gate and verification commands. |
