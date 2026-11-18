# Run from the repo root.
COMPOSE = docker compose --env-file .env -f infra/docker-compose.yml

.PHONY: up up-local-db down logs ps studio migrate schema-sql smoke-live code-guide-check test test-db lint fmt typecheck arch check-keys validate-golden n8n

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

schema-sql:    ## regenerate backend/migrations/schema.sql from the migrations (no DB connection)
	cd backend && { sed -n '1,13p' migrations/schema.sql; uv run --env-file ../.env alembic upgrade head --sql 2>/dev/null; } > migrations/schema.sql.tmp && mv migrations/schema.sql.tmp migrations/schema.sql

test:
	cd backend && uv run pytest -q

test-db:       ## real-Postgres tests (RLS isolation, SQL repositories, migration round trip); needs TEST_DATABASE_URL + TEST_APP_DATABASE_URL exported
	cd backend && RUN_DB_TESTS=1 uv run pytest -q tests/security tests/contracts/test_sql_repositories.py

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .

fmt:
	cd backend && uv run ruff check --fix . && uv run ruff format .

typecheck:
	cd backend && uv run mypy src

arch:          ## enforce module/layer boundaries
	cd backend && uv run lint-imports

smoke-live:    ## Phase 1 exit check on the LIVE API: real login, create/configure/publish a test bot (ARGS=--keep)
	uv run --with httpx scripts/smoke_live.py $(ARGS)

code-guide-check: ## list backend classes/functions docs/CODE_GUIDE.md doesn't explain yet
	cd backend && uv run python ../scripts/check_code_guide.py

check-keys:    ## Phase 0 exit check (add ARGS=--send-whatsapp to send the test template)
	uv run --with httpx scripts/check_keys.py $(ARGS)

validate-golden:
	python3 evals/runners/validate_golden.py evals/golden/golden_v0.jsonl
