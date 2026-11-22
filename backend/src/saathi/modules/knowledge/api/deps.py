# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Builds the knowledge use-case services for each request from their adapters (R6: the
#       only file in this module's api/ allowed to import adapters). Routes ask for services.
# Where things come from:
#   - the tenant-bound DB session and the after-commit list: saathi.api.deps;
#   - the job queue pool: saathi.api.deps (created by the container);
#   - things owned by other modules or chosen by configuration (bot lookup backed by tenancy,
#     the document store, the embedder): app.state, filled by main.py from bootstrap/.
#     This file never imports bootstrap/ (R5) or another module (R4).
# Tests: override get_source_service / get_faq_service with in-memory fakes.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Module-level wiring for the knowledge HTTP layer."""

# From collections.abc — standard type names: Callable = a function type.
from collections.abc import Callable

# From typing — type-hint helpers: Annotated = a type plus extra info; Any = any type.
from typing import Annotated, Any

# From fastapi — the web framework: Depends = 'FastAPI, please supply this'; Request = the
#   incoming request (gives access to app.state).
from fastapi import Depends, Request

# From sqlalchemy.ext.asyncio — async database sessions: AsyncSession = one session.
from sqlalchemy.ext.asyncio import AsyncSession

# From saathi.api.deps — shared dependencies: AfterCommitDep = the request's after-commit list;
#   TenantDbDep = tenant-bound session; get_job_pool = the ARQ pool.
from saathi.api.deps import AfterCommitDep, TenantDbDep, get_job_pool

# From saathi.modules.knowledge.adapters.arq_queue — job queue adapter: ArqIngestQueue.
from saathi.modules.knowledge.adapters.arq_queue import ArqIngestQueue

# From saathi.modules.knowledge.adapters.faq_repository — SQL FAQs: SqlAlchemyFaqRepository.
from saathi.modules.knowledge.adapters.faq_repository import SqlAlchemyFaqRepository

# From saathi.modules.knowledge.adapters.source_repository — SQL sources:
#   SqlAlchemySourceRepository.
from saathi.modules.knowledge.adapters.source_repository import SqlAlchemySourceRepository

# From saathi.modules.knowledge.application.faq_service — FAQ use cases: FaqService.
from saathi.modules.knowledge.application.faq_service import FaqService

# From saathi.modules.knowledge.application.source_service — source use cases: SourceService.
from saathi.modules.knowledge.application.source_service import SourceService

# From saathi.modules.knowledge.ports.external — outside needs: BotDirectory = does a bot exist.
from saathi.modules.knowledge.ports.external import BotDirectory

# From saathi.modules.knowledge.ports.providers — vendor contracts: Embedder = text -> vectors.
from saathi.modules.knowledge.ports.providers import Embedder

# From saathi.platform.storage — file storage contract: ObjectStore = save/read files.
from saathi.platform.storage import ObjectStore

# app.state.knowledge_bot_directory: builds a BotDirectory on the request's session.
BotDirectoryFactory = Callable[[AsyncSession], BotDirectory]
# app.state.document_store: returns the private document store (raises if not configured).
DocumentStoreProvider = Callable[[], ObjectStore]
# app.state.embedder: returns the platform embedder (raises if not configured).
EmbedderProvider = Callable[[], Embedder]


# The bot directory for this request's session.
def _bot_directory(request: Request, session: AsyncSession) -> BotDirectory:
    # The factory published by main.py (backed by tenancy, wired in bootstrap/).
    factory: BotDirectoryFactory = request.app.state.knowledge_bot_directory
    # Built on the same tenant-bound session.
    return factory(session)


# Build SourceService for one request.
async def get_source_service(
    request: Request,
    db: TenantDbDep,
    after_commit: AfterCommitDep,
    pool: Annotated[Any, Depends(get_job_pool)],
) -> SourceService:
    # The private document store (fails closed with ConfigurationError if not configured).
    store_provider: DocumentStoreProvider = request.app.state.document_store
    # Wire the service.
    return SourceService(
        sources=SqlAlchemySourceRepository(db),
        bots=_bot_directory(request, db),
        store=store_provider(),
        queue=ArqIngestQueue(pool, after_commit),  # jobs sent only after commit
        post_commit=after_commit,
    )


# Build FaqService for one request.
async def get_faq_service(request: Request, db: TenantDbDep) -> FaqService:
    # The platform embedder (fails closed with ConfigurationError if not configured).
    embedder_provider: EmbedderProvider = request.app.state.embedder
    # Wire the service.
    return FaqService(
        faqs=SqlAlchemyFaqRepository(db),
        bots=_bot_directory(request, db),
        embedder=embedder_provider(),
    )


# Short names used by the routes.
SourceServiceDep = Annotated[SourceService, Depends(get_source_service)]
# Short name for the FAQ service.
FaqServiceDep = Annotated[FaqService, Depends(get_faq_service)]
