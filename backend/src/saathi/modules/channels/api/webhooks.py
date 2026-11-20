# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Future WhatsApp webhook endpoints (details in the text below).
# Status: 🟡 Placeholder - built in a later phase (see
#         docs/planning/05_PHASEWISE_DEVELOPMENT_PLAN.md).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""WhatsApp webhook (P4.6). Not mounted until implemented.

GET  /api/v1/webhooks/whatsapp  - subscription challenge (hub.verify_token must match)
POST /api/v1/webhooks/whatsapp  - verify X-Hub-Signature-256 on the RAW body, enqueue, return 200
Never call the LLM inside the webhook request: Meta retries slow webhooks -> duplicate replies.
"""

from fastapi import APIRouter

router = APIRouter(tags=["webhooks"])
