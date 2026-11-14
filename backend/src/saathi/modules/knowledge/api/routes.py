"""Knowledge endpoints (Phase 2). Not mounted until implemented.

Planned:
  POST /api/v1/bots/{bot_id}/sources/upload   multipart -> object storage -> enqueue job (202)
  POST /api/v1/bots/{bot_id}/sources/crawl    {url, depth, include, exclude} -> enqueue (202)
  GET  /api/v1/bots/{bot_id}/sources          list with status
  CRUD /api/v1/bots/{bot_id}/faqs
Uploads: size limit, extension + magic-byte check, never trust the client filename.
"""

from fastapi import APIRouter

router = APIRouter(tags=["knowledge"])
