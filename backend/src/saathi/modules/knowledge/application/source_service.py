# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The things a tenant can do with a bot's knowledge sources (P2.1, P2.4, P2.8):
#   upload a file, add a website, list sources, look at one, re-sync one, delete one.
#   BotResyncService (below) is the system action: re-queue all of a bot's sources after its
#   chunking settings change.
# Rules:
#   🔒 the tenant always comes from the verified login (principal), never from the request (R8);
#   🔒 admins change things, viewers only look (R16);
#   re-uploading a file with the same name REPLACES that source (same storage key): the worker's
#   fingerprint check then creates zero new chunks if the content is unchanged (P2.8);
#   jobs are queued through IngestQueue, which (inside a request) only sends them after commit.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Source use cases (upload, crawl, list, resync, delete)."""

# From uuid — unique ids (UUIDs): UUID = the unique-id type; uuid4 = make a new random id.
from uuid import UUID, uuid4

# From saathi.modules.knowledge.domain.crawl — crawl settings: CrawlOptions = one crawl's
#   settings.
from saathi.modules.knowledge.domain.crawl import CrawlOptions

# From saathi.modules.knowledge.domain.entities — sources: Source = one document/site;
#   SourceKind = file or url; SourceStatus = its life-cycle states.
from saathi.modules.knowledge.domain.entities import Source, SourceKind, SourceStatus

# From saathi.modules.knowledge.ports.external — outside needs: BotDirectory = does the bot
#   exist; IngestQueue = put a job on the queue; PostCommitActions = work after COMMIT.
from saathi.modules.knowledge.ports.external import BotDirectory, IngestQueue, PostCommitActions

# From saathi.modules.knowledge.ports.repositories — storage contracts: SourceListing = source +
#   bookkeeping; SourceRepository = sources.
from saathi.modules.knowledge.ports.repositories import SourceListing, SourceRepository

# From saathi.platform.errors — our error types: ConflictError = 409; NotFoundError = 404.
from saathi.platform.errors import ConflictError, NotFoundError

# From saathi.platform.security.auth — who is calling: Principal = verified user + tenant + role;
#   Role = owner/admin/viewer; require_role = 403 unless the role is high enough.
from saathi.platform.security.auth import Principal, Role, require_role

# From saathi.platform.security.uploads — upload checks: validate_document = check by real bytes.
from saathi.platform.security.uploads import validate_document

# From saathi.platform.storage — file storage contract: ObjectStore = save/read files.
from saathi.platform.storage import ObjectStore

# At most 100 sources per list call (R28: bounded lists).
MAX_LIST = 100


# The storage key of an uploaded file: tenant-prefixed, one key per (bot, file name).
def document_key(tenant_id: UUID, bot_id: UUID, safe_name: str) -> str:
    """'t/{tenant}/bots/{bot}/files/{name}'. Same name again = same key = same source."""
    # 🔒 Always starts with the tenant (platform/storage rule), so tenants' files never mix.
    return f"t/{tenant_id}/bots/{bot_id}/files/{safe_name}"


# The use cases.
class SourceService:
    # Receive every collaborator through the constructor (R21).
    def __init__(
        self,
        *,
        sources: SourceRepository,
        bots: BotDirectory,
        store: ObjectStore,
        queue: IngestQueue,
        post_commit: PostCommitActions,
    ) -> None:
        # Source storage.
        self._sources = sources
        # Bot existence check.
        self._bots = bots
        # Private document storage.
        self._store = store
        # Background job queue.
        self._queue = queue
        # Work that must wait for the commit (stored-file deletion).
        self._post_commit = post_commit

    # 404 unless the bot exists for the caller's tenant (another tenant's bot -> 404, R29).
    async def _require_bot(self, principal: Principal, bot_id: UUID) -> None:
        # Ask the bot directory.
        if not await self._bots.exists(principal.tenant_id, bot_id):
            # 404.
            raise NotFoundError("bot not found")

    # Load one of the caller's sources of this bot, or 404.
    async def _require_source(self, principal: Principal, bot_id: UUID, source_id: UUID) -> Source:
        # Filtered by tenant (R15).
        source = await self._sources.get(principal.tenant_id, source_id)
        # Missing, another tenant's, or another bot's (all look the same: 404, R29).
        if source is None or source.bot_id != bot_id:
            # 404.
            raise NotFoundError("source not found")
        # Found.
        return source

    # P2.1: upload a file -> storage -> source row (queued) -> job after commit.
    async def upload(
        self, principal: Principal, bot_id: UUID, filename: str, data: bytes
    ) -> Source:
        # Admins only.
        require_role(principal, Role.ADMIN)
        # 🔒 Check the file by its real bytes first (422 for anything we won't parse).
        info = validate_document(data, filename)
        # The bot must be the caller's.
        await self._require_bot(principal, bot_id)
        # Deterministic, tenant-prefixed key.
        key = document_key(principal.tenant_id, bot_id, info.safe_name)
        # Same name uploaded before? Then this replaces it.
        existing = await self._find_by_uri(principal, bot_id, key)
        # A file that is being processed right now can't be swapped under the worker.
        if existing is not None and existing.status is SourceStatus.PROCESSING:
            # 409: try again shortly.
            raise ConflictError("this file is being processed; try again in a minute")
        # Save the bytes (private bucket). Done before commit: the job only runs after commit.
        await self._store.put(key, data, info.content_type)
        # Replacing: move the existing source back to the queue (ready/failed -> queued).
        if existing is not None:
            # Already queued: nothing to change, just make sure a job runs.
            if existing.status is not SourceStatus.QUEUED:
                # Back to queued.
                existing.requeue()
                # Save it.
                await self._sources.save(existing)
            # Queue a job (after commit).
            await self._queue.enqueue_ingest(principal.tenant_id, existing.id)
            # The replaced source.
            return existing
        # A new source, queued.
        source = Source(
            id=uuid4(),
            tenant_id=principal.tenant_id,  # 🔒 from the token, never from the request (R8)
            bot_id=bot_id,
            kind=SourceKind.FILE,
            uri=key,
            title=filename.strip()[:300] or info.safe_name,
        )
        # Save it (409 if the same name was added concurrently).
        await self._sources.add(source)
        # Queue the job (after commit).
        await self._queue.enqueue_ingest(principal.tenant_id, source.id)
        # The new source.
        return source

    # P2.4: add (or update) a website source.
    async def add_website(
        self, principal: Principal, bot_id: UUID, options: CrawlOptions
    ) -> Source:
        # Admins only.
        require_role(principal, Role.ADMIN)
        # The bot must be the caller's.
        await self._require_bot(principal, bot_id)
        # The same start address added before?
        existing = await self._find_by_uri(principal, bot_id, options.root_url)
        # Re-adding an existing site: refuse while it is being crawled.
        if existing is not None:
            # Same rule as for files.
            raise ConflictError("this website is already a source; use re-sync to refresh it")
        # A new website source.
        source = Source(
            id=uuid4(),
            tenant_id=principal.tenant_id,  # 🔒 from the token (R8)
            bot_id=bot_id,
            kind=SourceKind.URL,
            uri=options.root_url,
            title=options.root_url,
            crawl=options,
        )
        # Save it (409 on a concurrent duplicate).
        await self._sources.add(source)
        # Queue the job (after commit).
        await self._queue.enqueue_ingest(principal.tenant_id, source.id)
        # The new source.
        return source

    # A bot's sources with their status, newest first.
    async def list_sources(
        self, principal: Principal, bot_id: UUID, limit: int = 50
    ) -> list[SourceListing]:
        # Viewers may look.
        require_role(principal, Role.VIEWER)
        # The bot must be the caller's (404 otherwise, even for an empty list).
        await self._require_bot(principal, bot_id)
        # Bounded list (R28).
        return await self._sources.list_for_bot(principal.tenant_id, bot_id, min(limit, MAX_LIST))

    # One source.
    async def get_source(self, principal: Principal, bot_id: UUID, source_id: UUID) -> Source:
        # Viewers may look.
        require_role(principal, Role.VIEWER)
        # 404 if missing or another tenant's/bot's.
        return await self._require_source(principal, bot_id, source_id)

    # P2.8: process a source again (e.g. the website changed, or a failure was fixed).
    async def resync(self, principal: Principal, bot_id: UUID, source_id: UUID) -> Source:
        # Admins only.
        require_role(principal, Role.ADMIN)
        # 404 if missing or another tenant's/bot's.
        source = await self._require_source(principal, bot_id, source_id)
        # Being processed right now: nothing to do yet.
        if source.status is SourceStatus.PROCESSING:
            # 409.
            raise ConflictError("this source is being processed right now")
        # Ready/failed -> queued (queued stays queued: its job may have been lost, so the job is
        #   simply sent again; the worker ignores duplicates).
        if source.status is not SourceStatus.QUEUED:
            # Back to queued.
            source.requeue()
            # Save it.
            await self._sources.save(source)
        # Queue the job (after commit).
        await self._queue.enqueue_ingest(principal.tenant_id, source.id)
        # The source.
        return source

    # Delete a source, its chunks (database cascade) and its stored file.
    async def delete(self, principal: Principal, bot_id: UUID, source_id: UUID) -> None:
        # Admins only.
        require_role(principal, Role.ADMIN)
        # 404 if missing or another tenant's/bot's.
        source = await self._require_source(principal, bot_id, source_id)
        # Delete the row (chunks go with it). A running job notices and stops.
        if not await self._sources.delete(principal.tenant_id, source_id):
            # Deleted concurrently.
            raise NotFoundError("source not found")
        # Uploaded files: remove the stored bytes once the delete has committed (a rollback
        #   keeps both). If that removal fails, it is logged; the orphan file is never served.
        if source.kind == SourceKind.FILE:
            # The storage key.
            key = source.uri

            # The deferred deletion.
            async def remove_file() -> None:
                # Delete the stored bytes.
                await self._store.delete(key)

            # Run it after commit.
            self._post_commit.add(remove_file)

    # Find a bot's source by its uri (storage key or URL).
    async def _find_by_uri(self, principal: Principal, bot_id: UUID, uri: str) -> Source | None:
        # One lookup, served by the (tenant_id, bot_id, uri) unique index.
        return await self._sources.get_by_uri(principal.tenant_id, bot_id, uri)


# System action, kept separate from SourceService because it needs only sources + queue (no
#   file storage), so publishing a config never depends on storage being configured.
class BotResyncService:
    # Receive the collaborators through the constructor (R21).
    def __init__(self, *, sources: SourceRepository, queue: IngestQueue) -> None:
        # Source storage.
        self._sources = sources
        # Background job queue.
        self._queue = queue

    # System action (no principal): after a publish changed a bot's chunking settings, queue
    #   every source of the bot again. The caller (publish) already checked the admin role and
    #   runs this inside the same transaction.
    async def requeue_bot(self, tenant_id: UUID, bot_id: UUID) -> int:
        """Ready/failed sources go back to queued. Queued ones will pick up the new settings when
        claimed, and processing ones re-queue themselves when they finish. Returns how many."""
        # Count of sources queued again.
        count = 0
        # Every source of the bot, locked so a worker can't change them meanwhile.
        for source in await self._sources.all_for_bot_for_update(tenant_id, bot_id):
            # Only finished ones need a new job.
            if source.status in (SourceStatus.READY, SourceStatus.FAILED):
                # Back to queued.
                source.requeue()
                # Save it.
                await self._sources.save(source)
                # Queue it (after commit).
                await self._queue.enqueue_ingest(tenant_id, source.id)
                # Count it.
                count += 1
        # How many were queued.
        return count
