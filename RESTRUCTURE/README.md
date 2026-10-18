# WIGS v2 — Restructure Reference

This folder is the single reference point for the complete redesign of WIGS.
Every design decision for v2 lives here. When building any component, read the
relevant doc before writing a single line of code.

## What changed and why

v1 was a deterministic algorithmic system. It computed numeric scores using
hand-tuned weights and thresholds and used those scores to make decisions.
The problem: every edge case required a human to tune a number. The system
could not reason about context — it could only compare values to thresholds.

v2 delegates all decision-making to an AI (Claude). The system's job is to
aggregate high-quality data. Claude's job is to reason about it and decide
whether a token is worth recommending. Humans tune the guardrails; Claude
handles everything in between.

## The pipeline in one sentence

> Track the right wallets → watch every token they buy → aggregate all
> meaningful data about that token → let Claude decide if it's worth buying →
> send recommendations to Slack.

## Document index

| Doc | What it covers |
|---|---|
| [`docs/00-system-overview.md`](docs/00-system-overview.md) | Full architecture, data flow, subsystem responsibilities |
| [`docs/01-wallet-tracker.md`](docs/01-wallet-tracker.md) | The 24/7 wallet add/remove engine — criteria, loop design, sources |
| [`docs/02-token-watcher.md`](docs/02-token-watcher.md) | Token state machine, watch criteria, data collection cadence |
| [`docs/03-data-aggregation.md`](docs/03-data-aggregation.md) | Every data point the AI receives — what, why, where it comes from |
| [`docs/04-ai-recommender.md`](docs/04-ai-recommender.md) | Claude's role, prompt design, guardrails, output schema |
| [`docs/05-slack-delivery.md`](docs/05-slack-delivery.md) | Slack message format, channel structure, alert anatomy |
| [`docs/06-data-sources.md`](docs/06-data-sources.md) | API catalog — endpoint, key, rate limit, cost, priority |
| [`docs/07-architecture.md`](docs/07-architecture.md) | Services, DB schema, job scheduler, infra decisions |
| [`docs/08-migration.md`](docs/08-migration.md) | What to keep, what to delete, build order for v2 |

## Ground rules for this rebuild

1. The AI makes recommendations. The code makes nothing happen without data.
2. Hard guardrails live in code. Soft judgment lives with Claude.
3. Every AI decision is logged with full reasoning — no black boxes.
4. The wallet tracker runs independently of everything else. Do not couple it.
5. Slack is the only alert channel. No Telegram, no Discord.
6. Data freshness is the product. Stale data = bad recommendations.
