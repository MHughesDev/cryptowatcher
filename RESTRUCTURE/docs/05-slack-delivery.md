# Subsystem 5 — Slack Delivery

## Purpose

Send formatted token recommendations to a Slack channel when Claude decides
RECOMMEND. This is the only user-facing output of the entire system.

---

## Channel structure

| Channel | Purpose |
|---|---|
| `#recommendations` | All RECOMMEND decisions — primary signal channel |
| `#watchlist` | Tokens currently in WATCHED/ACTIVE state (optional, for visibility) |
| `#system-log` | Hard veto events, wallet adds/removes, system health — not for trading |

`#recommendations` is the only channel that matters for trading decisions.

---

## Recommendation message format

```
🟢 *STRONG SIGNAL* — $SYMBOL                     ← HIGH confidence
🟡 *SIGNAL* — $SYMBOL                            ← MEDIUM confidence
🔵 *EARLY SIGNAL* — $SYMBOL                      ← LOW confidence

*CA:* `<mint address>`
*MC Now:* $340k  |  *MC When Wallets Bought:* $175k avg  |  *Upside from signal:* 1.9x

*Why:* <Claude's one-sentence thesis from strongest_signal field>

*Wallets:* 3 tracked wallets (72% avg win rate) bought in the top 12% of holders
*Buy spread:* 4 minutes — tight convergence signal

*Key risk:* <Claude's biggest_risk field>

*Safety:* LP locked 180d ✓ | Authorities revoked ✓ | RugCheck 82/100
*Supply:* Top 10 hold 34% | Dev holding 2.1% | Hostile supply 8.4%
*Volume:* $87k/hr | 91% authentic | 3.2:1 buy/sell ratio

*Social:* 124 quality mentions in last hour | Sentiment 0.72 | @TokenHandle (2.8k followers)
*Narrative:* ANIMAL — Frog meme cultural moment

— WIGS | <timestamp>
```

### Rules for message content

- The CA is always in a code block so it can be copied easily
- All dollar amounts use `$Xk` / `$XM` notation (not full numbers)
- Confidence is reflected in the emoji + header: 🟢 STRONG, 🟡 SIGNAL, 🔵 EARLY
- Claude's reasoning populates `Why:` and `Key risk:` directly — no paraphrasing
- Safety fields are always shown so the reader can verify without leaving Slack
- No hype language. No moon emoji. No "gem" or "100x" claims. Factual only.

---

## Watchlist message format (optional `#watchlist` channel)

Posted when a token enters WATCHED state (first wallet buy):

```
👀 *WATCHING* — $SYMBOL
CA: `<mint address>` | MC: $180k | Wallets: 1 (first signal)
Waiting for: second wallet buy, social confirmation, volume buildup
```

Updated when a second wallet buys:

```
👀 *WATCHING (ELEVATED)* — $SYMBOL
CA: `<mint address>` | MC: $210k | Wallets: 2 | Spread: 8 min
Escalated: multiple independent wallets within 30 min window
```

---

## System log messages (`#system-log`)

These are operational, not trading signals. Mute this channel by default.

```
🔴 HARD VETO — $SYMBOL | Reason: MINT_AUTHORITY_ACTIVE | CA: ...
⚪ WALLET ADDED — <address> | Source: HISTORICAL_WINNER | Win rate: 61% | 30d PnL: +$12,400
🔴 WALLET REMOVED — <address> | Reason: TRADE_SIZE_WHALE | Last trade: $87,000
⚪ TOKEN EXPIRED — $SYMBOL | Reason: TIMEOUT_7D | Never recommended
```

---

## Implementation

Use the official Slack Bolt SDK (Python) or the `slack_sdk` webhook client.

For the recommendation channel, use an incoming webhook URL (simplest path).
For the system log, same approach.

```python
import slack_sdk

client = slack_sdk.WebhookClient(url=settings.slack_webhook_url)

def send_recommendation(packet: TokenDataPacket, decision: AIDecision) -> None:
    message = format_recommendation_message(packet, decision)
    client.send(text=message)
```

The message formatter is a pure function: takes data in, returns a Slack-formatted
string. No side effects. Easy to test.

---

## Deduplication

Never send the same token twice unless it re-enters the watch list as a new event.
Track `recommendation_sent_at` on the token. If it's already set, skip.

The only exception: if a token was RECOMMENDED 48+ hours ago, re-enters the watch
list because of new wallet buys, and passes a fresh AI evaluation — send again
with a note that this is a re-entry signal.

---

## Rate limiting

Do not send more than 3 recommendations within any 10-minute window.
If more qualify simultaneously, queue them and send with a 4-minute gap.
This prevents alert fatigue and gives you time to act on each one.
