# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Saves FAQs and finds the closest active FAQ question in Postgres (implements
#       FaqRepository, P2.12).
# Matching: cosine similarity between the customer's question vector and each stored FAQ
#   question vector, for one bot. Bots have few FAQs (tens), so an exact scan through the
#   (tenant_id, bot_id) index is fast; no vector index is needed (R23: indexes only for real
#   needs).
# 🔒 Every query filters by tenant_id (R15) on top of row-level security.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""SQL FAQ repository."""

# From collections.abc — standard type names for collections: Sequence = read-only list type.
from collections.abc import Sequence

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# From sqlalchemy — SQLAlchemy, our database toolkit: delete = DELETE statement; select = SELECT
#   statement; update = UPDATE statement.
from sqlalchemy import delete, select, update

# From sqlalchemy.exc — database errors: IntegrityError = a constraint was violated.
from sqlalchemy.exc import IntegrityError

# From sqlalchemy.ext.asyncio — async database sessions: AsyncSession = one async session.
from sqlalchemy.ext.asyncio import AsyncSession

# From saathi.modules.knowledge.adapters.orm — knowledge tables: FaqRow = faqs table.
from saathi.modules.knowledge.adapters.orm import FaqRow

# From saathi.modules.knowledge.domain.faq — FAQ entity: Faq = one question + exact answer.
from saathi.modules.knowledge.domain.faq import Faq

# From saathi.modules.knowledge.ports.repositories — storage contracts: FaqMatch = closest FAQ.
from saathi.modules.knowledge.ports.repositories import FaqMatch

# From saathi.platform.db.errors — database error helper: violated_constraint = which rule fired.
from saathi.platform.db.errors import violated_constraint

# From saathi.platform.errors — our error types: NotFoundError = 404.
from saathi.platform.errors import NotFoundError

# The rule that the bot exists for this tenant (composite foreign key).
_BOT_FK = "fk_faqs_tenant_id_bots"


# Turn a row into a domain Faq.
def _to_domain(row: FaqRow) -> Faq:
    # Copy the fields.
    return Faq(
        id=row.id,
        tenant_id=row.tenant_id,
        bot_id=row.bot_id,
        question=row.question,
        answer=row.answer,
        is_active=row.is_active,
    )


# The repository.
class SqlAlchemyFaqRepository:
    """Implements FaqRepository. The session must come from tenant_session() (RLS bound)."""

    # Keep the session.
    def __init__(self, session: AsyncSession) -> None:
        # The tenant-bound session.
        self._session = session

    # Save a new FAQ with its question vector.
    async def add(self, faq: Faq, vector: Sequence[float]) -> None:
        # Stage the row.
        self._session.add(
            FaqRow(
                id=faq.id,
                tenant_id=faq.tenant_id,
                bot_id=faq.bot_id,
                question=faq.question,
                answer=faq.answer,
                is_active=faq.is_active,
                embedding=list(vector),
            )
        )
        # Send it now so constraint errors surface here.
        try:
            # Run the INSERT.
            await self._session.flush()
        # A rule was broken.
        except IntegrityError as exc:
            # The bot doesn't exist for this tenant.
            if violated_constraint(exc) == _BOT_FK:
                # 404.
                raise NotFoundError("bot not found") from exc
            # Anything else is a bug.
            raise

    # Save changes (and a new vector if the question changed).
    async def update(self, faq: Faq, vector: Sequence[float] | None) -> None:
        # The columns to write.
        values: dict[str, object] = {
            "question": faq.question,
            "answer": faq.answer,
            "is_active": faq.is_active,
        }
        # New question -> new vector.
        if vector is not None:
            # Store it.
            values["embedding"] = list(vector)
        # 🔒 UPDATE only this tenant's row.
        result = await self._session.execute(
            update(FaqRow)
            .where(FaqRow.id == faq.id, FaqRow.tenant_id == faq.tenant_id)
            .values(**values)
        )
        # Nothing updated: deleted meanwhile.
        if result.rowcount == 0:  # type: ignore[attr-defined]  # CursorResult for UPDATE
            # 404.
            raise NotFoundError("faq not found")

    # Delete one FAQ.
    async def delete(self, tenant_id: UUID, faq_id: UUID) -> bool:
        # 🔒 DELETE only this tenant's row.
        result = await self._session.execute(
            delete(FaqRow).where(FaqRow.id == faq_id, FaqRow.tenant_id == tenant_id)
        )
        # True if a row went away.
        return bool(result.rowcount)  # type: ignore[attr-defined]  # CursorResult for DELETE

    # Load one FAQ.
    async def get(self, tenant_id: UUID, faq_id: UUID) -> Faq | None:
        # 🔒 Tenant + id.
        row = await self._session.scalar(
            select(FaqRow).where(FaqRow.id == faq_id, FaqRow.tenant_id == tenant_id)
        )
        # Convert, or None.
        return _to_domain(row) if row is not None else None

    # A bot's FAQs, newest first.
    async def list_for_bot(self, tenant_id: UUID, bot_id: UUID, limit: int) -> list[Faq]:
        # serves: ix_faqs_tenant_bot.
        rows = await self._session.scalars(
            select(FaqRow)
            .where(FaqRow.tenant_id == tenant_id, FaqRow.bot_id == bot_id)
            .order_by(FaqRow.created_at.desc(), FaqRow.id)
            .limit(limit)
        )
        # Convert each.
        return [_to_domain(r) for r in rows]

    # The closest active FAQ question.
    async def best_match(
        self, tenant_id: UUID, bot_id: UUID, vector: Sequence[float]
    ) -> FaqMatch | None:
        # Cosine distance (0 = same meaning).
        distance = FaqRow.embedding.cosine_distance(list(vector))
        # serves: ix_faqs_tenant_bot (exact scan of one bot's few FAQs).
        row = (
            await self._session.execute(
                select(FaqRow, (1 - distance).label("similarity"))
                .where(
                    FaqRow.tenant_id == tenant_id,
                    FaqRow.bot_id == bot_id,
                    FaqRow.is_active.is_(True),
                    FaqRow.embedding.is_not(None),
                )
                .order_by(distance)
                .limit(1)
            )
        ).first()
        # No FAQ at all.
        if row is None:
            # No match.
            return None
        # The best FAQ and its similarity.
        return FaqMatch(faq=_to_domain(row[0]), similarity=float(row[1]))
