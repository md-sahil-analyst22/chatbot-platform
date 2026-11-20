# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The future 'learn a document' process (read, split, embed, save). The planned steps are
#       listed at the bottom.
# Status: 🟡 Placeholder - built in a later phase (see
#         docs/planning/05_PHASEWISE_DEVELOPMENT_PLAN.md).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Ingestion use case (P2.2 - P2.8). Orchestrates ports; contains no vendor code."""

import hashlib


# A fingerprint (SHA-256) of a file: same file = same fingerprint.
def content_hash(data: bytes) -> str:
    """Stable file fingerprint used for idempotent re-sync."""
    return hashlib.sha256(data).hexdigest()


# Planned flow (implemented in Phase 2):
#   1. load Source (tenant-bound session) -> transition QUEUED -> PROCESSING
#   2. bytes = ObjectStore.get(key); if source.is_unchanged(hash): mark READY, stop
#   3. ParsedDocument = parser.parse(bytes)  -> clean -> chunk (heading-aware, 500-800 tokens)
#   4. vectors = Embedder.embed(chunks) in batches
#   5. in ONE transaction: delete old chunks for source, insert new chunks, set hash, READY
#   6. any exception -> FAILED with a safe error message (no stack traces stored)
