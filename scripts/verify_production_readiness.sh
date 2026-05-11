#!/usr/bin/env bash
set -euo pipefail

echo "[1/6] Environment validation"
./scripts/bootstrap_staging.sh --check-only

echo "[2/6] Bootstrap script syntax"
bash -n ./scripts/bootstrap_staging.sh

echo "[3/6] Webhook registration CLI help"
python ./scripts/register_helius_webhook.py --help >/dev/null

echo "[4/6] Docker flow command generation"
make -n docker-up >/dev/null

echo "[5/6] Observability unit test"
PYTHONPATH=src pytest -q tests/test_observability.py

echo "[6/6] Decision label contract unit test"
PYTHONPATH=src pytest -q tests/test_decision_labels.py

echo "Production readiness verification checks passed."
