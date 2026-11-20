# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Contract: send a reply to a customer on some channel.
# ─────────────────────────────────────────────────────────────────────────────────────────────
from typing import Protocol

from saathi.modules.channels.domain.message import Channel, OutboundMessage


# Implemented per channel (e.g. WhatsApp).
class ChannelSender(Protocol):
    channel: Channel

    async def send(self, tenant_id: str, recipient: str, message: OutboundMessage) -> None: ...
