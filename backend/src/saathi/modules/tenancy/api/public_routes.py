"""Public, unauthenticated widget endpoints (mounted under /public/v1).

Returns only fields safe for anyone to read. Rate-limited per IP and per bot (P6.6), cacheable
for 60 s so a busy website does not hit the database on every page view.
"""

from fastapi import APIRouter, Response

from saathi.modules.tenancy.api.deps import ResolvedWidgetDep
from saathi.modules.tenancy.api.schemas import PublicWidgetConfigOut

router = APIRouter(prefix="/widgets", tags=["public-widget"])


@router.get("/{public_key}/config")
async def widget_config(widget: ResolvedWidgetDep, response: Response) -> PublicWidgetConfigOut:
    cfg = await widget.service.get(widget.tenant_id, widget.bot_id)
    response.headers["Cache-Control"] = "public, max-age=60"
    return PublicWidgetConfigOut(
        bot_id=cfg.bot_id,
        header_title=cfg.header_title,
        header_subtitle=cfg.header_subtitle,
        footer_text=cfg.footer_text,
        greeting=cfg.greeting,
        primary_color=cfg.primary_color,
        launcher_position=cfg.launcher_position,
        logo_url=None,  # P4.13: ObjectStore.public_url(...) for cfg.logo_asset_id
        languages=list(cfg.languages),
    )
