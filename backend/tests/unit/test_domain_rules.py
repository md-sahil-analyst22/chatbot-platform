# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The rules of Bot and Source (validation, allowed status changes) and the guard.
# How to run: cd backend && uv run pytest tests/unit (fast, no database or network).
# ─────────────────────────────────────────────────────────────────────────────────────────────
import dataclasses
from uuid import uuid4

import pytest
from tests.fakes.builders import make_bot

from saathi.modules.conversation.application.nodes.guard import MAX_MESSAGE_CHARS, guard_node
from saathi.modules.knowledge.domain.entities import Source, SourceStatus
from saathi.modules.tenancy.domain.entities import Bot
from saathi.platform.errors import ConflictError, ValidationError


def _bot() -> Bot:
    return make_bot()


def test_bot_rejects_unsupported_language() -> None:
    with pytest.raises(ValidationError):
        Bot(
            id=uuid4(),
            tenant_id=uuid4(),
            name="Mitra",
            persona="",
            languages=("fr",),
            public_key="pk_" + uuid4().hex,
        )


def test_bot_rejects_malformed_public_key() -> None:
    with pytest.raises(ValidationError):
        Bot(id=uuid4(), tenant_id=uuid4(), name="M", persona="", languages=("en",), public_key="x")


def test_bot_is_immutable() -> None:
    bot = _bot()
    with pytest.raises(dataclasses.FrozenInstanceError):
        bot.languages = ("fr",)  # type: ignore[misc]
    with pytest.raises(TypeError):
        bot.settings["x"] = 1  # type: ignore[index]


def test_bot_changes_are_revalidated() -> None:
    bot = _bot()
    assert bot.with_languages(("en", "bn")).languages == ("en", "bn")
    with pytest.raises(ValidationError):
        bot.with_languages(("fr",))
    with pytest.raises(ValidationError):
        bot.renamed("  ")


def test_source_lifecycle_only_through_methods() -> None:
    s = Source(id=uuid4(), tenant_id=uuid4(), bot_id=uuid4(), kind="file", uri="x")
    s.start_processing()
    s.mark_ready("hash-1")
    assert s.status is SourceStatus.READY and s.is_unchanged("hash-1")
    with pytest.raises(ConflictError):
        s.start_processing()  # must be re-queued first
    s.requeue()
    s.start_processing()
    with pytest.raises(AttributeError):
        s.status = SourceStatus.READY  # type: ignore[misc]


@pytest.mark.parametrize(
    ("message", "blocked"),
    [("", True), ("x" * (MAX_MESSAGE_CHARS + 1), True), ("ar price koto?", False)],
)
def test_guard_node(message: str, blocked: bool) -> None:
    assert guard_node({"user_message": message})["blocked"] is blocked
