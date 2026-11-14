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


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.env != "local")
    is_prod = settings.env == "production"

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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
            await container.aclose()

    app = FastAPI(
        title="Saathi AI API",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url=None if is_prod else "/docs",
        redoc_url=None,
        openapi_url=None if is_prod else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key"],
    )
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    app.include_router(build_api_router())
    return app
