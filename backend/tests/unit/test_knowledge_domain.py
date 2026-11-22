# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The Phase 2 business rules: Source life cycle, crawl options, chunking policy,
#                FAQs, and the bot's retrieval settings (incl. old stored configs still loading).
# How to run: cd backend && uv run pytest tests/unit/test_knowledge_domain.py (no database).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Phase 2 domain rules (R20, R22)."""

# From uuid — unique ids (UUIDs): uuid4 = makes a random id.
from uuid import uuid4

# pytest — the test framework.
import pytest

# From tests.fakes.builders — one-line builders for test objects: make_config = a valid
#   BotConfig.
from tests.fakes.builders import make_config

# From saathi.modules.knowledge.domain.chunking — chunk rules: Chunk = one passage;
#   ChunkingPolicy = chunk size + overlap.
from saathi.modules.knowledge.domain.chunking import Chunk, ChunkingPolicy

# From saathi.modules.knowledge.domain.crawl — crawl settings: CrawlOptions = one crawl's
#   settings.
from saathi.modules.knowledge.domain.crawl import CrawlOptions

# From saathi.modules.knowledge.domain.entities — sources: Source = one document/website;
#   SourceStatus = queued/processing/ready/failed.
from saathi.modules.knowledge.domain.entities import Source, SourceStatus

# From saathi.modules.knowledge.domain.faq — FAQs: Faq = one question + exact answer.
from saathi.modules.knowledge.domain.faq import Faq

# From saathi.modules.tenancy.adapters.config_mapper — config <-> JSON: config_from_json =
#   JSON -> BotConfig; config_to_json = BotConfig -> JSON.
from saathi.modules.tenancy.adapters.config_mapper import config_from_json, config_to_json

# From saathi.modules.tenancy.domain.bot_config — bot settings: RetrievalSettings = the
#   per-bot knowledge settings.
from saathi.modules.tenancy.domain.bot_config import RetrievalSettings

# From saathi.platform.errors — our error types: ConflictError = 409 not allowed now;
#   ValidationError = 422 invalid input.
from saathi.platform.errors import ConflictError, ValidationError


# A file source in a given status (default: queued).
def _file(status: SourceStatus = SourceStatus.QUEUED) -> Source:
    # Minimal valid file source with random ids.
    return Source(
        id=uuid4(), tenant_id=uuid4(), bot_id=uuid4(), kind="file", uri="t/x/f.pdf", status=status
    )


# A website must have crawl settings; a file must not; unknown kinds are refused.
def test_website_source_requires_crawl_options_and_files_refuse_them() -> None:
    # A URL source without crawl settings...
    with pytest.raises(ValidationError):
        # ...is refused.
        Source(id=uuid4(), tenant_id=uuid4(), bot_id=uuid4(), kind="url", uri="https://a.in")
    # A file source WITH crawl settings...
    with pytest.raises(ValidationError):
        # ...is refused too.
        Source(
            id=uuid4(),
            tenant_id=uuid4(),
            bot_id=uuid4(),
            kind="file",
            uri="t/x",
            crawl=CrawlOptions(root_url="https://a.in"),
        )
    # An unknown kind ('ftp')...
    with pytest.raises(ValidationError):
        # ...is refused.
        Source(id=uuid4(), tenant_id=uuid4(), bot_id=uuid4(), kind="ftp", uri="x")


# A failure reason is stored (shortened) and forgotten after a later success.
def test_failure_reason_is_stored_bounded_and_cleared_on_success() -> None:
    # A queued source...
    s = _file()
    # ...starts processing...
    s.start_processing()
    # ...and fails with a 900-character reason.
    s.mark_failed("x" * 900)
    # It is failed, and the reason is cut to the column size (500).
    assert s.status is SourceStatus.FAILED and s.error is not None and len(s.error) == 500
    # Retry: failed -> queued...
    s.requeue()
    # ...-> processing...
    s.start_processing()
    # ...-> ready.
    s.mark_ready("hash")
    # The old reason is gone and the fingerprint is stored.
    assert s.error is None and s.content_hash == "hash"


# Moves that skip a step are refused with 409.
def test_illegal_transitions_are_409() -> None:
    # A queued source can't jump straight to ready.
    with pytest.raises(ConflictError):
        # Try it.
        _file().mark_ready("h")
    # A source that is processing...
    s = _file()
    # ...(start it)...
    s.start_processing()
    # ...can't be put back in the queue (the publish hook relies on this).
    with pytest.raises(ConflictError):
        # Try it.
        s.requeue()


# Each of these crawl settings breaks one rule.
@pytest.mark.parametrize(
    "kwargs",
    [
        # Not a web address.
        {"root_url": "ftp://a.in"},
        # Too deep.
        {"root_url": "https://a.in", "max_depth": 4},
        # Zero pages.
        {"root_url": "https://a.in", "max_pages": 0},
        # Too many pages.
        {"root_url": "https://a.in", "max_pages": 201},
        # A pattern that doesn't start with '/'.
        {"root_url": "https://a.in", "include_patterns": ("services/*",)},
        # Too many patterns.
        {"root_url": "https://a.in", "exclude_patterns": tuple(f"/{i}" for i in range(21))},
        # An address that is too long.
        {"root_url": "https://" + "a" * 2000},
    ],
)
# Every invalid crawl setting is refused.
def test_crawl_options_reject_invalid_values(kwargs: dict[str, object]) -> None:
    # Bounded job (R33), untrusted input (R19): 422.
    with pytest.raises(ValidationError):
        # Build it with the bad values.
        CrawlOptions(**kwargs)  # type: ignore[arg-type]  # deliberately wrong values


# Crawl settings survive the JSON round trip; old rows with few keys still load.
def test_crawl_options_json_round_trip_and_old_rows_load() -> None:
    # Settings with every field set.
    opts = CrawlOptions("https://a.in", 2, 30, ("/svc/*",), ("/blog/*",))
    # To JSON and back gives the same settings.
    assert CrawlOptions.from_json(opts.to_json()) == opts
    # A minimal stored JSON loads with the default page budget.
    assert CrawlOptions.from_json({"root_url": "https://a.in"}).max_pages == 50


# Chunk size/overlap ranges, the fingerprint signature and the overlap size.
def test_chunking_policy_ranges_and_signature() -> None:
    # Too small, too big, negative overlap, too much overlap...
    for size, overlap in ((199, 0.1), (1201, 0.1), (500, -0.1), (500, 0.31)):
        # ...each is refused.
        with pytest.raises(ValidationError):
            # Build it.
            ChunkingPolicy(size, overlap)
    # A different size gives a different signature (it is part of the source fingerprint)...
    assert ChunkingPolicy(700, 0.15).signature != ChunkingPolicy(600, 0.15).signature
    # ...and so does a different overlap.
    assert ChunkingPolicy(700, 0.15).signature != ChunkingPolicy(700, 0.10).signature
    # Overlap tokens = size x ratio (700 x 0.15).
    assert ChunkingPolicy(700, 0.15).overlap_tokens == 105


# A chunk needs text and a position from 0.
def test_chunk_rejects_empty_text_and_negative_index() -> None:
    # Only spaces...
    with pytest.raises(ValidationError):
        # ...is refused.
        Chunk(index=0, text="   ")
    # A negative position...
    with pytest.raises(ValidationError):
        # ...is refused.
        Chunk(index=-1, text="x")


# FAQ text rules and immutable edits.
def test_faq_validation_and_edits() -> None:
    # A valid FAQ in Bengali.
    faq = Faq(id=uuid4(), tenant_id=uuid4(), bot_id=uuid4(), question="ফি কত?", answer="৫০০ টাকা")
    # Editing returns a NEW FAQ...
    edited = faq.edited(answer="600")
    # ...with the new answer, while the original is unchanged.
    assert edited.answer == "600" and faq.answer == "৫০০ টাকা"
    # Empty question, empty answer, too long question/answer, control character...
    for q, a in (("", "a"), ("q", ""), ("q" * 1001, "a"), ("q", "a" * 4001), ("q\x00", "a")):
        # ...each is refused.
        with pytest.raises(ValidationError):
            # Build it.
            Faq(id=uuid4(), tenant_id=uuid4(), bot_id=uuid4(), question=q, answer=a)
    # Switching it off keeps everything else.
    assert faq.with_active(False).is_active is False


# Retrieval settings ranges, and which changes count as 'chunking changed'.
def test_retrieval_settings_validation_and_chunking_difference() -> None:
    # The defaults are valid.
    d = RetrievalSettings()
    # Thresholds and search sizes don't change how documents are cut...
    assert not d.chunking_differs(RetrievalSettings(confidence_threshold=0.5, vector_top_k=10))
    # ...but chunk size does...
    assert d.chunking_differs(RetrievalSettings(chunk_size_tokens=500))
    # ...and so does overlap.
    assert d.chunking_differs(RetrievalSettings(chunk_overlap_ratio=0.1))
    # Each of these values is out of range...
    for kwargs in (
        {"chunk_size_tokens": 100},
        {"chunk_overlap_ratio": 0.5},
        {"vector_top_k": 0},
        {"keyword_top_k": 51},
        {"rerank_top_n": 11},
        {"faq_threshold": 1.1},
        {"confidence_threshold": -0.1},
    ):
        # ...and is refused.
        with pytest.raises(ValidationError):
            # Build it.
            RetrievalSettings(**kwargs)  # type: ignore[arg-type]  # deliberately wrong values


# R22: a config saved before Phase 2 (no 'retrieval' part) still loads.
def test_old_stored_config_without_retrieval_loads_with_defaults() -> None:
    # A stored config as JSON...
    stored = config_to_json(make_config())
    # ...without the Phase 2 part.
    del stored["retrieval"]
    # It loads, with the default retrieval settings.
    assert config_from_json(stored).retrieval == RetrievalSettings()


# Custom retrieval settings survive saving and loading.
def test_retrieval_settings_round_trip_through_json() -> None:
    # From dataclasses — copy with some fields changed: replace.
    from dataclasses import replace

    # A config with a custom chunk size.
    config = replace(make_config(), retrieval=RetrievalSettings(chunk_size_tokens=500))
    # Save + load keeps it.
    assert config_from_json(config_to_json(config)).retrieval.chunk_size_tokens == 500
