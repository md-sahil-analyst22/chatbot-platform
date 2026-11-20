# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The map of every URL the API answers, grouped into three areas.
# Areas: /health + /ready (no login), /api/v1/... (Bot Studio, login required), /public/v1/...
#        (the website widget, no login, read-only).
# Used by: main.py attaches this map to the app.
# ─────────────────────────────────────────────────────────────────────────────────────────────
from fastapi import APIRouter

from saathi.api.health import router as health_router
from saathi.modules.tenancy.api.config_routes import options_router as model_options_router
from saathi.modules.tenancy.api.config_routes import router as bot_config_router
from saathi.modules.tenancy.api.public_routes import router as public_widget_router
from saathi.modules.tenancy.api.routes import router as tenancy_router


# Builds the URL map. Each module contributes its own routes; this file only groups them.
def build_api_router() -> APIRouter:
    root = APIRouter()
    root.include_router(health_router)  # unversioned: /health

    # Authenticated API (dashboard / Bot Studio): bearer token, tenant from token.
    v1 = APIRouter(prefix="/api/v1")
    # Bots: create, list, read, update, delete (modules/tenancy/api/routes.py).
    v1.include_router(tenancy_router)
    # Bot configuration versions: save draft, publish, rollback (config_routes.py).
    v1.include_router(bot_config_router)
    # Which AI models this tenant's plan may use.
    v1.include_router(model_options_router)
    # Phase 2: knowledge | Phase 3: conversation | Phase 4: channel webhooks
    root.include_router(v1)

    # Public API (website widget): bot public key, no user login, read-only, rate-limited.
    public = APIRouter(prefix="/public/v1")
    # The widget's public look - no login, only safe fields (public_routes.py).
    public.include_router(public_widget_router)
    root.include_router(public)
    return root
