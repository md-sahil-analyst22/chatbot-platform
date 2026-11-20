# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The public widget endpoint: GET /public/v1/widget/{key}/config - no login needed.
# Security: 🔒 Returns display fields only. The tenant is found from the key on the server, never
#           from the request.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Public, unauthenticated widget endpoints (mounted under /public/v1).

Returns only fields safe for anyone to read. Rate-limited per IP and per bot (P6.6), cacheable
for 60 s so a busy website does not hit the database on every page view.
"""

# From fastapi — the web framework that turns Python functions into web endpoints: APIRouter = a
#   group of related endpoints; Response = the outgoing HTTP response.
from fastapi import APIRouter, Response

# From saathi.modules.tenancy.api.deps — builds the tenancy services per request:
#   ResolvedWidgetDep = a ready ResolvedWidget.
from saathi.modules.tenancy.api.deps import ResolvedWidgetDep

# From saathi.modules.tenancy.api.schemas — the JSON shapes of the tenancy API:
#   PublicWidgetConfigOut = public widget response.
from saathi.modules.tenancy.api.schemas import PublicWidgetConfigOut

router = APIRouter(prefix="/widgets", tags=["public-widget"])


# The widget calls this when it loads on a tenant's website.
@router.get("/{public_key}/config")
async def widget_config(widget: ResolvedWidgetDep, response: Response) -> PublicWidgetConfigOut:
    cfg = await widget.service.get(widget.tenant_id, widget.bot_id)
    response.headers["Cache-Control"] = "public, max-age=60"
    return PublicWidgetConfigOut(
        header_title=cfg.header_title,
        header_subtitle=cfg.header_subtitle,
        footer_text=cfg.footer_text,
        greeting=cfg.greeting,
        primary_color=cfg.primary_color,
        launcher_position=cfg.launcher_position,
        logo_url=None,  # P4.13: ObjectStore.public_url(...) for cfg.logo_asset_id
        languages=list(cfg.languages),
    )
