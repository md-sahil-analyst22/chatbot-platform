# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Future web endpoints for tenants' own API keys (listed in the text below).
# Status: 🟡 Placeholder - built in a later phase (see
#         docs/planning/05_PHASEWISE_DEVELOPMENT_PLAN.md).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""BYOK endpoints (Phase 8.1). Not mounted until implemented.

PUT    /api/v1/credentials/{provider}   body {api_key} -> 200 {provider, masked, status}   OWNER
GET    /api/v1/credentials              -> [{id, provider, masked, status, created_at}]    ADMIN
DELETE /api/v1/credentials/{id}         -> 204 (revoke)                                    OWNER

The api_key field is write-only: it is never echoed, logged or included in validation errors.
"""

# From fastapi — the web framework that turns Python functions into web endpoints: APIRouter = a
#   group of related endpoints.
from fastapi import APIRouter

router = APIRouter(prefix="/credentials", tags=["credentials"])
