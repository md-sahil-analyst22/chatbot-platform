# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The 'state' passed between the steps of a chat reply (message, language, intent, answer,
#       citations...).
# ─────────────────────────────────────────────────────────────────────────────────────────────
# From enum — fixed sets of named values: StrEnum = a fixed set of named text values.
from enum import StrEnum

# From typing — type-hint helpers: TypedDict = a dict with known keys.
from typing import TypedDict


# What the customer wants: FAQ, lead, booking, order status, complaint, human, chit-chat or
# out of scope.
class Intent(StrEnum):
    # A question the documents/FAQs can answer.
    FAQ = "faq"
    # The customer wants to leave contact details.
    LEAD = "lead"
    # The customer wants an appointment.
    BOOKING = "booking"
    # Where is my order?
    ORDER_STATUS = "order_status"
    # A complaint.
    COMPLAINT = "complaint"
    # The customer wants a person.
    HUMAN = "human"
    # Small talk (hi, thanks...).
    CHITCHAT = "chitchat"
    # Not something this bot handles.
    OUT_OF_SCOPE = "out_of_scope"


# A source the answer was based on.
class Citation(TypedDict):
    # Which document.
    source_id: str
    # Its title.
    title: str
    # Which page, if known.
    page: int | None


# Everything known about one chat turn; every field optional (total=False).
class ChatState(TypedDict, total=False):
    # 🔒 Which workspace.
    tenant_id: str
    # Which bot.
    bot_id: str
    # Which conversation.
    conversation_id: str
    # web / whatsapp / voice.
    channel: str
    # What the customer wrote.
    user_message: str
    # True if the guard stopped the message.
    blocked: bool
    # Why it was stopped.
    block_reason: str | None
    # Detected language.
    language: str | None
    # The question rewritten for searching.
    rewritten_query: str | None
    # What the customer wants.
    intent: Intent | None
    # The reply.
    answer: str | None
    # Sources the reply used.
    citations: list[Citation]
    # How sure the bot is (0-1).
    confidence: float | None
