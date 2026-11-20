# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Contract: send a reply to a customer on some channel.
# ─────────────────────────────────────────────────────────────────────────────────────────────
# From typing — type-hint helpers: Protocol = an interface: any class with these methods fits.
from typing import Protocol

# From saathi.modules.channels.domain.message — channel-neutral messages: Channel = where a
#   message came from; OutboundMessage = a reply to a customer.
from saathi.modules.channels.domain.message import Channel, OutboundMessage


# Implemented per channel (e.g. WhatsApp).
class ChannelSender(Protocol):
    channel: Channel

    async def send(self, tenant_id: str, recipient: str, message: OutboundMessage) -> None: ...
