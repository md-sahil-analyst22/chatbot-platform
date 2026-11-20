# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Future web endpoints for uploading documents and FAQs (listed in the text below).
# Status: 🟡 Placeholder - built in a later phase (see
#         docs/planning/05_PHASEWISE_DEVELOPMENT_PLAN.md).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Knowledge endpoints (Phase 2). Not mounted until implemented.

Planned:
  POST /api/v1/bots/{bot_id}/sources/upload   multipart -> object storage -> enqueue job (202)
  POST /api/v1/bots/{bot_id}/sources/crawl    {url, depth, include, exclude} -> enqueue (202)
  GET  /api/v1/bots/{bot_id}/sources          list with status
  CRUD /api/v1/bots/{bot_id}/faqs
Uploads: size limit, extension + magic-byte check, never trust the client filename.
"""

# From fastapi — the web framework that turns Python functions into web endpoints: APIRouter = a
#   group of related endpoints.
from fastapi import APIRouter

router = APIRouter(tags=["knowledge"])
