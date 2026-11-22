# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The text pipeline before embedding: token estimate, language detection, the
#                cleaner (P2.5) and the heading-aware chunker (P2.6), incl. Hindi/Bengali text.
# How to run: cd backend && uv run pytest tests/unit/test_text_processing.py (no database).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Cleaner, chunker and text metrics."""

# itertools — loop helpers: pairwise = (a, b), (b, c), ... over a list.
import itertools

# unicodedata — Unicode normalisation (to build the expected NFC text).
import unicodedata

# From saathi.modules.knowledge.application.chunker — the chunker: chunk_pages = pages ->
#   chunks.
from saathi.modules.knowledge.application.chunker import chunk_pages

# From saathi.modules.knowledge.application.cleaner — the cleaner: TextPage = one page of text;
#   clean_pages = tidy a document; normalise_text = tidy one text.
from saathi.modules.knowledge.application.cleaner import TextPage, clean_pages, normalise_text

# From saathi.modules.knowledge.application.text_metrics — measuring: detect_language = script
#   -> 'en'/'hi'/'bn'; estimate_tokens = rough token count.
from saathi.modules.knowledge.application.text_metrics import detect_language, estimate_tokens

# From saathi.modules.knowledge.domain.chunking — chunk rules: ChunkingPolicy = size + overlap.
from saathi.modules.knowledge.domain.chunking import ChunkingPolicy


# The language is told apart by the script the text is written in.
def test_language_detection_by_script() -> None:
    # English text -> 'en'.
    assert detect_language("What are your office hours?") == "en"
    # Devanagari -> 'hi'.
    assert detect_language("आपके ऑफिस का समय क्या है?") == "hi"
    # Bengali script -> 'bn'.
    assert detect_language("আপনার অফিসের সময় কী?") == "bn"
    # Hinglish is written in Latin letters, so it counts as English.
    assert detect_language("aapka office kab khulta hai") == "en"
    # Only numbers: English by default.
    assert detect_language("12345") == "en"


# The token estimate is never zero for real text and grows with length.
def test_token_estimate_grows_with_text_and_counts_indic_words() -> None:
    # Every word costs at least one token.
    assert estimate_tokens("a b c") == 3
    # Longer text costs more.
    assert estimate_tokens("GST filing " * 50) > estimate_tokens("GST filing")
    # Hindi words cost at least one token each.
    assert estimate_tokens("नमस्ते दुनिया") >= 2
    # Empty text costs nothing.
    assert estimate_tokens("") == 0


# Unicode forms, spaces and blank lines are unified.
def test_normalise_unifies_unicode_and_spacing() -> None:
    # 'e' + a separate accent mark, extra spaces, Windows line break, many blank lines.
    out = normalise_text("Café   menu\r\n\n\n\nnext")
    # One composed 'é' (NFC), one space, at most one blank line.
    assert out == unicodedata.normalize("NFC", "Café menu\n\nnext")


# Running headers, footers and page numbers are removed; the content stays.
def test_cleaner_removes_running_headers_footers_and_page_numbers() -> None:
    # Five pages, each: the same header, two content lines, a numbered footer.
    pages = [
        TextPage(
            f"TaxMitra Associates\nService {i} costs {i}00 rupees.\nCall us on day {i}.\n"
            f"Page {i} of 5",
            page=i,
        )
        for i in range(1, 6)
    ]
    # Clean them.
    cleaned = clean_pages(pages)
    # Header and footer are gone; both content lines survive on every page (they look alike
    #   once digits are ignored, but they are not at the page edges).
    assert [p.text for p in cleaned] == [
        f"Service {i} costs {i}00 rupees.\nCall us on day {i}." for i in range(1, 6)
    ]


# A real sentence that starts like boilerplate is kept.
def test_cleaner_keeps_real_sentences_that_look_like_boilerplate() -> None:
    # A real fact, a copyright footer with a year, and a 'skip' link.
    page = TextPage(
        "Copyright registration fees are ₹500.\n© 2026 TaxMitra. All rights reserved\n"
        "Skip to content"
    )
    # Only the real fact survives.
    assert clean_pages([page])[0].text == "Copyright registration fees are ₹500."


# Empty pages and exact duplicate pages are dropped.
def test_cleaner_drops_empty_and_duplicate_pages() -> None:
    # The same page crawled twice (with and without '/'), plus an empty page.
    pages = [
        TextPage("About us\nWe file ITR.", url="https://a.in/about"),
        TextPage("About us\nWe file ITR.", url="https://a.in/about/"),
        TextPage("   ", url="https://a.in/empty"),
    ]
    # Clean them.
    cleaned = clean_pages(pages)
    # Only the first copy is kept.
    assert [p.url for p in cleaned] == ["https://a.in/about"]


# No chunk is bigger than the limit, and neighbours overlap.
def test_chunks_respect_the_size_limit_and_overlap() -> None:
    # One long paragraph of 200 numbered sentences.
    text = " ".join(f"Sentence {i} explains the GST filing fee." for i in range(200))
    # Small chunks (200 tokens) with 15% overlap.
    policy = ChunkingPolicy(200, 0.15)
    # Cut it.
    chunks = chunk_pages([TextPage(text, page=1)], policy)
    # Several chunks...
    assert len(chunks) > 3
    # ...none over the limit.
    assert all(estimate_tokens(c.text) <= policy.chunk_size_tokens for c in chunks)
    # Each pair of neighbours...
    for a, b in itertools.pairwise(chunks):
        # ...the next chunk's first sentence...
        first_sentence_of_b = b.text.split(". ")[0]
        # ...is also in the previous chunk (overlap: a boundary sentence is never lost).
        assert first_sentence_of_b in a.text
    # Positions are 0, 1, 2... in order.
    assert [c.index for c in chunks] == list(range(len(chunks)))


# Chunks start at headings and remember the heading path.
def test_chunks_follow_headings_and_record_the_section_path() -> None:
    # A body big enough to fill a chunk on its own.
    body = " ".join(["Detail about this topic."] * 40)
    # Two sections under one top heading.
    text = f"# Services\n\n## GST\n\n{body}\n\n## ITR\n\n{body}"
    # Cut it (page 3 of a file).
    chunks = chunk_pages([TextPage(text, page=3)], ChunkingPolicy(300, 0.1))
    # The heading path of each chunk.
    sections = [c.section for c in chunks]
    # Both sections appear with their full path.
    assert "Services > GST" in sections and "Services > ITR" in sections
    # The heading line itself is kept in the text (context for search and the LLM).
    assert any(c.text.startswith("## ITR") for c in chunks)
    # The page number is carried on every chunk.
    assert all(c.page == 3 for c in chunks)


# Two web pages are never mixed in one chunk.
def test_chunks_never_mix_two_web_pages() -> None:
    # Two short pages that would fit in one chunk.
    pages = [
        TextPage("Home page text.", url="https://a.in/"),
        TextPage("Contact page text.", url="https://a.in/contact"),
    ]
    # Cut them.
    chunks = chunk_pages(pages, ChunkingPolicy())
    # One chunk per page, each with its own address.
    assert [c.url for c in chunks] == ["https://a.in/", "https://a.in/contact"]


# Hindi text is split at the danda (।) and tagged as Hindi.
def test_hindi_text_is_split_at_danda_and_tagged_hi() -> None:
    # A long Hindi paragraph whose sentences end with '।'.
    text = "।".join(["जीएसटी फाइलिंग की फीस पाँच सौ रुपये है"] * 120) + "।"
    # Cut it into small chunks.
    chunks = chunk_pages([TextPage(text)], ChunkingPolicy(200, 0.1))
    # More than one chunk...
    assert len(chunks) > 1
    # ...all tagged Hindi...
    assert all(c.language == "hi" for c in chunks)
    # ...and all within the limit.
    assert all(estimate_tokens(c.text) <= 200 for c in chunks)


# No text in, no chunks out.
def test_empty_input_gives_no_chunks() -> None:
    # No pages at all.
    assert chunk_pages([], ChunkingPolicy()) == []
    # A page with only blank lines.
    assert chunk_pages([TextPage("\n\n  \n")], ChunkingPolicy()) == []
