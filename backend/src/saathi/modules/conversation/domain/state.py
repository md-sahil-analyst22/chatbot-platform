from enum import StrEnum
from typing import TypedDict


class Intent(StrEnum):
    FAQ = "faq"
    LEAD = "lead"
    BOOKING = "booking"
    ORDER_STATUS = "order_status"
    COMPLAINT = "complaint"
    HUMAN = "human"
    CHITCHAT = "chitchat"
    OUT_OF_SCOPE = "out_of_scope"


class Citation(TypedDict):
    source_id: str
    title: str
    page: int | None


class ChatState(TypedDict, total=False):
    tenant_id: str
    bot_id: str
    conversation_id: str
    channel: str
    user_message: str
    blocked: bool
    block_reason: str | None
    language: str | None
    rewritten_query: str | None
    intent: Intent | None
    answer: str | None
    citations: list[Citation]
    confidence: float | None
