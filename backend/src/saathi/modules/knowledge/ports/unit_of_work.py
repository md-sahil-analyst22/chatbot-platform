# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The contract for 'open one short database transaction for one tenant and give me the
#       repositories inside it'. Used by the background ingestion job, which must NOT keep a
#       transaction open while it downloads, parses and embeds (that can take a minute).
# How it's used:
#     async with uow(tenant_id) as repos:      # transaction starts, tenant bound (RLS)
#         source = await repos.sources.get_for_update(...)
#     # leaving the block commits (or rolls back on an error)
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Unit-of-work port for multi-step background use cases."""

# From contextlib — context-manager helpers: AbstractAsyncContextManager = the type of
#   something used with `async with`.
from contextlib import AbstractAsyncContextManager

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you.
from dataclasses import dataclass

# From typing — type-hint helpers: Protocol = an interface: any class with these methods fits.
from typing import Protocol

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From saathi.modules.knowledge.ports.external — outside needs: ChunkingPolicySource = which
#   chunking settings a bot uses.
from saathi.modules.knowledge.ports.external import ChunkingPolicySource

# From saathi.modules.knowledge.ports.repositories — storage contracts: ChunkRepository = chunks;
#   SourceRepository = sources.
from saathi.modules.knowledge.ports.repositories import ChunkRepository, SourceRepository


# @dataclass writes __init__ for us; frozen=True means objects can't be changed after creation.
@dataclass(frozen=True, slots=True)
# The repositories available inside one transaction.
class IngestionRepositories:
    # Sources.
    sources: SourceRepository
    # Chunks.
    chunks: ChunkRepository
    # The bot's chunking settings (read in the same transaction).
    policies: ChunkingPolicySource


# Contract: open a tenant-bound transaction.
class IngestionUnitOfWork(Protocol):
    # Calling it with a tenant gives an `async with` block; the block's end commits.
    def __call__(self, tenant_id: UUID) -> AbstractAsyncContextManager[IngestionRepositories]: ...
