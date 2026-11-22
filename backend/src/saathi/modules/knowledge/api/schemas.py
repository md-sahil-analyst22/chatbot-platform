# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The JSON shapes going in and out of the knowledge endpoints (sources and FAQs).
# Rules: requests reject unknown fields (a smuggled tenant_id -> 422, R8/R19) and every text and
#   list has a maximum size (R28). Responses never include storage paths or internal settings.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Request/response schemas for /api/v1 knowledge endpoints."""

# From datetime — dates and times: datetime = a date + time value.
from datetime import datetime

# From typing — type-hint helpers: Annotated = a type with extra rules attached; Literal = only
#   these exact values.
from typing import Annotated, Literal

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From pydantic — checks data against declared types and rules: BaseModel = parent class for
#   request/response shapes; ConfigDict = model options such as extra='forbid'; Field = per-field
#   rules; model_validator = a check across several fields.
from pydantic import BaseModel, ConfigDict, Field, model_validator

# A path pattern: starts with '/', at most 200 characters.
PathPattern = Annotated[str, Field(min_length=1, max_length=200, pattern=r"^/")]


# Parent of every request shape.
class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")  # reject unknown fields (e.g. a smuggled tenant_id)


# Body of POST /bots/{bot_id}/sources/crawl.
class CrawlIn(_Strict):
    # The start page or sitemap address.
    url: str = Field(min_length=8, max_length=2000, pattern=r"^https?://")
    # How many clicks away from the start page.
    max_depth: int = Field(default=1, ge=0, le=3)
    # Page budget.
    max_pages: int = Field(default=50, ge=1, le=200)
    # Only these paths ('/services/*'); empty = all.
    include_patterns: list[PathPattern] = Field(default_factory=list, max_length=20)
    # Skip these paths ('/blog/*').
    exclude_patterns: list[PathPattern] = Field(default_factory=list, max_length=20)


# Crawl settings in responses.
class CrawlOut(BaseModel):
    # The start address.
    url: str
    # Depth.
    max_depth: int
    # Page budget.
    max_pages: int
    # Include patterns.
    include_patterns: list[str]
    # Exclude patterns.
    exclude_patterns: list[str]


# One source in responses.
class SourceOut(BaseModel):
    # Its id.
    id: UUID
    # file or url.
    kind: Literal["file", "url"]
    # Display name (original file name or website address).
    title: str | None
    # queued / processing / ready / failed.
    status: Literal["queued", "processing", "ready", "failed"]
    # Safe failure reason (None unless failed or retrying).
    error: str | None
    # Crawl settings (website sources only).
    crawl: CrawlOut | None = None
    # Number of chunks (list responses only).
    chunk_count: int | None = None
    # When it was added (list responses only).
    created_at: datetime | None = None
    # When it last finished processing (list responses only).
    synced_at: datetime | None = None


# Body of POST /bots/{bot_id}/faqs.
class FaqIn(_Strict):
    # The question customers ask.
    question: str = Field(min_length=1, max_length=1000)
    # The exact answer.
    answer: str = Field(min_length=1, max_length=4000)


# Body of PATCH /bots/{bot_id}/faqs/{faq_id}: only the fields sent are changed.
class FaqUpdate(_Strict):
    # New question.
    question: str | None = Field(default=None, min_length=1, max_length=1000)
    # New answer.
    answer: str | None = Field(default=None, min_length=1, max_length=4000)
    # Switch on/off.
    is_active: bool | None = None

    # At least one field, and no explicit nulls.
    @model_validator(mode="after")
    # Check the body as a whole.
    def _not_empty(self) -> "FaqUpdate":
        # Nothing to change is a client mistake.
        if not self.model_fields_set:
            # 422.
            raise ValueError("send at least one field to change")
        # Explicit null for any sent field.
        if any(getattr(self, name) is None for name in self.model_fields_set):
            # 422.
            raise ValueError("fields must not be null")
        # Valid.
        return self


# One FAQ in responses.
class FaqOut(BaseModel):
    # Its id.
    id: UUID
    # The question.
    question: str
    # The answer.
    answer: str
    # Switched on?
    is_active: bool
