# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The first step of every chat reply: block empty or too-long messages.
# Status: 🟡 A smarter prompt-injection check is added in Phase 3.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Guard node (P3.2), deterministic part. The injection classifier is added in Phase 3."""

from saathi.modules.conversation.domain.state import ChatState

# Longest allowed customer message.
MAX_MESSAGE_CHARS = 2000


# Returns blocked=True with a reason, or the cleaned message.
def guard_node(state: ChatState) -> ChatState:
    text = (state.get("user_message") or "").strip()
    # Empty message -> blocked.
    if not text:
        return {"blocked": True, "block_reason": "empty_message"}
    # Too long -> blocked (protects cost and the model).
    if len(text) > MAX_MESSAGE_CHARS:
        return {"blocked": True, "block_reason": "message_too_long"}
    return {"blocked": False, "block_reason": None, "user_message": text}
