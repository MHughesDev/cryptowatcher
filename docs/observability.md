# Observability (Phase 5)

This project now exposes lightweight in-process metrics for operational monitoring.

## Endpoint

- `GET /metrics/system`
- Returns JSON with:
  - `counters`: cumulative counter values
  - `gauges`: latest gauge values

## Webhook counters

Incremented in `POST /webhook/helius`:

- `webhook_received_requests`
- `webhook_events_processed`
- `webhook_events_skipped_no_wallet`
- `webhook_events_skipped_untracked`

## Wallet lifecycle gauges/counters

Updated by `update_wallet_scores` worker job:

- Gauges:
  - `wallet_lifecycle_active`
  - `wallet_lifecycle_degraded`
  - `wallet_lifecycle_retired`
- Counter:
  - `wallet_scores_updated`

## Notes

- These metrics are process-local and reset on restart.
- Intended for immediate operational visibility and local/staging debugging.
