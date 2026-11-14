# backend/

FastAPI API + ARQ worker. Python 3.12, managed with **uv**.

```bash
uv sync                    # install deps (+ dev group)
uv run pytest -q           # tests
uv run ruff check .        # lint
uv run mypy src            # types
uv run lint-imports        # module/layer boundaries
uv run uvicorn saathi.main:create_app --factory --reload
```

Layout: `src/saathi/` (application code), `migrations/` (Alembic), `tests/`.
See `../docs/REPO_STRUCTURE.md` for the full explanation.
