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


# A stand-in for the bots table: a Python dictionary instead of a database.
class InMemoryBotRepository:
    """BotRepository fake. Enforces the tenant filter exactly like the SQL adapter + RLS."""

    # Start empty.
    def __init__(self) -> None:
        # bot id -> Bot.
        self.rows: dict[UUID, Bot] = {}

    # Same rule as the database: is this name already used by ANOTHER bot of the same tenant?
    def _name_taken(self, bot: Bot) -> bool:
        # True if any stored bot...
        return any(
            b.tenant_id == bot.tenant_id and b.name == bot.name and b.id != bot.id
            for b in self.rows.values()
        )

    # Save a new bot.
    async def add(self, bot: Bot) -> None:
        # Name already used in this tenant...
        if self._name_taken(bot):
            # ...409, like the real database.
            raise ConflictError("a bot with this name already exists")
        # Store it.
        self.rows[bot.id] = bot

    # Save changes to a bot.
    async def update(self, bot: Bot) -> None:
        # Not found in this tenant...
        if await self.get(bot.tenant_id, bot.id) is None:
            # ...404.
            raise NotFoundError("bot not found")
        # Name already used...
        if self._name_taken(bot):
            # ...409.
            raise ConflictError("a bot with this name already exists")
        # Store the new version.
        self.rows[bot.id] = bot

    # Delete a bot.
    async def delete(self, tenant_id: UUID, bot_id: UUID) -> bool:
        # Not found in this tenant...
        if await self.get(tenant_id, bot_id) is None:
            # ...report that nothing was deleted.
            return False
        # Remove it.
        del self.rows[bot_id]
        # Report success.
        return True

    # Read one bot.
    async def get(self, tenant_id: UUID, bot_id: UUID) -> Bot | None:
        # Look it up by id.
        bot = self.rows.get(bot_id)
        # 🔒 Return it only if it belongs to the asking tenant (like row-level security).
        return bot if bot is not None and bot.tenant_id == tenant_id else None

    # This tenant's bots.
    async def list_for_tenant(self, tenant_id: UUID, limit: int) -> list[Bot]:
        # Only this tenant's, at most `limit`.
        return [b for b in self.rows.values() if b.tenant_id == tenant_id][:limit]


# A stand-in for the tenants table.
class InMemoryTenantRepository:
    # Optionally start with tenant -> plan.
    def __init__(self, plans: dict[UUID, str] | None = None) -> None:
        # Store them (empty if none given).
        self.plans = plans or {}

    # A tenant's plan.
    async def get_plan(self, tenant_id: UUID) -> str | None:
        # None if unknown.
        return self.plans.get(tenant_id)


# A stand-in for the bot_config_versions table.
class InMemoryBotConfigRepository:
    # Start empty.
    def __init__(self) -> None:
        # version id -> BotConfigVersion.
        self.rows: dict[UUID, BotConfigVersion] = {}

    # Helper: one bot's versions in this tenant, oldest first.
    def _of(self, tenant_id: UUID, bot_id: UUID) -> list[BotConfigVersion]:
        # Sort...
        return sorted(
            # every stored version of this bot in this tenant,
            (v for v in self.rows.values() if v.tenant_id == tenant_id and v.bot_id == bot_id),
            # ...by version number.
            key=lambda v: v.version,
        )

    # The next version number.
    async def next_version(self, tenant_id: UUID, bot_id: UUID) -> int:
        # This bot's versions.
        versions = self._of(tenant_id, bot_id)
        # Highest + 1, or 1 for the first.
        return versions[-1].version + 1 if versions else 1

    # Save a new version.
    async def add(self, version: BotConfigVersion) -> None:
        # That number already exists (like the database's unique rule)...
        if any(v.version == version.version for v in self._of(version.tenant_id, version.bot_id)):
            # ...409.
            raise ConflictError("the configuration was saved concurrently; try again")
        # Store it.
        self.rows[version.id] = version

    # Change a version's status.
    async def update_status(self, version: BotConfigVersion) -> None:
        # When publishing...
        if version.status is ConfigStatus.PUBLISHED:
            # ...look at the bot's other versions:
            others = self._of(version.tenant_id, version.bot_id)
            # if another one is already published (like the database's partial unique
            #   index)...
            if any(v.status is ConfigStatus.PUBLISHED and v.id != version.id for v in others):
                # Same outcome as the partial unique index in Postgres.
                raise ConflictError("another publish is in progress; try again")
        # Store the change.
        self.rows[version.id] = version

    # One version by number.
    async def get(self, tenant_id: UUID, bot_id: UUID, version: int) -> BotConfigVersion | None:
        # The first match, or None.
        return next((v for v in self._of(tenant_id, bot_id) if v.version == version), None)

    # The newest draft.
    async def latest_draft(self, tenant_id: UUID, bot_id: UUID) -> BotConfigVersion | None:
        # All drafts, oldest first.
        drafts = [v for v in self._of(tenant_id, bot_id) if v.status is ConfigStatus.DRAFT]
        # The last one, or None.
        return drafts[-1] if drafts else None

    # The live version.
    async def published(self, tenant_id: UUID, bot_id: UUID) -> BotConfigVersion | None:
        # The first published one, or None.
        return next(
            (v for v in self._of(tenant_id, bot_id) if v.status is ConfigStatus.PUBLISHED), None
        )

    # The version history.
    async def list_versions(
        self, tenant_id: UUID, bot_id: UUID, limit: int
    ) -> list[BotConfigVersion]:
        # Newest first, at most `limit`.
        return list(reversed(self._of(tenant_id, bot_id)))[:limit]


# A stand-in for the widget-key lookup function.
class InMemoryPublicBotLookup:
    # Optionally start with key -> (tenant, bot).
    def __init__(self, keys: dict[str, PublicBotRef] | None = None) -> None:
        # Store them.
        self.keys = keys or {}

    # Look a key up.
    async def resolve(self, public_key: str) -> PublicBotRef | None:
        # None if unknown.
        return self.keys.get(public_key)


# A stand-in for the provider_credentials table.
class InMemoryCredentialRepository:
    # Start empty.
    def __init__(self) -> None:
        # credential id -> (record, encrypted key).
        self.rows: dict[UUID, tuple[ProviderCredential, str]] = {}

    # Save a new key.
    async def add(self, credential: ProviderCredential, ciphertext: str) -> None:
        # Store the record and the encrypted key.
        self.rows[credential.id] = (credential, ciphertext)

    # Save changes to a record.
    async def save(self, credential: ProviderCredential) -> None:
        # Keep the existing encrypted key...
        _, ciphertext = self.rows[credential.id]
        # ...and store the updated record with it.
        self.rows[credential.id] = (credential, ciphertext)

    # The active key for a tenant + vendor.
    async def active(self, tenant_id: UUID, provider: str) -> tuple[ProviderCredential, str] | None:
        # The first match, or None:
        return next(
            # each (record, encrypted key)
            (
                (c, ct)
                for c, ct in self.rows.values()
                if c.tenant_id == tenant_id
                and c.provider == provider
                and c.status is CredentialStatus.ACTIVE
            ),
            # or None if nothing matches.
            None,
        )

    # One record.
    async def get(self, tenant_id: UUID, credential_id: UUID) -> ProviderCredential | None:
        # Look it up.
        found = self.rows.get(credential_id)
        # 🔒 Only if it belongs to the asking tenant.
        return found[0] if found and found[0].tenant_id == tenant_id else None

    # All records of a tenant.
    async def list_for_tenant(self, tenant_id: UUID) -> list[ProviderCredential]:
        # Only this tenant's.
        return [c for c, _ in self.rows.values() if c.tenant_id == tenant_id]
