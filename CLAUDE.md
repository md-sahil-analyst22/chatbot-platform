# Instructions for Claude in this repository

**Before writing or changing code, read [`docs/REPO_STRUCTURE.md`](docs/REPO_STRUCTURE.md), Part 0 and Part 1.** It's the coding rulebook for this repo: where each kind of code goes (§0.5), 45 numbered rules with reasons and examples, and the "before you say done" checklist (§1.12).

## The rules you must never break

- **R3:** `domain/` is plain Python: no FastAPI, SQLAlchemy, pydantic, httpx or Redis.
- **R4:** modules never import each other.
- **R6:** only a module's `api/deps.py` imports adapters; routes stay thin.
- **R7:** vendors only through ports + registries, chosen by configuration.
- **R8:** the tenant comes from the verified token, never from the request.
- **R15 / R23:** every query filters by `tenant_id`; every tenant table has forced RLS.
- **R16:** fail closed: missing auth, key or signature means deny.
- **R17:** secrets never in code, logs, errors or responses.

## Before you finish

```bash
cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy src && uv run lint-imports && uv run pytest
cd ../dashboard && npm run typecheck && npm test && npm run build
```

If a request conflicts with a rule or a planning document in `docs/planning/`, say so and recommend a fix (R44). Don't silently adapt.
