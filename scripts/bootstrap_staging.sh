#!/usr/bin/env bash
set -euo pipefail

CHECK_ONLY=false
SMOKE_ONLY=false
REGISTER_WEBHOOK=false
WEBHOOK_URL="${WEBHOOK_URL:-}"

for arg in "$@"; do
  case "$arg" in
    --check-only) CHECK_ONLY=true ;;
    --smoke-only) SMOKE_ONLY=true ;;
    --register-webhook) REGISTER_WEBHOOK=true ;;
    --webhook-url=*) WEBHOOK_URL="${arg#*=}" ;;
  esac
done

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

required=(DATABASE_URL REDIS_URL HELIUS_API_KEY HELIUS_WEBHOOK_SECRET)
missing=()
for key in "${required[@]}"; do
  if [[ -z "${!key:-}" ]]; then
    missing+=("$key")
  fi
done

if (( ${#missing[@]} > 0 )); then
  echo "Missing required env vars: ${missing[*]}" >&2
  exit 1
fi

echo "Environment validation passed."

$CHECK_ONLY && exit 0

if ! $SMOKE_ONLY; then
  echo "Running migrations..."
  alembic upgrade head
fi

if $REGISTER_WEBHOOK; then
  if [[ -z "$WEBHOOK_URL" ]]; then
    echo "Missing --webhook-url for webhook registration" >&2
    exit 1
  fi
  echo "Registering Helius webhook..."
  python scripts/register_helius_webhook.py --url "$WEBHOOK_URL"
fi

echo "Running API health smoke check (requires API running on localhost:8000)..."
python - <<'PY'
import json
import urllib.request

url = "http://127.0.0.1:8000/health"
try:
    with urllib.request.urlopen(url, timeout=3) as resp:
        data = json.loads(resp.read().decode())
except Exception as exc:
    raise SystemExit(f"Health check failed: {exc}")
if data.get("status") != "ok":
    raise SystemExit(f"Unexpected health payload: {data}")
print("Health check passed.")
PY

echo "Smoke checks completed."
