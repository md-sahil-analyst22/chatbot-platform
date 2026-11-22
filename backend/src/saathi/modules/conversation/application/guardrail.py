# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The confidence guardrail (P2.14): decides whether retrieval found something solid enough
#       to answer from. If not, the bot says "I'm not sure" and offers a human, and the question
#       is logged for the business to fill the gap. The bot never invents an answer.
# Rules, checked in order:
#   1. nothing found                          -> NO_RESULTS
#   2. results were not reranked (degraded)   -> PROVIDER_UNAVAILABLE (we don't trust an
#                                                unscored guess: fail closed)
#   3. top reranker score below the bot's threshold -> LOW_CONFIDENCE
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Confidence guardrail and the localized 'not sure' reply."""

# From saathi.modules.conversation.ports.retrieval — retrieval types: Retrieval = what retrieval
#   found.
from saathi.modules.conversation.ports.retrieval import Retrieval

# From saathi.modules.conversation.ports.unanswered — unanswered log: UnansweredReason = why.
from saathi.modules.conversation.ports.unanswered import UnansweredReason

# The 'not sure' reply per language (offers a human; never guesses).
_UNSURE: dict[str, str] = {
    # English.
    "en": (
        "I'm not sure about that, and I don't want to give you wrong information. "
        "Would you like me to connect you with our team?"
    ),
    # Hindi.
    "hi": (
        "मुझे इसके बारे में पक्की जानकारी नहीं है, और मैं आपको गलत जानकारी नहीं देना चाहता। "
        "क्या आप चाहेंगे कि मैं आपको हमारी टीम से जोड़ दूँ?"
    ),
    # Bengali.
    "bn": (
        "এ বিষয়ে আমি নিশ্চিত নই, আর আমি আপনাকে ভুল তথ্য দিতে চাই না। "
        "আপনি কি চান আমি আপনাকে আমাদের টিমের সাথে যোগাযোগ করিয়ে দিই?"
    ),
}


# The 'not sure' reply in the user's language (English for anything else, incl. Hinglish).
def unsure_message(language: str) -> str:
    """'hi-IN' and 'hi' both give Hindi; unknown languages give English."""
    # Use the first part of codes like 'hi-IN'.
    return _UNSURE.get(language.split("-")[0].lower(), _UNSURE["en"])


# Is this retrieval good enough to answer from? None = yes, otherwise why not.
def assess(retrieval: Retrieval, confidence_threshold: float) -> UnansweredReason | None:
    """Apply the three rules above. FAQ matches are always good (they passed their own,
    higher threshold in retrieval)."""
    # An FAQ won: answer with it.
    if retrieval.faq is not None:
        # Good.
        return None
    # Rule 1: nothing found.
    if not retrieval.passages:
        # Not sure.
        return UnansweredReason.NO_RESULTS
    # Rule 2: unscored results (reranker down) are not trusted.
    if not retrieval.reranked or retrieval.confidence is None:
        # Not sure.
        return UnansweredReason.PROVIDER_UNAVAILABLE
    # Rule 3: too weak a match.
    if retrieval.confidence < confidence_threshold:
        # Not sure.
        return UnansweredReason.LOW_CONFIDENCE
    # Good enough.
    return None
