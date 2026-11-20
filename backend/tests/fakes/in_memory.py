# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: In-memory versions of the repositories (a dict instead of a database table).
# How to run: Used automatically by the tests; nothing to run directly.
# ─────────────────────────────────────────────────────────────────────────────────────────────
# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From saathi.modules.credentials.domain.credential — the saved-API-key business object:
#   CredentialStatus = active or revoked; ProviderCredential = one saved key's details.
from saathi.modules.credentials.domain.credential import CredentialStatus, ProviderCredential

# From saathi.modules.tenancy.domain.bot_config — the bot configuration business objects:
#   BotConfigVersion = one saved version; ConfigStatus = draft/published/archived.
from saathi.modules.tenancy.domain.bot_config import BotConfigVersion, ConfigStatus

# From saathi.modules.tenancy.domain.entities — the Bot business object: Bot = one chatbot.
from saathi.modules.tenancy.domain.entities import Bot

# From saathi.modules.tenancy.ports.repositories — tenancy storage contracts: PublicBotRef =
#   tenant + bot for a widget key.
from saathi.modules.tenancy.ports.repositories import PublicBotRef

# From saathi.platform.errors — our error types: ConflictError = 409 clash with existing data;
#   NotFoundError = 404 not found.
from saathi.platform.errors import ConflictError, NotFoundError


class InMemoryBotRepository:
    """BotRepository fake. Enforces the tenant filter exactly like the SQL adapter + RLS."""

    def __init__(self) -> None:
        self.rows: dict[UUID, Bot] = {}

    def _name_taken(self, bot: Bot) -> bool:
        return any(
            b.tenant_id == bot.tenant_id and b.name == bot.name and b.id != bot.id
            for b in self.rows.values()
        )

    async def add(self, bot: Bot) -> None:
        if self._name_taken(bot):
            raise ConflictError("a bot with this name already exists")
        self.rows[bot.id] = bot

    async def update(self, bot: Bot) -> None:
        if await self.get(bot.tenant_id, bot.id) is None:
            raise NotFoundError("bot not found")
        if self._name_taken(bot):
            raise ConflictError("a bot with this name already exists")
        self.rows[bot.id] = bot

    async def delete(self, tenant_id: UUID, bot_id: UUID) -> bool:
        if await self.get(tenant_id, bot_id) is None:
            return False
        del self.rows[bot_id]
        return True

    async def get(self, tenant_id: UUID, bot_id: UUID) -> Bot | None:
        bot = self.rows.get(bot_id)
        return bot if bot is not None and bot.tenant_id == tenant_id else None

    async def list_for_tenant(self, tenant_id: UUID, limit: int) -> list[Bot]:
        return [b for b in self.rows.values() if b.tenant_id == tenant_id][:limit]


class InMemoryTenantRepository:
    def __init__(self, plans: dict[UUID, str] | None = None) -> None:
        self.plans = plans or {}

    async def get_plan(self, tenant_id: UUID) -> str | None:
        return self.plans.get(tenant_id)


class InMemoryBotConfigRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, BotConfigVersion] = {}

    def _of(self, tenant_id: UUID, bot_id: UUID) -> list[BotConfigVersion]:
        return sorted(
            (v for v in self.rows.values() if v.tenant_id == tenant_id and v.bot_id == bot_id),
            key=lambda v: v.version,
        )

    async def next_version(self, tenant_id: UUID, bot_id: UUID) -> int:
        versions = self._of(tenant_id, bot_id)
        return versions[-1].version + 1 if versions else 1

    async def add(self, version: BotConfigVersion) -> None:
        if any(v.version == version.version for v in self._of(version.tenant_id, version.bot_id)):
            raise ConflictError("the configuration was saved concurrently; try again")
        self.rows[version.id] = version

    async def update_status(self, version: BotConfigVersion) -> None:
        if version.status is ConfigStatus.PUBLISHED:
            others = self._of(version.tenant_id, version.bot_id)
            if any(v.status is ConfigStatus.PUBLISHED and v.id != version.id for v in others):
                # Same outcome as the partial unique index in Postgres.
                raise ConflictError("another publish is in progress; try again")
        self.rows[version.id] = version

    async def get(self, tenant_id: UUID, bot_id: UUID, version: int) -> BotConfigVersion | None:
        return next((v for v in self._of(tenant_id, bot_id) if v.version == version), None)

    async def latest_draft(self, tenant_id: UUID, bot_id: UUID) -> BotConfigVersion | None:
        drafts = [v for v in self._of(tenant_id, bot_id) if v.status is ConfigStatus.DRAFT]
        return drafts[-1] if drafts else None

    async def published(self, tenant_id: UUID, bot_id: UUID) -> BotConfigVersion | None:
        return next(
            (v for v in self._of(tenant_id, bot_id) if v.status is ConfigStatus.PUBLISHED), None
        )

    async def list_versions(
        self, tenant_id: UUID, bot_id: UUID, limit: int
    ) -> list[BotConfigVersion]:
        return list(reversed(self._of(tenant_id, bot_id)))[:limit]


class InMemoryPublicBotLookup:
    def __init__(self, keys: dict[str, PublicBotRef] | None = None) -> None:
        self.keys = keys or {}

    async def resolve(self, public_key: str) -> PublicBotRef | None:
        return self.keys.get(public_key)


class InMemoryCredentialRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, tuple[ProviderCredential, str]] = {}

    async def add(self, credential: ProviderCredential, ciphertext: str) -> None:
        self.rows[credential.id] = (credential, ciphertext)

    async def save(self, credential: ProviderCredential) -> None:
        _, ciphertext = self.rows[credential.id]
        self.rows[credential.id] = (credential, ciphertext)

    async def active(self, tenant_id: UUID, provider: str) -> tuple[ProviderCredential, str] | None:
        return next(
            (
                (c, ct)
                for c, ct in self.rows.values()
                if c.tenant_id == tenant_id
                and c.provider == provider
                and c.status is CredentialStatus.ACTIVE
            ),
            None,
        )

    async def get(self, tenant_id: UUID, credential_id: UUID) -> ProviderCredential | None:
        found = self.rows.get(credential_id)
        return found[0] if found and found[0].tenant_id == tenant_id else None

    async def list_for_tenant(self, tenant_id: UUID) -> list[ProviderCredential]:
        return [c for c, _ in self.rows.values() if c.tenant_id == tenant_id]
