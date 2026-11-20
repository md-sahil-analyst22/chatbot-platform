# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Channel-neutral messages: the same shape whether the customer writes on the website or
#       WhatsApp.
# ─────────────────────────────────────────────────────────────────────────────────────────────
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


# Where a message came from.
class Channel(StrEnum):
    WEB = "web"
    WHATSAPP = "whatsapp"
    VOICE = "voice"


@dataclass(frozen=True, slots=True)
# A message FROM a customer.
class InboundMessage:
    tenant_id: str
    bot_id: str
    channel: Channel
    external_user_id: str  # widget session id / WhatsApp phone
    external_message_id: str  # used for dedupe (P4.7)
    text: str
    received_at: datetime
    media_url: str | None = None


@dataclass(frozen=True, slots=True)
# A message TO a customer.
class OutboundMessage:
    text: str
    buttons: tuple[str, ...] = field(default_factory=tuple)  # WhatsApp: max 3

    # At most 3 quick-reply buttons (WhatsApp's limit).
    def __post_init__(self) -> None:
        if len(self.buttons) > 3:
            raise ValueError("at most 3 reply buttons")
