"""Knowledge domain. Source is an aggregate: its state changes only through intention-revealing
methods, so the lifecycle rules cannot be bypassed by assigning a field.
"""

from enum import StrEnum
from uuid import UUID

from saathi.platform.errors import ConflictError


class SourceStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


_ALLOWED: dict[SourceStatus, frozenset[SourceStatus]] = {
    SourceStatus.QUEUED: frozenset({SourceStatus.PROCESSING}),
    SourceStatus.PROCESSING: frozenset({SourceStatus.READY, SourceStatus.FAILED}),
    SourceStatus.READY: frozenset({SourceStatus.QUEUED}),  # re-sync
    SourceStatus.FAILED: frozenset({SourceStatus.QUEUED}),  # retry
}


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

    def start_processing(self) -> None:
        self._transition(SourceStatus.PROCESSING)

    def mark_ready(self, content_hash: str) -> None:
        self._transition(SourceStatus.READY)
        self._content_hash = content_hash

    def mark_failed(self) -> None:
        self._transition(SourceStatus.FAILED)

    def requeue(self) -> None:
        self._transition(SourceStatus.QUEUED)

    def is_unchanged(self, new_hash: str) -> bool:
        """P2.8: re-uploading an identical file must create zero new chunks."""
        return self._content_hash == new_hash

    def _transition(self, new: SourceStatus) -> None:
        if new not in _ALLOWED[self._status]:
            raise ConflictError(f"source cannot go from {self._status} to {new}")
        self._status = new
