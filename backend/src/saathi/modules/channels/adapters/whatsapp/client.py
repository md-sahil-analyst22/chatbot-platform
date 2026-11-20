# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Sends messages through the WhatsApp Cloud API.
# Status: 🟡 Placeholder - built in a later phase (see
#         docs/planning/05_PHASEWISE_DEVELOPMENT_PLAN.md).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""WhatsApp Cloud API sender (implements ChannelSender). Settings: WHATSAPP_*.

Per-tenant tokens (encrypted at rest) replace the single test token in Phase 4.
"""

# httpx — the HTTP client we use to call other web services.
import httpx

# From pydantic — checks data against declared types and rules: SecretStr = text that hides
#   itself when printed or logged.
from pydantic import SecretStr

# From pydantic_settings — reads settings from environment variables and .env: BaseSettings =
#   parent class for a group of settings; SettingsConfigDict = where settings are read from (.env,
#   prefix).
from pydantic_settings import BaseSettings, SettingsConfigDict

# From saathi.modules.channels.domain.message — channel-neutral messages: Channel = where a
#   message came from; OutboundMessage = a reply to a customer.
from saathi.modules.channels.domain.message import Channel, OutboundMessage

# From saathi.platform.errors — our error types: ProviderError = a vendor failed;
#   ProviderTimeoutError = a vendor was too slow.
from saathi.platform.errors import ProviderError, ProviderTimeoutError


# WHATSAPP_* settings from .env.
class WhatsAppSettings(BaseSettings):
    # Read WHATSAPP_* variables from .env and ignore the rest.
    model_config = SettingsConfigDict(env_prefix="WHATSAPP_", env_file=".env", extra="ignore")

    # Which version of Meta's Graph API to call.
    graph_version: str = "v21.0"
    # 🔒 WHATSAPP_ACCESS_TOKEN (hidden when printed).
    access_token: SecretStr | None = None
    # The WhatsApp business number's id at Meta.
    phone_number_id: str | None = None
    # 🔒 WHATSAPP_APP_SECRET: used to check webhook signatures.
    app_secret: SecretStr | None = None
    # 🔒 WHATSAPP_VERIFY_TOKEN: used when Meta first connects the webhook.
    verify_token: SecretStr | None = None


# The WhatsApp sender.
class WhatsAppSender:
    # This sender serves the WhatsApp channel.
    channel = Channel.WHATSAPP

    # Built with:
    def __init__(
        self,
        # the shared HTTP client,
        http: httpx.AsyncClient,
        *,
        access_token: str,
        # the business number's id,
        phone_number_id: str,
        # the Graph API version,
        graph_version: str = "v21.0",
        # and the time limit.
        timeout_s: float = 10.0,
    ) -> None:
        # Remember the HTTP client.
        self._http = http
        # Meta's 'send message' address for our number.
        self._url = f"https://graph.facebook.com/{graph_version}/{phone_number_id}/messages"
        # 🔒 The token travels in the Authorization header.
        self._headers = {"Authorization": f"Bearer {access_token}"}
        # Remember the time limit.
        self._timeout = timeout_s

    # Send one reply to a customer's number.
    async def send(self, tenant_id: str, recipient: str, message: OutboundMessage) -> None:
        # Try the call:
        try:
            # POST to Meta
            r = await self._http.post(
                # at the send address,
                self._url,
                # with the token header,
                headers=self._headers,
                # within the time limit,
                timeout=self._timeout,
                # sending JSON:
                json={
                    # the product name Meta requires,
                    "messaging_product": "whatsapp",
                    # the customer's number,
                    "to": recipient,
                    # a plain text message,
                    "type": "text",
                    # with this body.
                    "text": {"body": message.text},
                },
            )
            # An error status counts as a failure.
            r.raise_for_status()
        # Too slow:
        except httpx.TimeoutException as exc:
            # timed-out error.
            raise ProviderTimeoutError("whatsapp send timed out") from exc
        # Network problem or error status:
        except httpx.HTTPError as exc:
            # vendor error.
            raise ProviderError("whatsapp send failed") from exc
