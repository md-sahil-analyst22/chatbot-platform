# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Saves unanswered questions in Postgres (implements UnansweredLog, P2.14).
# 🔒 The session must come from tenant_session(); row-level security rejects a row whose
#    tenant_id differs from the session's tenant.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""SQL unanswered-question log."""

# From sqlalchemy.ext.asyncio — async database sessions: AsyncSession = one session.
from sqlalchemy.ext.asyncio import AsyncSession

# From saathi.modules.conversation.adapters.orm — conversation tables: UnansweredQuestionRow.
from saathi.modules.conversation.adapters.orm import UnansweredQuestionRow

# From saathi.modules.conversation.ports.unanswered — unanswered log: UnansweredQuestion = one
#   record.
from saathi.modules.conversation.ports.unanswered import UnansweredQuestion

# Longest question stored (matches the column).
_MAX_QUESTION = 2000
# Longest language code stored (matches the column).
_MAX_LANGUAGE = 10


# The repository.
class SqlAlchemyUnansweredLog:
    """Implements UnansweredLog. Inserts inside the caller's transaction."""

    # Keep the session.
    def __init__(self, session: AsyncSession) -> None:
        # The tenant-bound session.
        self._session = session

    # Save one unanswered question.
    async def record(self, item: UnansweredQuestion) -> None:
        # Stage the row (text bounded to the column sizes).
        self._session.add(
            UnansweredQuestionRow(
                tenant_id=item.tenant_id,
                bot_id=item.bot_id,
                conversation_id=item.conversation_id,
                question=item.question[:_MAX_QUESTION],
                language=item.language[:_MAX_LANGUAGE],
                reason=item.reason.value,
                top_score=item.top_score,
                config_version=item.config_version,
            )
        )
        # Send it now so errors surface here, not at commit.
        await self._session.flush()
