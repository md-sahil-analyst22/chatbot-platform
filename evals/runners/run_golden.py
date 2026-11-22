# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: The golden-set eval runner (P2.15) and tuning sweep (P2.16).
#   1. Creates one eval tenant + bot per demo business on a THROWAWAY Postgres.
#   2. Ingests demos/<bot>/docs/* through the real IngestionService (parse, clean, chunk, embed).
#   3. Asks every golden question through the real AnswerService (FAQ -> hybrid search -> rerank
#      -> guardrail -> grounded answer with citations), as the RLS-bound app role.
#   4. Scores: answerable rows must be correct (LLM judge vs. expected key facts) AND cite the
#      expected source file; unanswerable rows must get "I'm not sure".
#   5. Writes evals/reports/<date>_golden_vN[_sweep].md + .json, with p50/p95/p99 latency.
# Sweep (--sweep): one answer run per chunk size with the confidence threshold off, then every
#   threshold is replayed from the recorded confidence (identical result, no extra LLM calls).
# 🔒 Safety: refuses any database host other than localhost (never Supabase, which local dev
#   shares with production). Uses the platform's vendor keys from .env (costs a little money);
#   --smoke uses offline stand-ins instead (no keys, no cost) to check the pipeline itself.
# Run from backend/:
#   uv run --env-file ../.env python ../evals/runners/run_golden.py \
#       --golden ../evals/golden/golden_v1.jsonl [--sweep] [--smoke]
#   with TEST_DATABASE_URL / TEST_APP_DATABASE_URL pointing at the throwaway database.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Golden-set eval runner and tuning sweep (P2.15, P2.16)."""

# Lets type hints name classes defined further down the file.
from __future__ import annotations

# argparse — reads the command-line options (--sweep, --smoke...).
import argparse

# asyncio — runs the async main().
import asyncio

# hashlib — word fingerprints for the offline stand-in embedder.
import hashlib

# json — reads the golden set and writes the JSON report.
import json

# os — reads the test database addresses from the environment.
import os

# re — regular expressions (words, citations, the judge's JSON).
import re

# sys — exits with a clear message when something isn't set up.
import sys

# time — measures how long each answer takes.
import time

# From collections.abc — Sequence = a read-only list type.
from collections.abc import Sequence

# From dataclasses — asdict = object -> dict (for the JSON report); dataclass = data classes;
#   field = per-field options; replace = copy with some fields changed.
from dataclasses import asdict, dataclass, field, replace

# From datetime — UTC = the UTC time zone; datetime = date + time (report names, config rows).
from datetime import UTC, datetime

# From pathlib — Path = a file-system path.
from pathlib import Path

# From typing — Any = any type.
from typing import Any

# From urllib.parse — urlsplit = splits a URL (to read the database host).
from urllib.parse import urlsplit

# From uuid — NAMESPACE_URL + uuid5 = stable ids from a name; UUID; uuid4 = random ids.
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

# httpx — the HTTP client the real vendor adapters use.
import httpx

# From sqlalchemy — text = a raw SQL snippet (to seed tenants and bots).
from sqlalchemy import text

# From sqlalchemy.ext.asyncio — async_sessionmaker = makes sessions; create_async_engine = opens
#   a connection pool.
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# From sqlalchemy.pool — NullPool = no pooling (a short-lived script).
from sqlalchemy.pool import NullPool

# From saathi.bootstrap.knowledge_bridge — the same wiring the worker and the chat use.
from saathi.bootstrap.knowledge_bridge import build_answer_service, build_ingestion_service

# From saathi.bootstrap.providers — builders for the real vendor clients.
from saathi.bootstrap.providers import (
    build_embedder,
    build_llm_resolver,
    build_parsers_by_extension,
    build_reranker,
)

# From saathi.modules.conversation.application.answer_service — AnswerKind; AnswerRequest.
from saathi.modules.conversation.application.answer_service import AnswerKind, AnswerRequest

# From saathi.modules.conversation.application.llm_resolver — LlmResolver; select_model.
from saathi.modules.conversation.application.llm_resolver import LlmResolver, select_model

# From saathi.modules.conversation.application.prompt_builder — TenantPromptParts.
from saathi.modules.conversation.application.prompt_builder import TenantPromptParts

# From saathi.modules.conversation.ports.llm — ChatMessage; LLMResponse.
from saathi.modules.conversation.ports.llm import ChatMessage, LLMResponse

# From saathi.modules.conversation.ports.retrieval — RetrievalRequest = search knobs.
from saathi.modules.conversation.ports.retrieval import RetrievalRequest

# From saathi.modules.knowledge.adapters.source_repository — SqlAlchemySourceRepository.
from saathi.modules.knowledge.adapters.source_repository import SqlAlchemySourceRepository

# From saathi.modules.knowledge.application.ingestion — IngestOutcome.
from saathi.modules.knowledge.application.ingestion import IngestOutcome

# From saathi.modules.knowledge.application.source_service — document_key = storage key.
from saathi.modules.knowledge.application.source_service import document_key

# From saathi.modules.knowledge.domain.entities — Source.
from saathi.modules.knowledge.domain.entities import Source

# From saathi.modules.knowledge.ports.providers — EmbedTask; RerankResult.
from saathi.modules.knowledge.ports.providers import EmbedTask, RerankResult

# From saathi.modules.tenancy.adapters.config_repository — SqlAlchemyBotConfigRepository.
from saathi.modules.tenancy.adapters.config_repository import SqlAlchemyBotConfigRepository

# From saathi.modules.tenancy.domain.bot_config — the bot configuration objects.
from saathi.modules.tenancy.domain.bot_config import (
    BotConfig,
    BotConfigVersion,
    Branding,
    ConfigStatus,
    GenerationSettings,
    PromptSettings,
    RetrievalSettings,
)

# From saathi.platform.config.model_catalog — ModelCatalog; ModelOption; default_catalog.
from saathi.platform.config.model_catalog import ModelCatalog, ModelOption, default_catalog

# From saathi.platform.config.settings — get_settings = the app settings (.env).
from saathi.platform.config.settings import get_settings

# From saathi.platform.db.tenant_context — tenant_session = a session locked to one tenant (RLS).
from saathi.platform.db.tenant_context import tenant_session

# From saathi.platform.errors — ConfigurationError = missing settings; NotFoundError = 404.
from saathi.platform.errors import ConfigurationError, NotFoundError

# The repository root (two folders up from evals/runners/).
REPO = Path(__file__).resolve().parents[2]
# Where reports are written (git-ignored).
REPORTS = REPO / "evals" / "reports"
# Database hosts this runner may write to (throwaway databases only).
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
# Golden 'lang' -> reply language code (Hinglish/Banglish reply in English).
REPLY_LANGUAGE = {"hi": "hi", "bn": "bn"}
# Phase 2 exit criterion: at least 80% correct with the right source...
TARGET_CORRECT_WITH_SOURCE = 0.80
# ...and every unanswerable question gets "I'm not sure".
TARGET_UNANSWERABLE_UNSURE = 1.0


# ───────────────────────────── offline stand-ins (--smoke) ─────────────────────────────


# Offline embedder: words -> positions in a 1,536-number vector.
class SmokeEmbedder:
    """Deterministic word-hash vectors (1,536 numbers): similar words -> similar vectors."""

    # Part of the source fingerprint.
    model_name = "smoke-hash"

    # One vector per text.
    async def embed(self, texts: Sequence[str], *, task: EmbedTask) -> list[list[float]]:
        # The vectors.
        out = []
        # Each text...
        for t in texts:
            # ...starts as all zeros...
            v = [0.0] * 1536
            # ...each word adds 1 at the position its fingerprint picks...
            for word in re.findall(r"\w+", t.lower()):
                # Add it.
                v[int(hashlib.sha256(word.encode()).hexdigest(), 16) % 1536] += 1.0
            # ...then the vector is scaled to length 1.
            norm = sum(x * x for x in v) ** 0.5 or 1.0
            # Keep it.
            out.append([x / norm for x in v])
        # All vectors.
        return out


# Offline reranker: score = share of question words found in the passage.
class SmokeReranker:
    """Score = share of question words found in the document."""

    # Best top_n passages first.
    async def rerank(self, query: str, documents: Sequence[str], top_n: int) -> list[RerankResult]:
        # The question's words.
        words = set(re.findall(r"\w+", query.lower()))
        # Each passage's share of those words.
        scored = [
            RerankResult(i, len(words & set(re.findall(r"\w+", d.lower()))) / max(1, len(words)))
            for i, d in enumerate(documents)
        ]
        # Best first, at most top_n.
        return sorted(scored, key=lambda r: -r.score)[:top_n]


# Offline LLM: answers with passage [1]'s first line; the judge always says 'correct'.
class SmokeLlm:
    """Answers with the first context passage's first line, cited as [1]; grades by overlap."""

    # Same contract as a real completion client.
    async def complete(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        # Called as the judge?
        if "GRADER" in system:
            # Always 'correct' (smoke mode checks plumbing, not quality).
            return LLMResponse('{"correct": true, "reason": "smoke"}', model, 0, 0)
        # The first line of passage [1] in the prompt.
        match = re.search(r"\[1\] Source: [^\n]*\n([^\n]+)", system)
        # Cite it, or say NO_ANSWER when there is no passage.
        reply = f"{match.group(1)} [1]" if match else "NO_ANSWER"
        # The reply.
        return LLMResponse(reply, model, 0, 0)


# Offline credentials: every provider has a dummy key.
class SmokeCredentials:
    # The key for any tenant/provider.
    async def api_key_for(self, tenant_id: str, provider: str) -> str | None:
        # A dummy key.
        return "smoke"


# ───────────────────────────── data ─────────────────────────────


# One golden question (one line of the JSONL file).
@dataclass(frozen=True)
class Row:
    # Unique id, e.g. 'tm-001'.
    id: str
    # 'taxmitra' or 'cliniccare'.
    bot: str
    # en / hi / bn / hinglish / banglish.
    lang: str
    # What the customer types.
    question: str
    # Key facts the answer must contain (None if unanswerable).
    expected_answer: str | None
    # The document the answer must cite (None if unanswerable).
    expected_source: str | None
    # False = the bot must say it is not sure.
    answerable: bool
    # e.g. 'hours', 'fees', 'refusal'.
    category: str


# What happened to one question.
@dataclass
class Result:
    # The golden id.
    id: str
    # The bot.
    bot: str
    # The language.
    lang: str
    # Was it answerable?
    answerable: bool
    # faq / grounded / unsure.
    kind: str
    # Why 'unsure' (None otherwise).
    reason: str | None
    # Retrieval confidence.
    confidence: float | None
    # Titles of the cited sources.
    cited: list[str]
    # Did it cite the expected source?
    source_match: bool
    # The judge's verdict (None if not judged).
    correct: bool | None
    # Answer time in milliseconds.
    latency_ms: float
    # The answer text.
    answer: str


# The score of one configuration.
@dataclass
class Score:
    # e.g. 'chunk=700 thr=0.3'.
    label: str
    # How many answerable questions.
    answerable_total: int
    # How many of them were correct AND cited the right source.
    correct_with_source: int
    # How many unanswerable questions.
    unanswerable_total: int
    # How many of them got 'not sure'.
    unanswerable_unsure: int
    # Answerable questions that wrongly got 'not sure'.
    false_unsure: int
    # Extra facts (the sweep stores chunk size and threshold here).
    extras: dict[str, Any] = field(default_factory=dict)

    # Share of answerable questions answered correctly with the right source.
    @property
    def correct_with_source_rate(self) -> float:
        # Divide safely.
        return self.correct_with_source / max(1, self.answerable_total)

    # Share of unanswerable questions that got 'not sure'.
    @property
    def unsure_rate(self) -> float:
        # Divide safely.
        return self.unanswerable_unsure / max(1, self.unanswerable_total)

    # Does this configuration meet the Phase 2 exit criteria?
    @property
    def passes(self) -> bool:
        # Both targets met.
        return (
            self.correct_with_source_rate >= TARGET_CORRECT_WITH_SOURCE
            and self.unsure_rate >= TARGET_UNANSWERABLE_UNSURE
        )


# Read the golden JSONL file.
def load_golden(path: Path) -> list[Row]:
    # The rows.
    rows = []
    # Each line...
    for line in path.read_text(encoding="utf-8").splitlines():
        # ...that isn't blank...
        if line.strip():
            # ...is one JSON object...
            d = json.loads(line)
            # ...of which we keep the Row fields (extra keys like expected_behavior are ignored).
            rows.append(Row(**{k: d[k] for k in Row.__dataclass_fields__}))
    # All rows.
    return rows


# Nearest-rank percentile of a list of numbers.
def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile (p50/p95/p99), never the average (CLAUDE.md observability)."""
    # Nothing measured.
    if not values:
        # Zero.
        return 0.0
    # Smallest to largest.
    ordered = sorted(values)
    # The value at that rank (bounded to the list).
    return ordered[min(len(ordered) - 1, max(0, round(pct / 100 * len(ordered)) - 1))]


# Score a run; with a threshold, grounded answers below it count as 'not sure'.
def score(results: list[Result], threshold: float | None, label: str) -> Score:
    """Score results; with `threshold`, answers below it are replayed as 'unsure'."""
    # Start at zero.
    s = Score(label, 0, 0, 0, 0, 0)
    # Each result...
    for r in results:
        # ...'not sure' if it was, or if its confidence is below the replayed threshold.
        unsure = r.kind == AnswerKind.UNSURE.value or (
            threshold is not None
            and r.kind == AnswerKind.GROUNDED.value
            and (r.confidence or 0.0) < threshold
        )
        # Answerable questions:
        if r.answerable:
            # count it;
            s.answerable_total += 1
            # 'not sure' on an answerable question is a miss;
            if unsure:
                # Count it.
                s.false_unsure += 1
            # correct AND right source is a hit.
            elif r.correct and r.source_match:
                # Count it.
                s.correct_with_source += 1
        # Unanswerable questions:
        else:
            # count it;
            s.unanswerable_total += 1
            # 'not sure' is the right answer.
            s.unanswerable_unsure += int(unsure)
    # The score.
    return s


# ───────────────────────────── the run ─────────────────────────────


# 🔒 Exit unless the database URL points at this machine.
def _require_local(url: str, name: str) -> None:
    # The host name ('+asyncpg' removed so urlsplit understands the scheme).
    host = urlsplit(url.replace("+asyncpg", "")).hostname or ""
    # Not local -> refuse (never Supabase).
    if host not in LOCAL_HOSTS:
        # Stop with a clear message.
        sys.exit(f"refusing to run: {name} must point at a local throwaway database, not '{host}'")


# Stable tenant and bot ids for a demo business.
def _bot_ids(slug: str) -> tuple[UUID, UUID]:
    # Stable ids per demo bot, so every run replaces the previous eval data.
    return uuid5(NAMESPACE_URL, f"saathi-eval:tenant:{slug}"), uuid5(
        NAMESPACE_URL, f"saathi-eval:bot:{slug}"
    )


# Ask the judge model whether an answer states the expected facts.
async def _judge(llm: Any, model: str, row: Row, answer: str) -> bool:
    """LLM-as-judge: does the answer state the expected key facts without contradicting them?"""
    # The grading instructions (strict JSON reply).
    system = (
        "You are a strict GRADER of a customer-support bot. Reply with JSON only: "
        '{"correct": true|false, "reason": "<short>"}. correct=true only if the ANSWER states '
        "the EXPECTED facts (any language, any wording) and contradicts none of them. Extra "
        "correct detail is fine."
    )
    # The question, expected facts and answer.
    user = f"QUESTION: {row.question}\nEXPECTED: {row.expected_answer}\nANSWER: {answer}"
    # Ask (temperature 0 = as repeatable as possible).
    response = await llm.complete(
        system=system,
        messages=[ChatMessage("user", user)],
        model=model,
        temperature=0.0,
        max_tokens=200,
    )
    # The JSON object in the reply.
    match = re.search(r"\{.*\}", response.text, re.S)
    # Read 'correct'; anything unreadable counts as wrong.
    try:
        # True/False from the JSON.
        return bool(json.loads(match.group(0))["correct"]) if match else False
    # Broken JSON or missing key.
    except (ValueError, KeyError):
        # Wrong.
        return False


# One full run with one configuration.
async def run_config(
    *,
    rows: list[Row],
    retrieval: RetrievalSettings,
    model_key: str,
    owner_url: str,
    app_url: str,
    providers: dict[str, Any],
    judge: bool,
) -> list[Result]:
    """Fresh eval tenants -> publish config -> ingest demo docs -> answer every question."""
    # Owner connection (only to seed tenants and bots, like an operator).
    owner = create_async_engine(owner_url, poolclass=NullPool)
    # App-role connection (RLS applies, like production).
    app = create_async_engine(app_url, poolclass=NullPool)
    # Sessions for the app role.
    app_sm = async_sessionmaker(app, expire_on_commit=False)
    # The model catalog.
    catalog: ModelCatalog = providers["catalog"]
    # The concrete model (used for the judge).
    selection = select_model(catalog, model_key, temperature=0.0, max_output_tokens=200)
    # The results.
    results: list[Result] = []
    # Always close the connections at the end.
    try:
        # Each demo business in the golden set...
        for slug in sorted({r.bot for r in rows}):
            # ...its stable ids...
            tenant, bot = _bot_ids(slug)
            # ...its bot.json (name, persona)...
            meta = json.loads((REPO / "demos" / slug / "bot.json").read_text(encoding="utf-8"))
            # ...fresh tenant + bot rows (owner only seeds, like an operator).
            async with owner.begin() as conn:
                # Remove the previous run's data (cascades to everything of that tenant).
                await conn.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tenant})
                # The tenant.
                await conn.execute(
                    text("INSERT INTO tenants (id, name) VALUES (:t, :n)"),
                    {"t": tenant, "n": f"eval-{slug}"},
                )
                # The bot.
                await conn.execute(
                    text(
                        "INSERT INTO bots (id, tenant_id, name, languages, public_key) "
                        "VALUES (:b, :t, :n, ARRAY['en','hi','bn'], :k)"
                    ),
                    {
                        "b": bot,
                        "t": tenant,
                        "n": meta["bot"]["name"],
                        "k": f"pk_eval_{slug}_{uuid4().hex[:12]}",
                    },
                )
            # The configuration under test.
            config = BotConfig(
                prompt=PromptSettings(persona=meta["bot"]["persona"][:1000]),
                generation=GenerationSettings(model_key=model_key),
                branding=Branding(header_title=meta["bot"]["name"]),
                retrieval=retrieval,
            )
            # Published as version 1 (the worker reads chunk settings from it).
            async with tenant_session(app_sm, tenant) as s:
                # Save it.
                await SqlAlchemyBotConfigRepository(s).add(
                    BotConfigVersion(
                        uuid4(),
                        tenant,
                        bot,
                        1,
                        ConfigStatus.PUBLISHED,
                        config,
                        "eval",
                        datetime.now(UTC),
                    )
                )
            # Ingest every demo document through the real use case.
            store = providers["store"]()
            # The real ingestion wiring.
            service = build_ingestion_service(
                sessionmaker=app_sm,
                store=store,
                parsers=providers["parsers"],
                crawler=providers["crawler"],
                embedder=providers["embedder"],
                pool=_NoQueue(),
            )
            # Each document...
            for doc in sorted((REPO / "demos" / slug / "docs").iterdir()):
                # ...its tenant-prefixed key...
                key = document_key(tenant, bot, doc.name)
                # ...its bytes stored...
                await store.put(key, doc.read_bytes(), "text/plain")
                # ...a queued source titled with the file name (the expected_source)...
                source = Source(
                    id=uuid4(), tenant_id=tenant, bot_id=bot, kind="file", uri=key, title=doc.name
                )
                # ...saved through RLS...
                async with tenant_session(app_sm, tenant) as s:
                    # Save.
                    await SqlAlchemySourceRepository(s).add(source)
                # ...and processed inline.
                outcome = await service.ingest(tenant, source.id)
                # Anything but 'done' means the eval can't be trusted.
                if outcome is not IngestOutcome.DONE:
                    # Stop.
                    raise RuntimeError(f"ingestion of {doc.name} ended with {outcome}")
            # The tenant's prompt text.
            prompt = TenantPromptParts(
                bot_name=meta["bot"]["name"],
                business_name=meta["tenant"]["name"],
                persona=config.prompt.persona,
            )
            # Each golden question for this bot...
            for row in (r for r in rows if r.bot == slug):
                # ...as an answer request with the configuration's knobs.
                request = AnswerRequest(
                    tenant_id=tenant,
                    bot_id=bot,
                    question=row.question,
                    language=REPLY_LANGUAGE.get(row.lang, "en"),
                    prompt=prompt,
                    model_key=model_key,
                    temperature=0.0,
                    max_output_tokens=400,
                    retrieval=RetrievalRequest(
                        retrieval.vector_top_k,
                        retrieval.keyword_top_k,
                        retrieval.rerank_top_n,
                        retrieval.faq_threshold,
                    ),
                    confidence_threshold=retrieval.confidence_threshold,
                    config_version=1,
                )
                # Start the clock.
                started = time.perf_counter()
                # Answer in one tenant-bound transaction (like the chat will).
                async with tenant_session(app_sm, tenant) as s:
                    # The real answer use case.
                    answer = await build_answer_service(
                        s,
                        embedder=providers["embedder"],
                        reranker=providers["reranker"],
                        llm=providers["llm"],
                        catalog=catalog,
                    ).answer(request)
                # Milliseconds taken.
                latency = (time.perf_counter() - started) * 1000
                # Titles of the cited sources.
                cited = [c.source_title for c in answer.citations]
                # The judge's verdict (only for answerable questions that got an answer).
                correct = None
                # Judge it?
                if row.answerable and answer.kind is not AnswerKind.UNSURE:
                    # Ask the judge (or count as correct with --no-judge).
                    correct = (
                        await _judge(providers["judge"], selection.model_id, row, answer.text)
                        if judge
                        else True
                    )
                # Record the result.
                results.append(
                    Result(
                        row.id,
                        slug,
                        row.lang,
                        row.answerable,
                        answer.kind.value,
                        answer.reason.value if answer.reason else None,
                        answer.confidence,
                        cited,
                        bool(row.expected_source and row.expected_source in cited),
                        correct,
                        round(latency, 1),
                        answer.text,
                    )
                )
    # Close both connection pools.
    finally:
        # Owner.
        await owner.dispose()
        # App.
        await app.dispose()
    # All results.
    return results


# Stand-in for the ARQ pool: the eval runs ingestion inline.
class _NoQueue:
    """The eval runs ingestion inline; nothing is queued."""

    # Accept and ignore.
    async def enqueue_job(self, *args: Any, **kwargs: Any) -> None:
        # Nothing to do.
        return None


# In-memory file storage for the eval (demo files are read from disk).
class _MemoryStore:
    # Empty store.
    def __init__(self) -> None:
        # key -> bytes.
        self.objects: dict[str, bytes] = {}

    # Save bytes.
    async def put(self, key: str, data: bytes, content_type: str) -> None:
        # Keep them.
        self.objects[key] = data

    # Read bytes.
    async def get(self, key: str) -> bytes:
        # Missing -> 404 (like the real store).
        if key not in self.objects:
            # 404.
            raise NotFoundError("missing")
        # The bytes.
        return self.objects[key]

    # Delete bytes.
    async def delete(self, key: str) -> None:
        # Remove if present.
        self.objects.pop(key, None)

    # Private store: no public URLs.
    def public_url(self, key: str) -> str | None:
        # None.
        return None


# The vendor clients: offline stand-ins (--smoke) or the real ones from .env.
def build_providers(smoke: bool, http: httpx.AsyncClient) -> dict[str, Any]:
    # Offline mode:
    if smoke:
        # One fake LLM for answers and judging.
        llm = SmokeLlm()
        # A catalog with one fake model as 'standard'.
        catalog = ModelCatalog(
            [
                ModelOption(
                    "standard",
                    "Smoke",
                    "smoke",
                    "smoke-model",
                    1000,
                    frozenset({"starter", "growth", "pro"}),
                )
            ]
        )
        # The offline set.
        return {
            "embedder": SmokeEmbedder(),
            "reranker": SmokeReranker(),
            "judge": llm,
            "catalog": catalog,
            "llm": LlmResolver(lambda provider, key: llm, SmokeCredentials()),
            "parsers": build_parsers_by_extension(),
            "crawler": None,
            "store": _MemoryStore,
        }
    # Real mode: settings from .env.
    settings = get_settings()
    # Build the embedder and reranker (fail with a clear message if keys are missing).
    try:
        # Both from the registries (EMBEDDING_PROVIDER, RERANKER_PROVIDER).
        embedder, reranker = build_embedder(settings, http), build_reranker(settings, http)
    # A key is missing (e.g. COHERE_API_KEY).
    except ConfigurationError as exc:
        # Stop with the reason and the offline alternative.
        sys.exit(
            f"cannot run real evals: {exc.message} (use --smoke for an offline pipeline check)"
        )
    # The per-bot LLM resolver with the platform keys.
    resolver = build_llm_resolver(http)
    # The real catalog (GEMINI_MODEL_* from .env).
    catalog = default_catalog()
    # The real set.
    return {
        "embedder": embedder,
        "reranker": reranker,
        "catalog": catalog,
        "llm": resolver,
        "judge": _JudgeClient(resolver, catalog),
        "parsers": build_parsers_by_extension(),
        "crawler": None,
        "store": _MemoryStore,
    }


# The judge uses the platform's 'standard' model through the normal resolver.
class _JudgeClient:
    """The judge uses the platform's 'standard' model through the normal resolver."""

    # Keep the resolver and catalog.
    def __init__(self, resolver: LlmResolver, catalog: ModelCatalog) -> None:
        # Both.
        self._resolver, self._catalog = resolver, catalog

    # Same contract as a completion client.
    async def complete(self, **kwargs: Any) -> LLMResponse:
        # The 'standard' model.
        selection = select_model(self._catalog, "standard", temperature=0.0, max_output_tokens=200)
        # A client for it.
        client = await self._resolver.resolve("eval", selection)
        # Ask.
        return await client.complete(**kwargs)


# Write <date>_<name>.json and .md into evals/reports/; return the .md path.
def write_report(name: str, payload: dict[str, Any], markdown: str) -> Path:
    # Make sure the folder exists.
    REPORTS.mkdir(parents=True, exist_ok=True)
    # e.g. '2026-11-22_golden_v1'.
    stem = f"{datetime.now(UTC):%Y-%m-%d}_{name}"
    # The full data as JSON (Indic text kept readable).
    (REPORTS / f"{stem}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # The readable summary.
    path = REPORTS / f"{stem}.md"
    # Write it.
    path.write_text(markdown, encoding="utf-8")
    # Its path.
    return path


# Header of the score table.
TABLE_HEADER = (
    "| config | correct + right source | unanswerable -> unsure | false unsure | Phase 2 exit |"
)


# One markdown line per question.
def result_row(r: Result) -> str:
    """One markdown line per question."""
    # Confidence with two decimals ('' if none).
    conf = "" if r.confidence is None else f"{r.confidence:.2f}"
    # The table line.
    return (
        f"| {r.id} | {r.lang} | {r.answerable} | {r.kind} | {r.reason or ''} | {conf} | "
        f"{', '.join(r.cited)} | {r.source_match} | {r.correct} |"
    )


# One markdown line per configuration score.
def summarise(s: Score) -> str:
    # Hits/total (rate) for both criteria, misses, and PASS/fail.
    return (
        f"| {s.label} | {s.correct_with_source}/{s.answerable_total} "
        f"({s.correct_with_source_rate:.0%}) | {s.unanswerable_unsure}/{s.unanswerable_total} "
        f"({s.unsure_rate:.0%}) | {s.false_unsure} | {'PASS' if s.passes else 'fail'} |"
    )


# Read the options, run the eval (or the sweep) and write the report.
async def main() -> None:
    # The command-line options.
    p = argparse.ArgumentParser(description=__doc__)
    # Which golden file.
    p.add_argument("--golden", type=Path, default=REPO / "evals/golden/golden_v1.jsonl")
    # Which catalog model the bots use.
    p.add_argument("--model-key", default="standard")
    # Chunk size (default: the platform default).
    p.add_argument("--chunk-size", type=int, default=RetrievalSettings().chunk_size_tokens)
    # Chunk overlap.
    p.add_argument("--overlap", type=float, default=RetrievalSettings().chunk_overlap_ratio)
    # Confidence threshold.
    p.add_argument(
        "--confidence-threshold", type=float, default=RetrievalSettings().confidence_threshold
    )
    # Passages kept after reranking.
    p.add_argument("--rerank-top-n", type=int, default=RetrievalSettings().rerank_top_n)
    # Tuning sweep instead of one run.
    p.add_argument("--sweep", action="store_true", help="tune chunk size and threshold (P2.16)")
    # Offline stand-ins.
    p.add_argument("--smoke", action="store_true", help="offline stand-ins: no keys, no cost")
    # Skip the judge.
    p.add_argument("--no-judge", action="store_true", help="skip the LLM judge (correct = cited)")
    # Parse them.
    args = p.parse_args()

    # The throwaway database addresses (owner and app role).
    owner_url, app_url = (
        os.environ.get("TEST_DATABASE_URL", ""),
        os.environ.get("TEST_APP_DATABASE_URL", ""),
    )
    # Both are required.
    if not (owner_url and app_url):
        # Stop with instructions.
        sys.exit(
            "set TEST_DATABASE_URL and TEST_APP_DATABASE_URL "
            "(throwaway database, see docs/runbooks/local-setup.md)"
        )
    # 🔒 Owner URL must be local...
    _require_local(owner_url, "TEST_DATABASE_URL")
    # ...and so must the app URL.
    _require_local(app_url, "TEST_APP_DATABASE_URL")
    # The golden questions.
    rows = load_golden(args.golden)
    # The configuration from the options.
    base = RetrievalSettings(
        chunk_size_tokens=args.chunk_size,
        chunk_overlap_ratio=args.overlap,
        confidence_threshold=args.confidence_threshold,
        rerank_top_n=args.rerank_top_n,
    )
    # One HTTP client for all vendor calls (timeouts set, redirects off).
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=5.0), follow_redirects=False
    ) as http:
        # The vendor clients.
        providers = build_providers(args.smoke, http)
        # For report titles.
        mode = "smoke" if args.smoke else "real"
        # Arguments shared by every run.
        common = {
            "rows": rows,
            "model_key": args.model_key,
            "owner_url": owner_url,
            "app_url": app_url,
            "providers": providers,
            "judge": not args.no_judge,
        }
        # A single run:
        if not args.sweep:
            # Run it.
            results = await run_config(retrieval=base, **common)
            # Score it.
            s = score(
                results, None, f"chunk={base.chunk_size_tokens} thr={base.confidence_threshold}"
            )
            # All answer times.
            lat = [r.latency_ms for r in results]
            # The markdown report.
            md = [
                f"# Golden eval ({args.golden.name}, {mode})",
                "",
                f"Settings: {asdict(base)} | model key `{args.model_key}`",
                "",
                TABLE_HEADER,
                "|---|---|---|---|---|",
                summarise(s),
                "",
                "Answer latency (retrieval + LLM, ms): "
                f"p50 {percentile(lat, 50):.0f} | p95 {percentile(lat, 95):.0f} | "
                f"p99 {percentile(lat, 99):.0f}",
                "",
                "| id | lang | answerable | kind | reason | conf | cited | source ok | correct |",
                "|---|---|---|---|---|---|---|---|---|",
                *[result_row(r) for r in results],
            ]
            # Write the .md and .json.
            path = write_report(
                args.golden.stem + ("_smoke" if args.smoke else ""),
                {
                    "settings": asdict(base),
                    "score": asdict(s),
                    "results": [asdict(r) for r in results],
                },
                "\n".join(md) + "\n",
            )
            # Print the summary part.
            print("\n".join(md[:8]))
            # And where the report is.
            print(f"report: {path}")
            # Done.
            return
        # P2.16 sweep: one answer run per chunk size (threshold off), thresholds replayed.
        table: list[Score] = []
        # Raw results per chunk size (for the JSON report).
        raw: dict[str, Any] = {}
        # Each chunk size...
        for size in (400, 700, 1000):
            # ...with the threshold off (every answer is generated and its confidence kept)...
            settings = replace(base, chunk_size_tokens=size, confidence_threshold=0.0)
            # ...one run...
            results = await run_config(retrieval=settings, **common)
            # ...kept...
            raw[str(size)] = [asdict(r) for r in results]
            # ...then each threshold is replayed from the recorded confidence.
            for thr in (0.1, 0.2, 0.3, 0.4, 0.5):
                # Score with that threshold.
                sc = score(results, thr, f"chunk={size} thr={thr}")
                # Remember the settings.
                sc.extras = {"chunk": size, "threshold": thr}
                # Add to the table.
                table.append(sc)
        # Best = never invents (unsure rate first), then most correct, then fewest misses.
        best = max(
            table, key=lambda x: (x.unsure_rate, x.correct_with_source_rate, -x.false_unsure)
        )
        # The markdown report.
        md = [
            f"# Tuning sweep ({args.golden.name}, {mode})",
            "",
            TABLE_HEADER,
            "|---|---|---|---|---|",
            *[summarise(s) for s in table],
            "",
            f"Recommended: chunk_size_tokens={best.extras['chunk']}, "
            f"confidence_threshold={best.extras['threshold']}",
        ]
        # Write the .md and .json.
        path = write_report(
            args.golden.stem + "_sweep" + ("_smoke" if args.smoke else ""),
            {"table": [asdict(s) for s in table], "results": raw},
            "\n".join(md) + "\n",
        )
        # Print the table.
        print("\n".join(md))
        # And where the report is.
        print(f"report: {path}")


# Run main() when started as a script.
if __name__ == "__main__":
    # Start the event loop.
    asyncio.run(main())
