# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Answers one question from a bot's knowledge, with citations (P2.13 + P2.14).
# Steps:
#   1. Retrieve: FAQ match or best passages (knowledge module, through a port).
#   2. ⭐ FAQ won -> reply with the FAQ answer word for word (no LLM call, no cost).
#   3. 🤷 Guardrail: nothing solid found -> "I'm not sure, want a human?" + log it.
#   4. 🤖 Otherwise build the system prompt with prompt_builder (platform rules first, tenant
#      text sealed, passages numbered [1]..[n] in <context>, R9) and ask the bot's model.
#   5. Check the reply: 'NO_ANSWER' or no valid [n] citation -> treated as unsupported ->
#      "I'm not sure" + log. Citation numbers that don't exist are removed.
# Failures: a provider that is down (embeddings, LLM) never crashes the chat: the reply is the
#   "I'm not sure" message and the question is logged (degrade gracefully).
# Not here yet: the live chat endpoint (P3.8). In Phase 2 this is used by the eval runner.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Grounded answer use case with citations and a confidence guardrail (P2.13, P2.14)."""

# re — regular expressions (citation markers like [2]).
import re

# From dataclasses — quick classes that mainly hold data: dataclass = decorator that writes
#   __init__ and friends for you; field = per-field options.
from dataclasses import dataclass, field

# From enum — fixed sets of named values: StrEnum = a fixed set of named text values.
from enum import StrEnum

# From uuid — unique ids (UUIDs): UUID = the unique-id type.
from uuid import UUID

# structlog — structured logging (JSON log lines).
import structlog

# From saathi.modules.conversation.application.guardrail — guardrail: assess = good enough?;
#   unsure_message = the localized 'not sure' reply.
from saathi.modules.conversation.application.guardrail import assess, unsure_message

# From saathi.modules.conversation.application.llm_resolver — per-bot model choice:
#   LlmResolver = gives a ready client; select_model = catalog key -> concrete model.
from saathi.modules.conversation.application.llm_resolver import LlmResolver, select_model

# From saathi.modules.conversation.application.prompt_builder — the ONLY place that builds the
#   system prompt (R9): TenantPromptParts = tenant text; build_system_prompt = the layered prompt.
from saathi.modules.conversation.application.prompt_builder import (
    TenantPromptParts,
    build_system_prompt,
)

# From saathi.modules.conversation.ports.llm — LLM contract: ChatMessage = one chat message.
from saathi.modules.conversation.ports.llm import ChatMessage

# From saathi.modules.conversation.ports.retrieval — retrieval contract: KnowledgeRetriever =
#   look things up; Passage = one passage; Retrieval = what was found; RetrievalRequest = knobs.
from saathi.modules.conversation.ports.retrieval import (
    KnowledgeRetriever,
    Passage,
    Retrieval,
    RetrievalRequest,
)

# From saathi.modules.conversation.ports.unanswered — unanswered log: UnansweredLog = store;
#   UnansweredQuestion = one record; UnansweredReason = why.
from saathi.modules.conversation.ports.unanswered import (
    UnansweredLog,
    UnansweredQuestion,
    UnansweredReason,
)

# From saathi.platform.config.model_catalog — models tenants may choose: ModelCatalog.
from saathi.platform.config.model_catalog import ModelCatalog

# From saathi.platform.errors — our error types: ConfigurationError = a provider isn't set up;
#   ProviderError = a vendor failed.
from saathi.platform.errors import ConfigurationError, ProviderError

# The logger for this file.
log = structlog.get_logger()

# The exact reply the platform rules ask for when the context has no answer.
NO_ANSWER = "NO_ANSWER"
# Citation markers: [1] .. [99].
_CITATION = re.compile(r"\[(\d{1,2})\]")
# Longest question we keep (chat messages are bounded at the edge too).
MAX_QUESTION_CHARS = 2000


# What kind of answer was given.
class AnswerKind(StrEnum):
    # An FAQ answer, word for word.
    FAQ = "faq"
    # Written by the model from cited passages.
    GROUNDED = "grounded"
    # "I'm not sure" (the question was logged).
    UNSURE = "unsure"


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# Everything needed to answer one question for one bot.
class AnswerRequest:
    # 🔒 From the verified caller (or the server-side widget-key lookup), never the request.
    tenant_id: UUID
    # The bot.
    bot_id: UUID
    # The customer's question.
    question: str
    # Reply language ('en', 'hi', 'bn').
    language: str
    # The tenant's prompt text (sealed by prompt_builder).
    prompt: TenantPromptParts
    # The bot's model catalog key ('standard'...).
    model_key: str
    # Sampling temperature from the bot's config.
    temperature: float
    # Reply length limit from the bot's config.
    max_output_tokens: int
    # Search knobs from the bot's config.
    retrieval: RetrievalRequest
    # Below this reranker score -> "I'm not sure".
    confidence_threshold: float
    # Which published config version this is (for logs/unanswered records).
    config_version: int | None = None
    # The conversation, when there is one (Phase 3).
    conversation_id: UUID | None = None


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# One source cited in the answer.
class Citation:
    # The [n] number used in the text.
    number: int
    # Source title.
    source_title: str
    # Page (or None).
    page: int | None
    # Web address (or None).
    url: str | None
    # Heading path.
    section: str


# @dataclass writes __init__; frozen=True makes it unchangeable.
@dataclass(frozen=True, slots=True)
# The answer.
class Answer:
    # faq / grounded / unsure.
    kind: AnswerKind
    # The reply text (citations as [n]).
    text: str
    # The cited sources (empty for unsure).
    citations: list[Citation] = field(default_factory=list)
    # Retrieval confidence, when known.
    confidence: float | None = None
    # Why it was 'unsure' (None otherwise).
    reason: UnansweredReason | None = None
    # The model that wrote it (grounded answers only).
    model: str | None = None
    # Tokens sent to the model.
    tokens_in: int = 0
    # Tokens produced by the model.
    tokens_out: int = 0


# Number the passages for the <context> block.
def format_context(passages: list[Passage]) -> str:
    """'[1] Source: price_list.pdf, page 2, section Fees' then the text, one block per passage."""
    # One block per passage.
    blocks: list[str] = []
    # Numbered from 1.
    for number, p in enumerate(passages, start=1):
        # Where it came from.
        where = [p.source_title or "document"]
        # Page, when known.
        if p.page is not None:
            # 'page 2'.
            where.append(f"page {p.page}")
        # Section, when known.
        if p.section:
            # 'section Fees > GST'.
            where.append(f"section {p.section}")
        # The block.
        blocks.append(f"[{number}] Source: {', '.join(where)}\n{p.text}")
    # Blank line between blocks.
    return "\n\n".join(blocks)


# Keep only valid citation numbers; return the cleaned text and the numbers used.
def extract_citations(text: str, passage_count: int) -> tuple[str, list[int]]:
    """Markers outside 1..passage_count are removed from the text."""
    # Numbers used, in first-seen order.
    used: list[int] = []

    # Replace one marker.
    def keep_or_drop(match: re.Match[str]) -> str:
        # Its number.
        n = int(match.group(1))
        # Not a real passage number: drop the marker.
        if not 1 <= n <= passage_count:
            # Remove it.
            return ""
        # Remember it (once).
        if n not in used:
            # Add it.
            used.append(n)
        # Keep the marker.
        return match.group(0)

    # Clean the text.
    cleaned = _CITATION.sub(keep_or_drop, text)
    # Tidy double spaces left by removed markers.
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip(), used


# The use case.
class AnswerService:
    # Receive every collaborator through the constructor (R21).
    def __init__(
        self,
        *,
        retriever: KnowledgeRetriever,
        llm: LlmResolver,
        catalog: ModelCatalog,
        unanswered: UnansweredLog,
    ) -> None:
        # Knowledge lookup.
        self._retriever = retriever
        # Per-bot model client.
        self._llm = llm
        # Model catalog.
        self._catalog = catalog
        # Unanswered log.
        self._unanswered = unanswered

    # Answer one question.
    async def answer(self, req: AnswerRequest) -> Answer:
        """Never raises for provider problems: they become an 'unsure' answer."""
        # Bounded question.
        question = req.question.strip()[:MAX_QUESTION_CHARS]
        # Step 1: retrieve.
        try:
            # FAQ or passages.
            found = await self._retriever.retrieve(
                req.tenant_id, req.bot_id, question, req.retrieval
            )
        # Embeddings (or search) unavailable: don't guess.
        except ProviderError as exc:
            # Log the type only.
            log.warning("answer.retrieval_unavailable", error_type=type(exc).__name__)
            # Not sure + log.
            return await self._unsure(req, question, UnansweredReason.PROVIDER_UNAVAILABLE, None)
        # Step 2: FAQ wins.
        if found.faq is not None:
            # The FAQ answer, word for word.
            return Answer(
                kind=AnswerKind.FAQ, text=found.faq.answer, confidence=found.faq.similarity
            )
        # Step 3: guardrail.
        reason = assess(found, req.confidence_threshold)
        # Not solid enough.
        if reason is not None:
            # Not sure + log.
            return await self._unsure(req, question, reason, found.confidence)
        # Step 4: generate.
        return await self._generate(req, question, found)

    # Step 4 + 5: ask the model and check its reply.
    async def _generate(self, req: AnswerRequest, question: str, found: Retrieval) -> Answer:
        # The concrete model for this bot (catalog key -> provider + model id).
        selection = select_model(
            self._catalog,
            req.model_key,
            temperature=req.temperature,
            max_output_tokens=req.max_output_tokens,
        )
        # R9: the system prompt comes only from prompt_builder (passages go into <context>).
        system = build_system_prompt(
            req.prompt, language=req.language, context=format_context(found.passages)
        )
        # Ask the model.
        try:
            # A client for the bot's provider.
            client = await self._llm.resolve(str(req.tenant_id), selection)
            # One completion.
            response = await client.complete(
                system=system,
                messages=[ChatMessage(role="user", content=question)],
                model=selection.model_id,
                temperature=selection.temperature,
                max_tokens=selection.max_output_tokens,
            )
        # Provider down or not configured: don't guess.
        except (ProviderError, ConfigurationError) as exc:
            # Log the type only.
            log.warning("answer.llm_unavailable", error_type=type(exc).__name__)
            # Not sure + log.
            return await self._unsure(
                req, question, UnansweredReason.PROVIDER_UNAVAILABLE, found.confidence
            )
        # Step 5: the model said the context has no answer.
        if NO_ANSWER in response.text:
            # Not sure + log.
            return await self._unsure(req, question, UnansweredReason.UNSUPPORTED, found.confidence)
        # Keep only real citation numbers.
        text, used = extract_citations(response.text, len(found.passages))
        # No valid citation = not grounded in the context: don't show it.
        if not used or not text:
            # Not sure + log.
            return await self._unsure(req, question, UnansweredReason.UNSUPPORTED, found.confidence)
        # The cited sources, in the order they were first cited.
        citations = [
            Citation(
                number=n,
                source_title=found.passages[n - 1].source_title,
                page=found.passages[n - 1].page,
                url=found.passages[n - 1].url,
                section=found.passages[n - 1].section,
            )
            for n in used
        ]
        # The grounded answer.
        return Answer(
            kind=AnswerKind.GROUNDED,
            text=text,
            citations=citations,
            confidence=found.confidence,
            model=response.model,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
        )

    # "I'm not sure" + log the question.
    async def _unsure(
        self,
        req: AnswerRequest,
        question: str,
        reason: UnansweredReason,
        top_score: float | None,
    ) -> Answer:
        # Record it for the business (same transaction as the caller's).
        await self._unanswered.record(
            UnansweredQuestion(
                tenant_id=req.tenant_id,
                bot_id=req.bot_id,
                question=question,
                language=req.language,
                reason=reason,
                top_score=top_score,
                config_version=req.config_version,
                conversation_id=req.conversation_id,
            )
        )
        # Log the decision (no question text: it may contain personal data, R18).
        log.info("answer.unsure", reason=reason.value, top_score=top_score)
        # The localized reply.
        return Answer(
            kind=AnswerKind.UNSURE,
            text=unsure_message(req.language),
            confidence=top_score,
            reason=reason,
        )
