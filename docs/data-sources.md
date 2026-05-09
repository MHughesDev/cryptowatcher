# Data Sources and APIs

Free-tier and public APIs only for the MVP. Premium sources can be added later but must not be required to run.

## Source selection by role

```text
Wallet events:        Helius Webhooks / Solana RPC
Market data:          DexScreener + GeckoTerminal + Birdeye
Execution realism:    Jupiter Quote API
Pump.fun context:     Bitquery (when free quota allows)
Social confirmation:  Reddit + Telegram + Discord + GDELT + YouTube
Ground truth:         Solana RPC
```

## API catalog

| Layer | Source | Free-tier status | Use in WIGS | Key endpoints |
|---|---|---|---|---|
| Wallet events | Helius Webhooks | Free plan available; monitor quota. | Real-time tracked-wallet transaction notifications. | Webhook transaction events, address monitoring. |
| Wallet parsing | Helius Enhanced Transactions API | Free plan; confirm current limits before production. | Parse raw signatures into swaps/transfers and extract token mints. | Parsed transactions by signature/address. |
| Ground truth | Solana RPC | Public RPC is rate-limited; Helius free RPC is better. | Token supply, largest holders, account data, transaction verification. | `getTokenSupply`, `getTokenLargestAccounts`, `getTransaction`, `getSignaturesForAddress`. |
| Market data | DexScreener API | Public/free with documented rate limits. | Price, pairs, liquidity, volume, boosts, token profile, paid-order checks. | `/tokens/v1/{chainId}/{tokenAddresses}`, `/token-pairs/v1/{chainId}/{tokenAddress}`, `/latest/dex/search`. |
| Market confirmation | GeckoTerminal Public API | Free public; ~30 calls/min. | Second opinion for pools, liquidity, OHLCV, price, volume. | Network token and pool endpoints. |
| Market/security | Birdeye Data Services | Standard plan: free with limited compute units and 1 rps. | Price, OHLCV, token data, wallet/market enrichment, security checks. | `/defi/price`, `/defi/txs/token`, security endpoints. |
| Execution realism | Jupiter Quote API | Keyless and free with rate limits. | Quote buy/sell route, estimate output, price impact, route viability. | Quote API, Swap API. |
| Pump.fun context | Bitquery GraphQL | Free developer plan with strict limits. | Token creation, Pump.fun trading, migration/graduation, creator holdings, bonding curve context. | GraphQL Solana/Pump.fun queries. |
| Reddit trend | Reddit Data API | Eligible free usage with OAuth; 100 QPM per client. | Mention velocity in crypto/Solana/memecoin communities. | Subreddit search, listing, comments. |
| Telegram trend | Telegram Bot API | Free, rate-limited. | Track authorized/public groups and channels. | Bot updates, channel/group messages where permitted. |
| Discord trend | Discord API | Free, rate-limited; bot needs server access and correct intents. | Track server/channel mentions in communities with permission. | Gateway events, channel message APIs. |
| News/event trend | GDELT 2.0 | Free/open. | Verify whether token narrative maps to a real event, culture, or news trend. | GDELT DOC API, raw data, BigQuery. |
| Video trend | YouTube Data API | Default quota: 10,000 units/day. | Search videos/shorts/channels for ticker, name, or narrative mentions. | Search, videos, channels. |

## MVP priority ranking

| Priority | Source | Why |
|---:|---|---|
| 1 | Helius Webhooks | Wallet-led event detection is the core of the system. |
| 2 | Solana RPC | Ground truth for supply, holders, and transactions. |
| 3 | Jupiter Quote API | Tells whether a trade is actually routeable and sellable. |
| 4 | DexScreener | Fast public liquidity/volume/pair data. |
| 5 | GeckoTerminal | Independent market-data cross-check. |
| 6 | Birdeye | Enrichment and security data within free tier. |
| 7 | Reddit + Telegram + Discord | Social traction confirmation. |
| 8 | GDELT + YouTube | Real-world and broader narrative confirmation. |
| 9 | Bitquery | Pump.fun-specific context when quota allows. |

## Excluded from free MVP

| Source | Reason |
|---|---|
| X/Twitter API | No longer a clean free source for this use case. |
| Nansen / Arkham / paid wallet labels | Useful later; not required if wallet labels are built in-house. |
| Private Discord/Telegram groups without permission | Not acceptable unless the bot/client is invited and usage follows platform rules. |
| Paid Pump.fun event streams | Add later if needed; must not be required for MVP. |

## Raw field spec — wallet event

| Field | Type | Description |
|---|---|---|
| `wallet_address` | string | Tracked wallet that triggered the event. |
| `tx_signature` | string | Solana transaction signature. |
| `event_time` | datetime | Chain event time. |
| `detected_at` | datetime | System detection time. |
| `event_type` | enum | BUY, SELL, TRANSFER_IN, TRANSFER_OUT, LP_ADD, LP_REMOVE. |
| `token_mint` | string | SPL mint address. |
| `amount_base` | decimal | SOL/USDC or route base amount. |
| `amount_token` | decimal | Token units received or sold. |
| `dex_or_program` | string | Raydium, PumpSwap, Jupiter route, etc. |
| `pool_address` | string | Pool if known. |
| `parse_source` | string | Helius, Solana RPC, Bitquery, etc. |

## Raw field spec — candidate token

| Field | Type | Description |
|---|---|---|
| `token_mint` | string | Unique Solana token mint. |
| `symbol` | string | Display symbol; not trusted as identity. |
| `name` | string | Display name; not trusted as identity. |
| `created_at` | datetime | Earliest known creation time. |
| `creator_wallet` | string | Creator/deployer if known. |
| `launch_source` | enum | Pump.fun, direct pool, unknown, etc. |
| `primary_pool` | string | Highest-liquidity pool. |
| `primary_dex` | string | Venue for primary pool. |
| `market_cap` | decimal | Current market cap if available. |
| `fdv` | decimal | Fully diluted valuation if available. |
| `liquidity_usd` | decimal | Current liquidity. |
| `volume_5m` | decimal | Recent volume. |
| `volume_1h` | decimal | Hourly volume. |
| `volume_24h` | decimal | Daily volume. |
| `holder_count` | int | Number of holders if available. |
| `top_10_holder_pct` | decimal | Concentration risk. |
| `mint_authority_active` | bool | Safety flag. |
| `freeze_authority_active` | bool | Safety flag. |
| `sell_quote_ok` | bool | Jupiter route/sellability check passed. |
| `social_score` | int | Social/narrative confirmation score. |
| `total_score` | int | Final evidence fusion score. |
