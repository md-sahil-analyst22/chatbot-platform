# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: A 'Source' = one document or web page a bot learns from, and its life cycle.
# Life cycle: queued -> processing -> ready or failed; ready/failed can be queued again (re-sync
#             / retry). Any other jump is refused.
# Pattern: A small 'state machine': the object protects its own rules.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Knowledge domain. Source is an aggregate: its state changes only through intention-revealing
methods, so the lifecycle rules cannot be bypassed by assigning a field.
"""

# From enum — fixed sets of named values: StrEnum = a fixed set of named text values.
from enum import StrEnum

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From saathi.platform.errors — our error types: ConflictError = 409 clash with existing data.
from saathi.platform.errors import ConflictError


# The possible states of a source.
class SourceStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


# Which state may follow which. Everything not listed is forbidden.
_ALLOWED: dict[SourceStatus, frozenset[SourceStatus]] = {
    SourceStatus.QUEUED: frozenset({SourceStatus.PROCESSING}),
    SourceStatus.PROCESSING: frozenset({SourceStatus.READY, SourceStatus.FAILED}),
    SourceStatus.READY: frozenset({SourceStatus.QUEUED}),  # re-sync
    SourceStatus.FAILED: frozenset({SourceStatus.QUEUED}),  # retry
}


# One document/web page. Its status can only change through the methods below.
class Source:
    __slots__ = ("_content_hash", "_status", "bot_id", "id", "kind", "tenant_id", "uri")

    def __init__(
        self,
        *,
        id: UUID,
        tenant_id: UUID,
        bot_id: UUID,
        kind: str,
        uri: str,
        content_hash: str | None = None,
        status: SourceStatus = SourceStatus.QUEUED,
    ) -> None:
        self.id = id
        self.tenant_id = tenant_id
        self.bot_id = bot_id
        self.kind = kind  # file | url
        self.uri = uri
        self._content_hash = content_hash
        self._status = status

    @property
    def status(self) -> SourceStatus:
        return self._status

    @property
    def content_hash(self) -> str | None:
        return self._content_hash

    # queued -> processing.
    def start_processing(self) -> None:
        self._transition(SourceStatus.PROCESSING)

    # processing -> ready, remembering the file's fingerprint.
    def mark_ready(self, content_hash: str) -> None:
        self._transition(SourceStatus.READY)
        self._content_hash = content_hash

    # processing -> failed.
    def mark_failed(self) -> None:
        self._transition(SourceStatus.FAILED)

    # ready/failed -> queued again.
    def requeue(self) -> None:
        self._transition(SourceStatus.QUEUED)

    # Same fingerprint as last time? Then there's nothing to redo.
    def is_unchanged(self, new_hash: str) -> bool:
        """P2.8: re-uploading an identical file must create zero new chunks."""
        return self._content_hash == new_hash

    # The single place where status changes; illegal moves -> 409 conflict.
    def _transition(self, new: SourceStatus) -> None:
        if new not in _ALLOWED[self._status]:
            raise ConflictError(f"source cannot go from {self._status} to {new}")
        self._status = new
