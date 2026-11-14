"""Guard node (P3.2), deterministic part. The injection classifier is added in Phase 3."""

from saathi.modules.conversation.domain.state import ChatState

MAX_MESSAGE_CHARS = 2000


def guard_node(state: ChatState) -> ChatState:
    text = (state.get("user_message") or "").strip()
    if not text:
        return {"blocked": True, "block_reason": "empty_message"}
    if len(text) > MAX_MESSAGE_CHARS:
        return {"blocked": True, "block_reason": "message_too_long"}
    return {"blocked": False, "block_reason": None, "user_message": text}
