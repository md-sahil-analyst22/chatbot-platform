# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Future chat endpoints (listed in the text below).
# Status: 🟡 Placeholder - built in a later phase (see
#         docs/planning/05_PHASEWISE_DEVELOPMENT_PLAN.md).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Chat endpoints (P3.8). Not mounted until implemented.

POST /api/v1/chat          -> full reply (JSON)
POST /api/v1/chat/stream   -> Server-Sent Events: token, citations, done
Public widget calls authenticate with the bot's public key + CORS allowlist + rate limits.
"""

from fastapi import APIRouter

router = APIRouter(tags=["chat"])
