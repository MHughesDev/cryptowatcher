# Wallet Discovery & Lifecycle Policy

This document defines the Phase 2 contract between wallet discovery and wallet retention.

## Discovery is additive-only

- Job: `discover_new_wallets` (scheduled daily).
- Inputs:
  - Recent completed outcomes labeled `HEAVY_HITTER` or `TRADEABLE_RUNNER`.
  - Active tracked wallets of type `KOL_PRECALL`.
- Behavior:
  - Builds a discovered wallet set with `wallet_universe.build_seed_wallet_set(...)`.
  - Upserts each wallet into `tracked_wallets` with source `seed_builder`.
  - Does **not** deactivate or delete wallets.

## Retention is score-driven

- Job: `update_wallet_scores` (scheduled every 6 hours).
- Behavior:
  - Recomputes wallet quality for active wallets.
  - Applies lifecycle thresholds:
    - `< wallet_degraded_quality_threshold`: `RETIRED` and `is_active=False`
    - `< wallet_active_quality_threshold`: `DEGRADED`
    - `>= wallet_active_quality_threshold`: `ACTIVE` and `is_active=True`

## Operational audit counters for discovery

`discover_new_wallets` logs these counters each run:

- `discovered`: total wallets returned by discovery algorithm
- `added`: newly inserted tracked wallets
- `existing`: wallets already present
- `reactivated`: previously inactive wallets reactivated via upsert
- `scored`: wallets that had enough events to produce a score snapshot
- `skipped_no_events`: wallets skipped for scoring due to no recent events

This split ensures discovery remains additive while retirement remains explicit and policy-controlled.
