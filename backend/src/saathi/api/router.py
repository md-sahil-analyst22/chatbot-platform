from fastapi import APIRouter

from saathi.api.health import router as health_router
from saathi.modules.tenancy.api.config_routes import options_router as model_options_router
from saathi.modules.tenancy.api.config_routes import router as bot_config_router
from saathi.modules.tenancy.api.public_routes import router as public_widget_router
from saathi.modules.tenancy.api.routes import router as tenancy_router


def build_api_router() -> APIRouter:
    root = APIRouter()
    root.include_router(health_router)  # unversioned: /health

    # Authenticated API (dashboard / Bot Studio): bearer token, tenant from token.
    v1 = APIRouter(prefix="/api/v1")
    v1.include_router(tenancy_router)
    v1.include_router(bot_config_router)
    v1.include_router(model_options_router)
    # Phase 2: knowledge | Phase 3: conversation | Phase 4: channel webhooks
    root.include_router(v1)

    # Public API (website widget): bot public key, no user login, read-only, rate-limited.
    public = APIRouter(prefix="/public/v1")
    public.include_router(public_widget_router)
    root.include_router(public)
    return root
