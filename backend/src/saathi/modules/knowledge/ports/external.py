# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The contracts the knowledge use cases need from 'outside': putting an ingestion job on
#       the background queue, checking that a bot exists, and finding out which chunking
#       settings a bot uses.
# Note: Bots and their published configuration are owned by the tenancy module. Knowledge never
#       imports tenancy (R4); bootstrap/ plugs in readers backed by tenancy.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Queue, bot-directory and bot-settings ports for the knowledge module."""

# From collections.abc — standard type names: Awaitable = something you can `await`;
#   Callable = a function type.
from collections.abc import Awaitable, Callable

# From typing — type-hint helpers: Protocol = an interface: any class with these methods fits.
from typing import Protocol

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From saathi.modules.knowledge.domain.chunking — chunking rules: ChunkingPolicy = size+overlap.
from saathi.modules.knowledge.domain.chunking import ChunkingPolicy


# Contract: ask the worker to (re)process one source.
class IngestQueue(Protocol):
    # Queue an ingestion job. Implementations used inside a request queue it only AFTER the
    #   transaction commits; jobs must tolerate a source that changed or disappeared meanwhile.
    async def enqueue_ingest(self, tenant_id: UUID, source_id: UUID) -> None: ...


# Contract: which chunking settings a bot uses right now.
class ChunkingPolicySource(Protocol):
    # The bot's published chunking settings (platform defaults if nothing is published yet).
    async def policy_for(self, tenant_id: UUID, bot_id: UUID) -> ChunkingPolicy: ...


# Contract: does this bot exist for this tenant?
class BotDirectory(Protocol):
    # True only if the bot exists AND belongs to the tenant (another tenant's bot -> False -> 404).
    async def exists(self, tenant_id: UUID, bot_id: UUID) -> bool: ...


# Contract: run some work only after the current transaction commits (e.g. delete a stored file
#   once its database row is really gone). platform.db.AfterCommit fits this contract.
class PostCommitActions(Protocol):
    # Register a no-argument async function to run after COMMIT (never after a rollback).
    def add(self, callback: Callable[[], Awaitable[None]]) -> None: ...
