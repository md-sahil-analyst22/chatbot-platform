# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The front door of the backend. create_app() builds the whole web application that
#       answers every HTTP request.
# Where it fits: uvicorn (the web server) calls create_app() once at start-up. Routes, security,
#                logging and the database are all plugged in here.
# Read next: api/router.py (which URLs exist) and bootstrap/container.py (the shared tools).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""ASGI entry point. Run with: uvicorn saathi.main:create_app --factory"""

# From collections.abc — standard type names for collections: AsyncIterator = type for something
#   looped with `async for`.
from collections.abc import AsyncIterator

# From contextlib — helpers for building `with` blocks: asynccontextmanager = turns an async
#   function into an `async with` block.
from contextlib import asynccontextmanager

# From fastapi — the web framework that turns Python functions into web endpoints: FastAPI = the
#   web app object.
from fastapi import FastAPI

# From fastapi.middleware.cors — browser cross-site access rules (CORS): CORSMiddleware =
#   decides which websites' browsers may call the API.
from fastapi.middleware.cors import CORSMiddleware

# From saathi.api.errors — turns our errors into JSON error responses: register_error_handlers =
#   installs the error -> JSON handlers.
from saathi.api.errors import register_error_handlers

# From saathi.api.middleware — per-request logging and request ids: RequestContextMiddleware =
#   adds a request id and access log to every request.
from saathi.api.middleware import RequestContextMiddleware

# From saathi.api.router — puts all endpoint groups together: build_api_router = builds the
#   /api/v1 router.
from saathi.api.router import build_api_router

# From saathi.bootstrap.container — builds the app's shared objects once at start-up: Container
#   = holds the shared objects (database, Redis, HTTP client...).
from saathi.bootstrap.container import Container

# From saathi.platform.config.settings — the app's core settings: get_settings = the settings,
#   read once.
from saathi.platform.config.settings import get_settings

# From saathi.platform.logging.setup — logging set-up: configure_logging = sets up logging.
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
