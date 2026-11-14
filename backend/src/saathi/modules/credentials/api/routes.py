"""BYOK endpoints (Phase 8.1). Not mounted until implemented.

PUT    /api/v1/credentials/{provider}   body {api_key} -> 200 {provider, masked, status}   OWNER
GET    /api/v1/credentials              -> [{id, provider, masked, status, created_at}]    ADMIN
DELETE /api/v1/credentials/{id}         -> 204 (revoke)                                    OWNER

The api_key field is write-only: it is never echoed, logged or included in validation errors.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/credentials", tags=["credentials"])
