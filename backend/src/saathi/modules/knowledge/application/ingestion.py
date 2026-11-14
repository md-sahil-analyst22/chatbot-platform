"""Ingestion use case (P2.2 - P2.8). Orchestrates ports; contains no vendor code."""

import hashlib


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
