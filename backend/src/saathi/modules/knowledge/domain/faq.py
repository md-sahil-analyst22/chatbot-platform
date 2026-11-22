# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: An FAQ = a question + the exact answer the business wants given (P2.12).
# Rule: When a customer's question means the same as an active FAQ question, the FAQ answer is
#       used word for word: it 'always wins' over passages found in documents.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""FAQ entity. Immutable: edits create a changed copy through named methods (R20)."""

# unicodedata — tells which characters are control characters.
import unicodedata

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you; replace = copy with some fields changed.
from dataclasses import dataclass, replace

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From saathi.platform.errors — our error types: ValidationError = 422 invalid input.
from saathi.platform.errors import ValidationError

# Longest question (matches the faqs.question column).
MAX_QUESTION_CHARS = 1000
# Longest answer (matches the faqs.answer column).
MAX_ANSWER_CHARS = 4000


# Refuse empty, too-long or control-character text.
def _check_text(value: str, name: str, max_len: int) -> None:
    # Must contain something visible.
    if not value.strip():
        # 422.
        raise ValidationError(f"{name} must not be empty")
    # Bounded length.
    if len(value) > max_len:
        # 422.
        raise ValidationError(f"{name} must be at most {max_len} characters")
    # Control characters (except newline/tab) are refused.
    if any(unicodedata.category(ch) == "Cc" and ch not in "\n\t" for ch in value):
        # 422.
        raise ValidationError(f"{name} contains control characters")


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# One FAQ entry.
class Faq:
    # Its id.
    id: UUID
    # 🔒 The owning workspace.
    tenant_id: UUID
    # The bot it belongs to.
    bot_id: UUID
    # The question customers ask.
    question: str
    # The exact answer to give.
    answer: str
    # Switched on (inactive FAQs are never matched).
    is_active: bool = True

    # Runs right after __init__: reject invalid values (R20).
    def __post_init__(self) -> None:
        # Check the question.
        _check_text(self.question, "question", MAX_QUESTION_CHARS)
        # Check the answer.
        _check_text(self.answer, "answer", MAX_ANSWER_CHARS)

    # A copy with new text (validated again).
    def edited(self, *, question: str | None = None, answer: str | None = None) -> "Faq":
        # Keep what wasn't given.
        return replace(
            self,
            question=self.question if question is None else question,
            answer=self.answer if answer is None else answer,
        )

    # A copy switched on or off.
    def with_active(self, is_active: bool) -> "Faq":
        # Only the flag changes.
        return replace(self, is_active=is_active)
