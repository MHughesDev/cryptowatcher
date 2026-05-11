# Production Readiness Checklist

Use this checklist before starting integrated staging tests or production trial traffic.

## Status: Ready to test with external dependencies available

- [x] **Phase completion recorded** (Phases 1–10 marked complete in `MASTER_PLAN.md`).
- [x] **Environment validation script** exists and checks required secrets/URLs.
- [x] **Database migrations** are automated via `alembic upgrade head` and Compose `migrate` job.
- [x] **API and worker startup order** waits for migration completion in Compose.
- [x] **Webhook registration helper** exists (`scripts/register_helius_webhook.py`).
- [x] **Staging/prod runbooks** documented and linked from README.
- [x] **Readiness verification script** exists (`scripts/verify_production_readiness.sh`).
- [x] **Core smoke-level tests** for observability and decision label contract pass.

## Verification commands

```bash
make readiness-check
```

If Docker is installed locally, also run:

```bash
docker compose config
make docker-up
make docker-down
```

## Remaining external validation (cannot be fully simulated in this environment)

- Live Docker runtime execution.
- Real Helius webhook registration against your account.
- End-to-end webhook delivery from Helius to deployed `/webhook/helius`.
