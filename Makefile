# Run from the repo root.
COMPOSE = docker compose --env-file .env -f infra/docker-compose.yml

.PHONY: up up-local-db down logs ps studio migrate test lint fmt typecheck arch check-keys validate-golden n8n

up:            ## start redis, api, worker (database: Supabase via DATABASE_URL in .env)
	$(COMPOSE) up -d --build

up-local-db:   ## same, plus a local Postgres for offline work (point .env URLs at it first)
	$(COMPOSE) --profile local-db up -d --build

down:          ## stop everything (keeps volumes)
	$(COMPOSE) --profile local-db down

logs:
	$(COMPOSE) logs -f api worker

ps:
	$(COMPOSE) ps

studio:        ## run Bot Studio (dashboard) dev server on :5173
	cd dashboard && npm install && npm run dev

n8n:           ## start n8n too (optional profile)
	$(COMPOSE) --profile integrations up -d n8n

migrate:
	cd backend && uv run --env-file ../.env alembic upgrade head

test:
	cd backend && uv run pytest -q

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .

fmt:
	cd backend && uv run ruff check --fix . && uv run ruff format .

typecheck:
	cd backend && uv run mypy src

arch:          ## enforce module/layer boundaries
	cd backend && uv run lint-imports

check-keys:    ## Phase 0 exit check (add ARGS=--send-whatsapp to send the test template)
	uv run --with httpx scripts/check_keys.py $(ARGS)

validate-golden:
	python3 evals/runners/validate_golden.py evals/golden/golden_v0.jsonl
