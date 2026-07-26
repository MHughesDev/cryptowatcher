# Subsystem 4 — AI Recommender

## Purpose

Claude is the decision-maker. It receives the full TokenDataPacket and
outputs a structured decision: RECOMMEND, WATCH, or PASS — with full reasoning.

The code enforces hard vetoes. Claude handles everything else.

---

## Model and API configuration

```python
Model:          claude-sonnet-4-6 (claude-sonnet-4-6)
API:            Anthropic Messages API
Caching:        System prompt cached (ephemeral TTL — saves ~80% on prompt tokens)
Max tokens:     1024 (output — decision + reasoning is concise)
Temperature:    0 (deterministic, auditable decisions)
```

### Why prompt caching matters here

The system prompt (guardrails + instructions + output schema) is ~3,000 tokens
and is identical for every evaluation. With caching enabled, the first call
pays full price; subsequent calls within the 5-minute TTL pay ~10% of input cost.
At 1 call per 30 minutes per token across 20+ watched tokens, the savings compound.

See the claude-api skill for implementation details.

---

## Hard guardrails (code-level, checked BEFORE Claude is called)

These trigger automatic PASS with no AI call. They are non-negotiable.

| Condition | Reason |
|---|---|
| `mint_authority_active == True` | Token supply can be inflated infinitely |
| `freeze_authority_active == True` | Wallets can be frozen (you can't sell) |
| `lp_locked == False` | Dev can remove liquidity instantly |
| `sell_route_exists == False` | Literally cannot exit |
| `is_honeypot == True` | RugCheck confirms cannot sell |
| `creator_current_holding_pct > 30%` | Dev holds dominant exit position |
| `hostile_supply_pct > 50%` | Majority of supply can dump at once |
| `top_10_holders_pct > 80%` | Extreme concentration risk |
| `token_age_minutes < 1` | Too early — data incomplete |

When a hard guardrail fails:
- Token status → EXPIRED with reason = HARD_VETO
- Logged with which guardrail triggered
- NO Slack message
- NO AI call (save cost, save latency)

---

## Claude's system prompt (canonical)

This is the exact system prompt sent with every evaluation.
It is the single source of truth for Claude's role and behavior.

```
You are a Solana memecoin signal analyst. Your job is to evaluate whether a
watched token is worth recommending to a trader based on aggregated on-chain,
market, and social data.

You will receive a structured data packet (TokenDataPacket) about a token
that was bought by one or more high-quality tracked wallets. Your job is to
reason carefully about this data and produce a structured decision.

DECISION OPTIONS:
- RECOMMEND: You believe this token has a genuine opportunity right now.
  The wallet signal is strong, the structure is clean, there is real momentum,
  and the risk/reward makes sense. Send to Slack immediately.

- WATCH: The setup is interesting but not ready yet. Something is missing —
  momentum hasn't arrived, social is thin, or a data point needs to confirm.
  Re-evaluate in the next cycle.

- PASS: This token does not meet the bar. Reasons can include: weak wallet
  signal, bad tokenomics, suspicious distribution, fading momentum, no social
  traction, copycat narrative, or any combination of red flags.

CONFIDENCE:
- HIGH: Multiple strong signals aligning with minimal red flags
- MEDIUM: Net positive but with meaningful uncertainty
- LOW: Marginal case — proceed with caution if RECOMMEND, skeptical if WATCH

WHAT MAKES A GOOD MEMECOIN OPPORTUNITY:
1. Multiple high-quality wallets bought early (top 20% of holders) at low MC
2. Dev has minimal/zero holdings OR has already sold out cleanly with price holding
3. LP is locked (non-negotiable — already filtered, but note it in reasoning)
4. Low hostile supply: snipers and bundles have mostly sold or are holding small %
5. Genuine holder growth: unique holders increasing naturally, not inflated
6. Authentic social: organic mentions, not bot spam or obvious paid shilling
7. Real volume: buy/sell ratio favoring buyers, with authentic volume (not wash)
8. Narrative is clear and timely: does the token name/concept make cultural sense right now?
9. Market cap is still early: ideally <$500k for highest upside; <$2M still viable
10. Momentum is building, not fading: positive price action, increasing holder count

RED FLAGS TO WEIGHT HEAVILY:
- Creator still holding >10% (anything over 5% warrants mention)
- Bundle wallets still holding significant supply (hidden sell pressure)
- Social is all bots or coordinated shills (check coordinated_shilling_detected)
- The token is a copycat of something that already ran (derivative with no new narrative)
- Volume is declining while price holds (distribution happening)
- Entry percentile for tracked wallets is >40% (they got in late, not early)
- Market cap already >$3M (most of the move may be over)
- Holder count is growing via bots (rapid large bursts, not organic spread)
- Official Twitter was created same day as token

REASONING STYLE:
- Be specific. Reference actual numbers from the data, not vague statements.
- Be direct. State what you actually think, not what sounds safe.
- Be concise. 3-5 sentences of reasoning. No padding.
- Identify the single strongest signal for your decision and the single biggest risk.
- If you RECOMMEND, write a Slack message that is informative and action-oriented
  (not hype). Include the key thesis in one sentence.

OUTPUT FORMAT:
You MUST respond with valid JSON matching this exact schema. No other text.

{
  "decision": "RECOMMEND" | "WATCH" | "PASS",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "strongest_signal": "one sentence — the most important reason for this decision",
  "biggest_risk": "one sentence — the most important risk or concern",
  "reasoning": "3-5 sentences of full reasoning",
  "watch_for": "if WATCH: what specific condition would upgrade this to RECOMMEND",
  "slack_message": "if RECOMMEND: full formatted Slack message (see format spec); else null"
}
```

---

## Evaluation call structure (Python)

```python
import anthropic
from wigs.filters import HARD_GUARDRAILS  # code-level vetoes

client = anthropic.Anthropic()

async def evaluate_token(packet: TokenDataPacket) -> AIDecision:
    # 1. Run hard guardrails — no AI call if any fail
    veto = check_hard_guardrails(packet)
    if veto:
        return AIDecision(decision="PASS", reason=f"HARD_VETO:{veto}", no_ai_call=True)

    # 2. Build user message from packet
    user_message = format_data_packet_for_claude(packet)

    # 3. Call Claude with prompt caching on system prompt
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"}  # cache the system prompt
            }
        ],
        messages=[
            {"role": "user", "content": user_message}
        ]
    )

    # 4. Parse structured JSON response
    decision = parse_ai_response(response.content[0].text)

    # 5. Log full decision with all context
    await log_ai_decision(packet.token_mint, packet, decision, response.usage)

    return decision
```

---

## Data packet formatting for Claude

The TokenDataPacket is serialized into a structured natural-language format
before being sent to Claude. Do NOT send raw JSON — Claude reasons better
with labeled, organized text.

Structure:

```
TOKEN: $SYMBOL (mint: <address>)
Age: X minutes | DEX: Raydium | Platform: pump.fun graduate

WALLET SIGNAL
• N tracked wallets bought this token
• Highest quality wallet: 72% 30d win rate, $8,400 avg trade, bought at $180k MC (top 8% of holders)
• Buy time spread: 4 minutes 12 seconds — TIGHT CONVERGENCE
• Current MC: $340k | Wallets bought at avg: $175k MC (1.9x since signal)

SUPPLY DISTRIBUTION
• Top 10 holders: 34% | Top 20: 51% | Gini: 0.61
• Creator holding: 2.1% (sold 97.9% of initial position — clean exit)
• Bundle supply: 8.2% (3 bundle wallets, 6.1% still holding)
• Sniper supply: 4.1% (11 sniper wallets, 2.3% still holding)
• Hostile supply total: 8.4% — LOW RISK
• Holder count: 847 (up 312 in last hour)

LIQUIDITY & SAFETY
• Liquidity: $42,000 USD
• LP locked: YES — 180 days via Streamflow (100% of LP)
• Mint authority: REVOKED
• Freeze authority: REVOKED
• Price impact (1 SOL sell): 0.8% — LIQUID
• Price impact (5 SOL sell): 4.2%
• Sell route: YES

MARKET DYNAMICS
• Market cap: $340,000 | FDV: $340,000
• Volume (5m): $12,400 | Volume (1h): $87,000 | Vol/MC: 25.6%
• Buy/sell ratio (5m): 3.2:1 — STRONG BUY PRESSURE
• Unique buyers (1h): 203
• Price change (5m): +8.2% | (1h): +34.1%
• Volume authenticity: 91% real

SOCIAL
• Twitter: @TokenHandle | 2,847 followers | Account age: 8 days
• Twitter mentions (1h): 124 quality mentions (accounts >30d, >100 followers)
• Cashtag volume (1h): 89 $SYMBOL mentions
• Sentiment: 0.72 (bullish)
• Coordinated shilling: NOT DETECTED
• Bot mention %: 11%
• Narrative: ANIMAL — strong cultural resonance (Pepe variant, Frog Superbowl meme)

SAFETY
• RugCheck score: 82/100
• RugCheck risks: ["low liquidity warning"] — minor

CREATOR HISTORY
• Prior tokens: 2
• Prior outcomes: 1 survivor (82k peak MC), 1 dead on arrival
• No prior rugs

PREVIOUS EVALUATIONS
• 8 minutes ago: WATCH (MEDIUM) — "Momentum building but volume needs to confirm; social still thin at that point"
• Current MC was $210k at last evaluation (62% increase since)
```

---

## Decision logging

Every AI call is permanently logged with:

```python
AIEvaluationLog:
    token_mint: str
    evaluated_at: datetime
    decision: str              # RECOMMEND | WATCH | PASS | HARD_VETO
    confidence: str
    strongest_signal: str
    biggest_risk: str
    reasoning: str
    watch_for: str | None
    
    # Snapshot of key data at evaluation time
    mc_at_evaluation: float
    wallet_count: int
    holder_count: int
    
    # API usage (for cost tracking)
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
```

This log is the audit trail. You can always answer "why did WIGS recommend this?"

---

## Cost estimation

At steady state with 20 watched tokens, each evaluated every 30 minutes:

```
Calls per hour:          40
System prompt tokens:    ~3,000 (cached after first call, ~5 min TTL)
Data packet tokens:      ~1,500 per call (varies)
Output tokens:           ~300 per call

Cache hit rate:          ~85% (within 5-min window across 40 calls/hour)
Estimated cost/hour:     ~$0.15 - $0.30 depending on cache efficiency
Estimated cost/day:      ~$3.60 - $7.20
```

This is trivially cheap for the value of the signal.
