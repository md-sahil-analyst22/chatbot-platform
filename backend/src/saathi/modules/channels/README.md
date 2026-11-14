# modules/channels

Every channel converts its payload into one `InboundMessage`, hands it to the conversation
module, and converts the reply back. Adding Telegram later = one new adapter folder.

- `domain/message.py` - `InboundMessage`, `OutboundMessage`, `Channel`
- `ports/channel.py` - `ChannelSender` interface
- `application/dispatch.py` - inbound -> conversation -> outbound (P4.1)
- `adapters/web/` - SSE formatting for the widget
- `adapters/whatsapp/` - Cloud API client, signature verification, dedupe (P4.6 - P4.11)
- `api/webhooks.py` - `/api/v1/webhooks/whatsapp` (return 200 fast, process async)
