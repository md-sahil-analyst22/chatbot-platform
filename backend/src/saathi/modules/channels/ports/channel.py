from typing import Protocol

from saathi.modules.channels.domain.message import Channel, OutboundMessage


class ChannelSender(Protocol):
    channel: Channel

    async def send(self, tenant_id: str, recipient: str, message: OutboundMessage) -> None: ...
