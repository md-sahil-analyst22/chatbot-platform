# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The knowledge web endpoints (P2.1, P2.4, P2.8, P2.12). Login required (/api/v1).
#   POST   /bots/{bot_id}/sources/upload          upload a file -> 202, processed in background
#   POST   /bots/{bot_id}/sources/crawl           add a website  -> 202, crawled in background
#   GET    /bots/{bot_id}/sources                 list with status and chunk count
#   GET    /bots/{bot_id}/sources/{id}            one source
#   POST   /bots/{bot_id}/sources/{id}/resync     process again  -> 202
#   DELETE /bots/{bot_id}/sources/{id}            delete source, chunks and stored file -> 204
#   GET    /bots/{bot_id}/faqs                    list FAQs
#   POST   /bots/{bot_id}/faqs                    add an FAQ (question is embedded) -> 201
#   PATCH  /bots/{bot_id}/faqs/{id}               change / switch on-off
#   DELETE /bots/{bot_id}/faqs/{id}               delete -> 204
# Thin: translate HTTP <-> service calls. 🔒 Uploads: the request size is checked BEFORE the
#   body is read (BodySizeLimitMiddleware in api/middleware.py); the file type is checked by its
#   bytes in the service.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Knowledge endpoints (Phase 2)."""

# From typing — type-hint helpers: Annotated = a type plus extra info.
from typing import Annotated

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From fastapi — the web framework: APIRouter = a group of endpoints; File = a multipart file
#   field; Query = a ?query parameter; UploadFile = an uploaded file; status = HTTP status codes.
from fastapi import APIRouter, File, Query, UploadFile, status

# From saathi.api.deps — shared dependencies: PrincipalDep = the verified caller.
from saathi.api.deps import PrincipalDep

# From saathi.modules.knowledge.api.deps — services: FaqServiceDep, SourceServiceDep.
from saathi.modules.knowledge.api.deps import FaqServiceDep, SourceServiceDep

# From saathi.modules.knowledge.api.schemas — JSON shapes.
from saathi.modules.knowledge.api.schemas import (
    CrawlIn,
    FaqIn,
    FaqOut,
    FaqUpdate,
    SourceOut,
)

# From saathi.modules.knowledge.domain.crawl — crawl settings: CrawlOptions.
from saathi.modules.knowledge.domain.crawl import CrawlOptions

# From saathi.modules.knowledge.domain.entities — sources: Source = one document/site.
from saathi.modules.knowledge.domain.entities import Source

# From saathi.modules.knowledge.domain.faq — FAQ entity: Faq.
from saathi.modules.knowledge.domain.faq import Faq

# From saathi.modules.knowledge.ports.repositories — storage contracts: SourceListing.
from saathi.modules.knowledge.ports.repositories import SourceListing

# From saathi.platform.security.uploads — upload limits: MAX_DOCUMENT_BYTES = 20 MB.
from saathi.platform.security.uploads import MAX_DOCUMENT_BYTES

# All knowledge endpoints live under one bot.
router = APIRouter(prefix="/bots/{bot_id}", tags=["knowledge"])


# Domain source -> response.
def _source_out(source: Source, listing: SourceListing | None = None) -> SourceOut:
    # Crawl settings for websites.
    crawl = source.crawl
    # Build the response (no storage key; validated against the response schema).
    return SourceOut.model_validate(
        {
            "id": source.id,
            "kind": source.kind,
            "title": source.title,
            "status": source.status.value,
            "error": source.error,
            "crawl": {
                "url": crawl.root_url,
                "max_depth": crawl.max_depth,
                "max_pages": crawl.max_pages,
                "include_patterns": list(crawl.include_patterns),
                "exclude_patterns": list(crawl.exclude_patterns),
            }
            if crawl
            else None,
            "chunk_count": listing.chunk_count if listing else None,
            "created_at": listing.created_at if listing else None,
            "synced_at": listing.synced_at if listing else None,
        }
    )


# Domain FAQ -> response.
def _faq_out(faq: Faq) -> FaqOut:
    # Public fields of an FAQ.
    return FaqOut(id=faq.id, question=faq.question, answer=faq.answer, is_active=faq.is_active)


# P2.1: upload a document.
@router.post("/sources/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_source(
    bot_id: UUID,
    principal: PrincipalDep,
    service: SourceServiceDep,
    file: Annotated[UploadFile, File(description="pdf, docx, xlsx, csv, txt or md (max 20 MB)")],
) -> SourceOut:
    # Read at most limit + 1 bytes (the service refuses anything over the limit).
    data = await file.read(MAX_DOCUMENT_BYTES + 1)
    # Hand over to the use case.
    return _source_out(await service.upload(principal, bot_id, file.filename or "", data))


# P2.4: add a website.
@router.post("/sources/crawl", status_code=status.HTTP_202_ACCEPTED)
async def crawl_source(
    bot_id: UUID, body: CrawlIn, principal: PrincipalDep, service: SourceServiceDep
) -> SourceOut:
    # Build the (validated) crawl settings.
    options = CrawlOptions(
        root_url=body.url,
        max_depth=body.max_depth,
        max_pages=body.max_pages,
        include_patterns=tuple(body.include_patterns),
        exclude_patterns=tuple(body.exclude_patterns),
    )
    # Hand over to the use case.
    return _source_out(await service.add_website(principal, bot_id, options))


# List a bot's sources.
@router.get("/sources")
async def list_sources(
    bot_id: UUID,
    principal: PrincipalDep,
    service: SourceServiceDep,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[SourceOut]:
    # Each listing -> response.
    return [
        _source_out(item.source, item)
        for item in await service.list_sources(principal, bot_id, limit)
    ]


# One source.
@router.get("/sources/{source_id}")
async def get_source(
    bot_id: UUID, source_id: UUID, principal: PrincipalDep, service: SourceServiceDep
) -> SourceOut:
    # Hand over to the use case.
    return _source_out(await service.get_source(principal, bot_id, source_id))


# P2.8: process a source again.
@router.post("/sources/{source_id}/resync", status_code=status.HTTP_202_ACCEPTED)
async def resync_source(
    bot_id: UUID, source_id: UUID, principal: PrincipalDep, service: SourceServiceDep
) -> SourceOut:
    # Hand over to the use case.
    return _source_out(await service.resync(principal, bot_id, source_id))


# Delete a source.
@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    bot_id: UUID, source_id: UUID, principal: PrincipalDep, service: SourceServiceDep
) -> None:
    # Hand over to the use case.
    await service.delete(principal, bot_id, source_id)


# List a bot's FAQs.
@router.get("/faqs")
async def list_faqs(
    bot_id: UUID,
    principal: PrincipalDep,
    service: FaqServiceDep,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[FaqOut]:
    # Each FAQ -> response.
    return [_faq_out(f) for f in await service.list_faqs(principal, bot_id, limit)]


# Add an FAQ.
@router.post("/faqs", status_code=status.HTTP_201_CREATED)
async def create_faq(
    bot_id: UUID, body: FaqIn, principal: PrincipalDep, service: FaqServiceDep
) -> FaqOut:
    # Hand over to the use case.
    return _faq_out(await service.create(principal, bot_id, body.question, body.answer))


# Change an FAQ.
@router.patch("/faqs/{faq_id}")
async def update_faq(
    bot_id: UUID, faq_id: UUID, body: FaqUpdate, principal: PrincipalDep, service: FaqServiceDep
) -> FaqOut:
    # Only the fields sent are changed.
    return _faq_out(
        await service.update(
            principal,
            bot_id,
            faq_id,
            question=body.question,
            answer=body.answer,
            is_active=body.is_active,
        )
    )


# Delete an FAQ.
@router.delete("/faqs/{faq_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_faq(
    bot_id: UUID, faq_id: UUID, principal: PrincipalDep, service: FaqServiceDep
) -> None:
    # Hand over to the use case.
    await service.delete(principal, bot_id, faq_id)
