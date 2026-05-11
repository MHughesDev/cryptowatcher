PYTHON ?= python
UVICORN ?= uvicorn
APP_MODULE ?= wigs.app:app

.PHONY: setup migrate run-api run-worker smoke webhook-register env-check docker-up docker-down docker-logs readiness-check

setup: env-check migrate
	@echo "Setup complete."

env-check:
	@./scripts/bootstrap_staging.sh --check-only

migrate:
	@alembic upgrade head

run-api:
	@$(UVICORN) $(APP_MODULE) --host 0.0.0.0 --port 8000 --reload

run-worker:
	@$(PYTHON) -m wigs.workers

smoke:
	@./scripts/bootstrap_staging.sh --smoke-only

webhook-register:
	@$(PYTHON) scripts/register_helius_webhook.py --url "$(WEBHOOK_URL)"

docker-up:
	@docker compose up -d postgres redis
	@docker compose run --rm migrate
	@docker compose up -d app worker

docker-down:
	@docker compose down

docker-logs:
	@docker compose logs -f app worker

readiness-check:
	@./scripts/verify_production_readiness.sh
