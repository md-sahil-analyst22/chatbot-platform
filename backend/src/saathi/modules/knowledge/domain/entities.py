# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: A 'Source' = one document or website a bot learns from, and its life cycle.
# Life cycle: queued -> processing -> ready or failed; ready/failed can be queued again (re-sync
#             / retry). Any other jump is refused.
# Pattern: A small 'state machine': the object protects its own rules.
# Fingerprint: after a successful run the source remembers a fingerprint of (content + chunking
#              settings + embedding model). Same fingerprint next time = nothing to redo (P2.8).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Knowledge domain. Source is an aggregate: its state changes only through intention-revealing
methods, so the lifecycle rules cannot be bypassed by assigning a field.
"""

# From enum — fixed sets of named values: StrEnum = a fixed set of named text values.
from enum import StrEnum

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From saathi.modules.knowledge.domain.crawl — crawl settings: CrawlOptions = one crawl's settings.
from saathi.modules.knowledge.domain.crawl import CrawlOptions

# From saathi.platform.errors — our error types: ConflictError = 409 clash with existing data;
#   ValidationError = 422 invalid input.
from saathi.platform.errors import ConflictError, ValidationError

# Longest failure reason we store (the column is 500 characters).
MAX_ERROR_CHARS = 500
# Longest display title we store (the column is 300 characters).
MAX_TITLE_CHARS = 300


# The possible states of a source.
class SourceStatus(StrEnum):
    # Waiting for the worker.
    QUEUED = "queued"
    # Being read, split and embedded right now.
    PROCESSING = "processing"
    # Done: the bot can answer from it.
    READY = "ready"
    # Something went wrong; can be retried.
    FAILED = "failed"


# Where a source comes from.
class SourceKind(StrEnum):
    # An uploaded file (uri = storage key).
    FILE = "file"
    # A website crawl (uri = the root/sitemap URL).
    URL = "url"


# Which state may follow which. Everything not listed is forbidden.
_ALLOWED: dict[SourceStatus, frozenset[SourceStatus]] = {
    # queued may only become processing;
    SourceStatus.QUEUED: frozenset({SourceStatus.PROCESSING}),
    # processing may become ready or failed;
    SourceStatus.PROCESSING: frozenset({SourceStatus.READY, SourceStatus.FAILED}),
    SourceStatus.READY: frozenset({SourceStatus.QUEUED}),  # re-sync
    SourceStatus.FAILED: frozenset({SourceStatus.QUEUED}),  # retry
}


# One document/website. Its status can only change through the methods below.
class Source:
    # Fixed list of attributes (saves memory, prevents typos creating new ones).
    __slots__ = (
        "_content_hash",
        "_error",
        "_status",
        "bot_id",
        "crawl",
        "id",
        "kind",
        "tenant_id",
        "title",
        "uri",
    )

    # Create a Source with (all by name, thanks to the '*'):
    def __init__(
        # self = this object itself (Python passes it in automatically).
        self,
        # Everything after '*' must be passed by name, e.g. api_key=...
        *,
        # the source's id,
        id: UUID,
        # 🔒 the owning workspace,
        tenant_id: UUID,
        # the bot it belongs to,
        bot_id: UUID,
        # file or url,
        kind: str,
        # where it lives (storage path or web address),
        uri: str,
        # its fingerprint (none until processed),
        content_hash: str | None = None,
        # its status (default queued),
        status: SourceStatus = SourceStatus.QUEUED,
        # a display name (original file name or page title), optional,
        title: str | None = None,
        # the safe reason of the last failure, if any,
        error: str | None = None,
        # the crawl settings (website sources only).
        crawl: CrawlOptions | None = None,
    ) -> None:
        # Only the two known kinds.
        if kind not in (SourceKind.FILE, SourceKind.URL):
            # 422.
            raise ValidationError("source kind must be 'file' or 'url'")
        # A location is required.
        if not uri:
            # 422.
            raise ValidationError("source uri must not be empty")
        # A website source needs crawl settings; a file never has them.
        if (kind == SourceKind.URL) != (crawl is not None):
            # 422.
            raise ValidationError("crawl settings are required for website sources only")
        # Store the id.
        self.id = id
        # Store the tenant.
        self.tenant_id = tenant_id
        # Store the bot.
        self.bot_id = bot_id
        self.kind = kind  # file | url
        # Store the location.
        self.uri = uri
        # Store the crawl settings (immutable value object).
        self.crawl = crawl
        # Store the title, shortened to what the column holds.
        self.title = title[:MAX_TITLE_CHARS] if title else None
        # Store the fingerprint (leading '_' = private: change it only through methods).
        self._content_hash = content_hash
        # Store the status (private as well).
        self._status = status
        # Store the last failure reason (private as well).
        self._error = error

    # @property: read-only from outside (source.status).
    @property
    # The current status...
    def status(self) -> SourceStatus:
        # ...returned as-is.
        return self._status

    # Read-only as well.
    @property
    # The current fingerprint...
    def content_hash(self) -> str | None:
        # ...returned as-is.
        return self._content_hash

    # Read-only as well.
    @property
    # The last failure reason (None after a success)...
    def error(self) -> str | None:
        # ...returned as-is.
        return self._error

    # queued -> processing.
    def start_processing(self) -> None:
        # Move to processing (only allowed from queued).
        self._transition(SourceStatus.PROCESSING)

    # processing -> ready, remembering the fingerprint.
    def mark_ready(self, content_hash: str) -> None:
        # Move to ready (only allowed from processing)...
        self._transition(SourceStatus.READY)
        # ...remember the fingerprint...
        self._content_hash = content_hash
        # ...and forget any earlier failure.
        self._error = None

    # processing -> failed, with a SAFE reason (shown to the tenant; never a stack trace).
    def mark_failed(self, reason: str = "processing failed") -> None:
        # Move to failed (only allowed from processing).
        self._transition(SourceStatus.FAILED)
        # Keep a bounded reason.
        self._error = reason[:MAX_ERROR_CHARS]

    # ready/failed -> queued again.
    def requeue(self) -> None:
        # Move back to queued (allowed from ready or failed).
        self._transition(SourceStatus.QUEUED)

    # Same fingerprint as last time? Then there's nothing to redo.
    def is_unchanged(self, new_hash: str) -> bool:
        """P2.8: re-uploading an identical file must create zero new chunks."""
        # Same fingerprint = nothing changed.
        return self._content_hash == new_hash

    # The single place where status changes; illegal moves -> 409 conflict.
    def _transition(self, new: SourceStatus) -> None:
        # This move isn't in the allowed list...
        if new not in _ALLOWED[self._status]:
            # ...so refuse with 409.
            raise ConflictError(f"source cannot go from {self._status} to {new}")
        # Allowed: change the status.
        self._status = new
