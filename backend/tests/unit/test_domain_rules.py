# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The rules of Bot and Source (validation, allowed status changes) and the guard.
# How to run: cd backend && uv run pytest tests/unit (fast, no database or network).
# ─────────────────────────────────────────────────────────────────────────────────────────────
# dataclasses — quick classes that mainly hold data.
import dataclasses

# From uuid — unique ids (UUIDs): uuid4 = makes a random id.
from uuid import uuid4

# pytest — the test framework.
import pytest

# From tests.fakes.builders — one-line builders for test objects: make_bot = builds a test bot.
from tests.fakes.builders import make_bot

# From saathi.modules.conversation.application.nodes.guard — the first chat step (blocks bad
#   messages): MAX_MESSAGE_CHARS = longest allowed customer message; guard_node = the guard step.
from saathi.modules.conversation.application.nodes.guard import MAX_MESSAGE_CHARS, guard_node

# From saathi.modules.knowledge.domain.entities — the document (Source) business object: Source
#   = one document/web page; SourceStatus = queued/processing/ready/failed.
from saathi.modules.knowledge.domain.entities import Source, SourceStatus

# From saathi.modules.tenancy.domain.entities — the Bot business object: Bot = one chatbot.
from saathi.modules.tenancy.domain.entities import Bot

# From saathi.platform.errors — our error types: ConflictError = 409 clash with existing data;
#   ValidationError = 422 invalid input.
from saathi.platform.errors import ConflictError, ValidationError


# Helper: a valid test bot.
def _bot() -> Bot:
    # Built by the shared builder.
    return make_bot()


# Unsupported languages are refused.
def test_bot_rejects_unsupported_language() -> None:
    # Expect a ValidationError from the next line:
    with pytest.raises(ValidationError):
        # Build a bot with:
        Bot(
            # an id,
            id=uuid4(),
            # a tenant,
            tenant_id=uuid4(),
            # a name,
            name="Mitra",
            # no persona,
            persona="",
            # French, which we don't support,
            languages=("fr",),
            # a valid key.
            public_key="pk_" + uuid4().hex,
        )


# A badly formed widget key is refused.
def test_bot_rejects_malformed_public_key() -> None:
    # Expect a ValidationError from the next line:
    with pytest.raises(ValidationError):
        # public_key='x' doesn't look like pk_...
        Bot(id=uuid4(), tenant_id=uuid4(), name="M", persona="", languages=("en",), public_key="x")


# A Bot can't be changed in place.
def test_bot_is_immutable() -> None:
    # A test bot.
    bot = _bot()
    # Expect FrozenInstanceError...
    with pytest.raises(dataclasses.FrozenInstanceError):
        # ...when assigning a field.
        bot.languages = ("fr",)  # type: ignore[misc]
    # Expect TypeError...
    with pytest.raises(TypeError):
        # ...when changing its settings dictionary (it's read-only).
        bot.settings["x"] = 1  # type: ignore[index]


# Changed copies are checked again.
def test_bot_changes_are_revalidated() -> None:
    # A test bot.
    bot = _bot()
    # A valid change works.
    assert bot.with_languages(("en", "bn")).languages == ("en", "bn")
    # Expect a ValidationError from the next line:
    with pytest.raises(ValidationError):
        # An invalid language in the copy is refused.
        bot.with_languages(("fr",))
    # Expect a ValidationError from the next line:
    with pytest.raises(ValidationError):
        # A blank name in the copy is refused.
        bot.renamed("  ")


# A Source's status only changes through its methods, in the allowed order.
def test_source_lifecycle_only_through_methods() -> None:
    # A new source (queued).
    s = Source(id=uuid4(), tenant_id=uuid4(), bot_id=uuid4(), kind="file", uri="x")
    # queued -> processing.
    s.start_processing()
    # processing -> ready, with a fingerprint.
    s.mark_ready("hash-1")
    # Ready, and the same fingerprint counts as unchanged.
    assert s.status is SourceStatus.READY and s.is_unchanged("hash-1")
    # Expect a ConflictError from the next line:
    with pytest.raises(ConflictError):
        s.start_processing()  # must be re-queued first
    # ready -> queued.
    s.requeue()
    # queued -> processing works now.
    s.start_processing()
    # Expect AttributeError...
    with pytest.raises(AttributeError):
        # ...when setting the status directly.
        s.status = SourceStatus.READY  # type: ignore[misc]


# Run the guard test once per (message, blocked?) pair:
@pytest.mark.parametrize(
    # the two values each case provides,
    ("message", "blocked"),
    # empty -> blocked; one character too long -> blocked; a normal Banglish question ->
    #   allowed.
    [("", True), ("x" * (MAX_MESSAGE_CHARS + 1), True), ("ar price koto?", False)],
)
# The guard blocks exactly the bad messages.
def test_guard_node(message: str, blocked: bool) -> None:
    # Run the guard and compare.
    assert guard_node({"user_message": message})["blocked"] is blocked
