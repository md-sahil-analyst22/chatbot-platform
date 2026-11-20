# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The 'state' passed between the steps of a chat reply (message, language, intent, answer,
#       citations...).
# ─────────────────────────────────────────────────────────────────────────────────────────────
from enum import StrEnum
from typing import TypedDict


# What the customer wants: FAQ, lead, booking, order status, complaint, human, chit-chat or
# out of scope.
class Intent(StrEnum):
    FAQ = "faq"
    LEAD = "lead"
    BOOKING = "booking"
    ORDER_STATUS = "order_status"
    COMPLAINT = "complaint"
    HUMAN = "human"
    CHITCHAT = "chitchat"
    OUT_OF_SCOPE = "out_of_scope"


# A source the answer was based on.
class Citation(TypedDict):
    source_id: str
    title: str
    page: int | None


# Everything known about one chat turn; every field optional (total=False).
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
