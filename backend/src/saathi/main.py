# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The front door of the backend. create_app() builds the whole web application that
#       answers every HTTP request.
# Where it fits: uvicorn (the web server) calls create_app() once at start-up. Routes, security,
#                logging and the database are all plugged in here.
# Read next: api/router.py (which URLs exist) and bootstrap/container.py (the shared tools).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""ASGI entry point. Run with: uvicorn saathi.main:create_app --factory"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from saathi.api.errors import register_error_handlers
from saathi.api.middleware import RequestContextMiddleware
from saathi.api.router import build_api_router
from saathi.bootstrap.container import Container
from saathi.platform.config.settings import get_settings
from saathi.platform.logging.setup import configure_logging


# Builds and returns the web app. Runs once when the server starts.
def create_app() -> FastAPI:
    # Step 1: read every setting (database address, login config...) from the .env file.
    settings = get_settings()
    # Step 2: make every log line structured - JSON everywhere except on a developer's laptop.
    configure_logging(settings.log_level, json_logs=settings.env != "local")
    # In production the interactive API docs (/docs) are hidden, so outsiders can't browse every
    # endpoint.
    is_prod = settings.env == "production"

    # 'lifespan' = code that runs once at start-up (before `yield`) and once at shutdown (after
    # it).
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Build the shared toolbox ONCE: database pool, Redis, HTTP client, login checker, model
        # list.
        container = Container.build(settings)
        # Publish narrow resources; request handlers never see the whole container.
        app.state.sessionmaker = container.sessionmaker
        app.state.token_verifier = container.token_verifier
        app.state.http = container.http
        app.state.model_catalog = container.model_catalog
        app.state.readiness_checks = container.readiness_checks()
        try:
            yield
        finally:
            # Shutdown: close every connection cleanly so nothing is left hanging.
            await container.aclose()

    # Create the web application object itself.
    app = FastAPI(
        title="Saathi AI API",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url=None if is_prod else "/docs",
        redoc_url=None,
        openapi_url=None if is_prod else "/openapi.json",
    )
    app.add_middleware(
        # CORS = which other websites may call this API from a browser. Only Bot Studio's
        # address is allowed (from settings); cookies are never sent.
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key"],
    )
    # Give every request an id and write one log line per request (see api/middleware.py).
    app.add_middleware(RequestContextMiddleware)
    # Turn every error into the same clean JSON shape - no stack traces leak out
    # (api/errors.py).
    register_error_handlers(app)
    # Attach all the URLs: /health, /ready, /api/v1/... and /public/v1/... (api/router.py).
    app.include_router(build_api_router())
    return app
