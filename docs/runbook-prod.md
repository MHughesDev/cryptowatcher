# Production Runbook

## Pre-deploy checklist
- Secrets provisioned in secret manager.
- Database backup and migration window approved.
- New app image built and scanned.

## Deploy sequence
1. Deploy API/worker image.
2. Run `alembic upgrade head` once (or run `migrate` job first if using compose/k8s job equivalent).
3. Verify `/health` and `/metrics/system`.
4. Confirm worker scheduler is active from logs.
5. Register/update Helius webhook endpoint.

## Rollback
- Re-deploy previous image.
- If schema rollback is required, run `alembic downgrade -1` only after impact review.

## Post-deploy validation
- Webhook requests increasing.
- `webhook_events_processed` advancing.
- `wallet_lifecycle_active` gauge non-zero.
- Alerts show expected channels (`LOG`/`DISCORD`/`TELEGRAM`/`SLACK`) based on feature flags.
