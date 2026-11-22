# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Two small measuring tools for text:
#   estimate_tokens(text)  -> roughly how many LLM 'tokens' a text costs (no tokenizer library);
#   detect_language(text)  -> 'hi' (Devanagari script), 'bn' (Bengali script) or 'en'.
# Why an estimate: the real Gemini tokenizer runs on Google's side. Chunk sizes only need to be
#   about right, so we count words/characters instead of adding a heavy dependency.
# Limits: Romanised Hindi/Bengali (Hinglish/Banglish) is written in Latin letters and is
#   reported as 'en'; the label only helps filtering and reports, never security.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Token estimate and script-based language detection (P2.6 chunk metadata)."""

# math — rounding up.
import math

# re — regular expressions (text patterns).
import re

# Unicode block of Devanagari (Hindi, Marathi...).
_DEVANAGARI = (0x0900, 0x097F)
# Unicode block of Bengali (Bengali, Assamese).
_BENGALI = (0x0980, 0x09FF)
# A 'word' = a run of non-space characters.
_WORD = re.compile(r"\S+")
# Latin words average ~4 characters per token.
_LATIN_CHARS_PER_TOKEN = 4.0
# Indic scripts split into more tokens: ~3 characters per token.
_INDIC_CHARS_PER_TOKEN = 3.0
# Below this share of Indic letters, a text counts as English.
_INDIC_SHARE = 0.3


# Is this character in the Devanagari or Bengali block?
def _is_indic(ch: str) -> bool:
    # The character's number.
    code = ord(ch)
    # Inside either block.
    return _DEVANAGARI[0] <= code <= _DEVANAGARI[1] or _BENGALI[0] <= code <= _BENGALI[1]


# Roughly how many tokens a text is.
def estimate_tokens(text: str) -> int:
    """Each word costs at least 1 token; long and Indic words cost more."""
    # Running total.
    total = 0
    # Look at each word...
    for word in _WORD.findall(text):
        # ...Indic words use the Indic rate, others the Latin rate...
        rate = _INDIC_CHARS_PER_TOKEN if any(_is_indic(c) for c in word) else _LATIN_CHARS_PER_TOKEN
        # ...and every word costs at least one token.
        total += max(1, math.ceil(len(word) / rate))
    # The estimate.
    return total


# Which language a text is written in (by script).
def detect_language(text: str) -> str:
    """'hi' or 'bn' when enough letters are in that script, otherwise 'en'."""
    # Counters for letters in each script.
    deva = beng = letters = 0
    # Look at each character...
    for ch in text:
        # ...only letters and Indic marks count (spaces, digits, punctuation don't).
        if not (ch.isalpha() or _is_indic(ch)):
            # Skip it.
            continue
        # One more letter.
        letters += 1
        # Its number.
        code = ord(ch)
        # Devanagari?
        if _DEVANAGARI[0] <= code <= _DEVANAGARI[1]:
            # Count it.
            deva += 1
        # Bengali?
        elif _BENGALI[0] <= code <= _BENGALI[1]:
            # Count it.
            beng += 1
    # No letters at all (numbers, symbols) -> English by default.
    if letters == 0:
        # Default.
        return "en"
    # Enough Devanagari or Bengali letters -> whichever has more.
    if (deva + beng) / letters >= _INDIC_SHARE:
        # Hindi or Bengali.
        return "hi" if deva >= beng else "bn"
    # Otherwise English (includes Hinglish/Banglish in Latin letters).
    return "en"
