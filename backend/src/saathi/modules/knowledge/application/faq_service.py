# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Managing a bot's FAQs (question + exact answer), P2.12.
# Embedding: each FAQ question is turned into a vector when it is saved, so a customer question
#   with the same meaning can be matched at once. The answer text is never embedded (it is
#   returned word for word).
# If the embedding service is down: saving fails with a clear error (nothing half-saved).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""FAQ use cases (create, list, update, delete)."""

# From uuid — unique ids (UUIDs): UUID = the unique-id type; uuid4 = make a new random id.
from uuid import UUID, uuid4

# From saathi.modules.knowledge.domain.faq — FAQ entity: Faq = one question + exact answer.
from saathi.modules.knowledge.domain.faq import Faq

# From saathi.modules.knowledge.ports.external — outside needs: BotDirectory = does the bot exist.
from saathi.modules.knowledge.ports.external import BotDirectory

# From saathi.modules.knowledge.ports.providers — vendor contracts: Embedder = text -> vectors.
from saathi.modules.knowledge.ports.providers import Embedder

# From saathi.modules.knowledge.ports.repositories — storage contracts: FaqRepository = FAQs.
from saathi.modules.knowledge.ports.repositories import FaqRepository

# From saathi.platform.errors — our error types: NotFoundError = 404.
from saathi.platform.errors import NotFoundError

# From saathi.platform.security.auth — who is calling: Principal = verified user + tenant + role;
#   Role = owner/admin/viewer; require_role = 403 unless the role is high enough.
from saathi.platform.security.auth import Principal, Role, require_role

# At most 200 FAQs per list call (R28: bounded lists).
MAX_LIST = 200


# The use cases.
class FaqService:
    # Receive every collaborator through the constructor (R21).
    def __init__(self, *, faqs: FaqRepository, bots: BotDirectory, embedder: Embedder) -> None:
        # FAQ storage.
        self._faqs = faqs
        # Bot existence check.
        self._bots = bots
        # Embedding provider (for FAQ questions).
        self._embedder = embedder

    # One vector for an FAQ question. Stored FAQs are matched against customer QUESTIONS, so
    #   both sides are embedded as 'query' (symmetric question-to-question similarity).
    async def _embed_question(self, question: str) -> list[float]:
        # One text in, one vector out.
        return (await self._embedder.embed([question], task="query"))[0]

    # Load one of the caller's FAQs of this bot, or 404.
    async def _require_faq(self, principal: Principal, bot_id: UUID, faq_id: UUID) -> Faq:
        # Filtered by tenant (R15).
        faq = await self._faqs.get(principal.tenant_id, faq_id)
        # Missing, another tenant's or another bot's (all 404, R29).
        if faq is None or faq.bot_id != bot_id:
            # 404.
            raise NotFoundError("faq not found")
        # Found.
        return faq

    # Add an FAQ to a bot.
    async def create(self, principal: Principal, bot_id: UUID, question: str, answer: str) -> Faq:
        # Admins only.
        require_role(principal, Role.ADMIN)
        # The bot must be the caller's (404 otherwise).
        if not await self._bots.exists(principal.tenant_id, bot_id):
            # 404.
            raise NotFoundError("bot not found")
        # Build (and validate) the FAQ. 🔒 Tenant from the token (R8).
        faq = Faq(
            id=uuid4(),
            tenant_id=principal.tenant_id,
            bot_id=bot_id,
            question=question,
            answer=answer,
        )
        # Embed the question, then save both together.
        await self._faqs.add(faq, await self._embed_question(faq.question))
        # The new FAQ.
        return faq

    # A bot's FAQs.
    async def list_faqs(self, principal: Principal, bot_id: UUID, limit: int = 100) -> list[Faq]:
        # Viewers may look.
        require_role(principal, Role.VIEWER)
        # The bot must be the caller's.
        if not await self._bots.exists(principal.tenant_id, bot_id):
            # 404.
            raise NotFoundError("bot not found")
        # Bounded list (R28).
        return await self._faqs.list_for_bot(principal.tenant_id, bot_id, min(limit, MAX_LIST))

    # Change an FAQ's text and/or switch it on/off. None = leave unchanged.
    async def update(
        self,
        principal: Principal,
        bot_id: UUID,
        faq_id: UUID,
        *,
        question: str | None = None,
        answer: str | None = None,
        is_active: bool | None = None,
    ) -> Faq:
        # Admins only.
        require_role(principal, Role.ADMIN)
        # 404 if missing or another tenant's.
        old = await self._require_faq(principal, bot_id, faq_id)
        # New text (validated by the entity).
        faq = old.edited(question=question, answer=answer)
        # Switch on/off if asked.
        if is_active is not None:
            # New flag.
            faq = faq.with_active(is_active)
        # Re-embed only when the question really changed (saves a provider call).
        vector = await self._embed_question(faq.question) if faq.question != old.question else None
        # Save.
        await self._faqs.update(faq, vector)
        # The updated FAQ.
        return faq

    # Delete an FAQ.
    async def delete(self, principal: Principal, bot_id: UUID, faq_id: UUID) -> None:
        # Admins only.
        require_role(principal, Role.ADMIN)
        # 404 if missing or another tenant's/bot's.
        await self._require_faq(principal, bot_id, faq_id)
        # Filtered by tenant; nothing deleted (concurrent delete) -> 404.
        if not await self._faqs.delete(principal.tenant_id, faq_id):
            # 404.
            raise NotFoundError("faq not found")
