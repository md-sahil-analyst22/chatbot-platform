# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Sends messages through the WhatsApp Cloud API.
# Status: 🟡 Placeholder - built in a later phase (see
#         docs/planning/05_PHASEWISE_DEVELOPMENT_PLAN.md).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""WhatsApp Cloud API sender (implements ChannelSender). Settings: WHATSAPP_*.

Per-tenant tokens (encrypted at rest) replace the single test token in Phase 4.
"""

import httpx
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from saathi.modules.channels.domain.message import Channel, OutboundMessage
from saathi.platform.errors import ProviderError, ProviderTimeoutError


# WHATSAPP_* settings from .env.
class WhatsAppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WHATSAPP_", env_file=".env", extra="ignore")

    graph_version: str = "v21.0"
    access_token: SecretStr | None = None
    phone_number_id: str | None = None
    app_secret: SecretStr | None = None
    verify_token: SecretStr | None = None


# The WhatsApp sender.
class WhatsAppSender:
    channel = Channel.WHATSAPP

    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        access_token: str,
        phone_number_id: str,
        graph_version: str = "v21.0",
        timeout_s: float = 10.0,
    ) -> None:
        self._http = http
        self._url = f"https://graph.facebook.com/{graph_version}/{phone_number_id}/messages"
        self._headers = {"Authorization": f"Bearer {access_token}"}
        self._timeout = timeout_s

    # Send one reply to a customer's number.
    async def send(self, tenant_id: str, recipient: str, message: OutboundMessage) -> None:
        try:
            r = await self._http.post(
                self._url,
                headers=self._headers,
                timeout=self._timeout,
                json={
                    "messaging_product": "whatsapp",
                    "to": recipient,
                    "type": "text",
                    "text": {"body": message.text},
                },
            )
            r.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("whatsapp send timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("whatsapp send failed") from exc
