from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class Channel(StrEnum):
    WEB = "web"
    WHATSAPP = "whatsapp"
    VOICE = "voice"


@dataclass(frozen=True, slots=True)
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
class OutboundMessage:
    text: str
    buttons: tuple[str, ...] = field(default_factory=tuple)  # WhatsApp: max 3

    def __post_init__(self) -> None:
        if len(self.buttons) > 3:
            raise ValueError("at most 3 reply buttons")
