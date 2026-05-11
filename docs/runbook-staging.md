# Staging Runbook

## 1) Configure environment
1. Copy `.env.example` to `.env`.
2. Fill required vars: `DATABASE_URL`, `REDIS_URL`, `HELIUS_API_KEY`, `HELIUS_WEBHOOK_SECRET`.

## 2) Validate and migrate
```bash
make env-check
make migrate
```

Or run a single command:
```bash
./scripts/bootstrap_staging.sh
```

## 3) Start services
In terminal A:
```bash
make run-api
```
In terminal B:
```bash
PYTHONPATH=src make run-worker
```

## 4) Register webhook
```bash
HELIUS_API_KEY=... make webhook-register WEBHOOK_URL=https://<public-host>/webhook/helius
```

Or inline with bootstrap:
```bash
./scripts/bootstrap_staging.sh --register-webhook --webhook-url=https://<public-host>/webhook/helius
```

## 5) Smoke checks
```bash
make smoke
curl -s http://127.0.0.1:8000/metrics/system
```

## 6) Docker-based staging (optional)
```bash
make docker-up
make docker-logs
make docker-down
```
