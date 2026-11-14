# syntax=docker/dockerfile:1
# ---- build stage ------------------------------------------------------------
FROM python:3.12-slim AS builder
# Pin to a specific uv version/digest before production.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

# Dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
RUN uv sync --no-dev --no-editable

# ---- runtime stage ----------------------------------------------------------
FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"
# Trusted proxies come from the FORWARDED_ALLOW_IPS env var (never '*').
CMD ["uvicorn", "saathi.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
