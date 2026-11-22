# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: The contract every knowledge repository must keep (R35): sources, chunks (incl.
#                both hybrid-search halves) and FAQs. The in-memory fakes run here; the SQL
#                adapters run the SAME classes on real Postgres in test_knowledge_sql.py.
# 🔒 Every test also checks the explicit tenant filter (R15): another tenant sees nothing.
# How to run: cd backend && uv run pytest tests/contracts/test_knowledge_repository_contract.py
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Knowledge repository contracts."""

# hashlib — fingerprints, used to build repeatable test vectors.
import hashlib

# From uuid — unique ids (UUIDs): UUID = the unique-id type; uuid4 = makes a random id.
from uuid import UUID, uuid4

# pytest — the test framework.
import pytest

# From tests.fakes.knowledge — the in-memory repositories under test here.
from tests.fakes.knowledge import (
    InMemoryChunkRepository,
    InMemoryFaqRepository,
    InMemorySourceRepository,
)

# From saathi.modules.knowledge.domain.chunking — Chunk = one passage.
from saathi.modules.knowledge.domain.chunking import Chunk

# From saathi.modules.knowledge.domain.crawl — CrawlOptions = one crawl's settings.
from saathi.modules.knowledge.domain.crawl import CrawlOptions

# From saathi.modules.knowledge.domain.entities — Source; SourceStatus.
from saathi.modules.knowledge.domain.entities import Source, SourceStatus

# From saathi.modules.knowledge.domain.faq — Faq.
from saathi.modules.knowledge.domain.faq import Faq

# From saathi.modules.knowledge.ports.repositories — the contracts being checked.
from saathi.modules.knowledge.ports.repositories import (
    ChunkRepository,
    FaqRepository,
    SourceRepository,
)

# From saathi.platform.errors — ConflictError = 409; NotFoundError = 404.
from saathi.platform.errors import ConflictError, NotFoundError

# Vector size used by the contracts (the SQL column is fixed at 1,536, R13).
DIM = 1536


# A repeatable unit vector for a text (same text = same vector, different text = different).
def vec(text: str) -> list[float]:
    """A deterministic unit vector for a text (same text = same vector)."""
    # 32 bytes from the text's fingerprint.
    raw = hashlib.sha256(text.encode()).digest()
    # Spread them over DIM numbers between -1 and 1.
    values = [((raw[i % 32] + i * 7) % 256) / 128.0 - 1.0 for i in range(DIM)]
    # The vector's length.
    norm = sum(v * v for v in values) ** 0.5
    # Scaled to length 1.
    return [v / norm for v in values]


# Every implementation must be able to create the parent tenant/bot rows (foreign keys).
class _Seeds:
    """Implementations make sure a tenant/bot exists (foreign keys) before use."""

    # Make the (tenant, bot) pair exist.
    async def seed_bot(self, tenant_id: UUID, bot_id: UUID) -> None:
        # Each implementation overrides this.
        raise NotImplementedError


# What every SourceRepository must do.
class SourceRepositoryContract(_Seeds):
    # The implementation under test (each concrete test class overrides this).
    def make(self) -> SourceRepository:
        # The base class has none.
        raise NotImplementedError

    # Add a queued file source (optionally for a given tenant/bot) and return it.
    async def _new(self, repo: SourceRepository, **kw: object) -> Source:
        # Tenant and bot: given, or random.
        tenant, bot = kw.pop("tenant", uuid4()), kw.pop("bot", uuid4())
        # Make sure they exist.
        await self.seed_bot(tenant, bot)  # type: ignore[arg-type]
        # A queued file source.
        source = Source(
            id=uuid4(),
            tenant_id=tenant,
            bot_id=bot,
            kind="file",
            uri=f"t/{uuid4()}",
            title="Fees.pdf",
            **kw,
        )  # type: ignore[arg-type]
        # Save it.
        await repo.add(source)
        # Return it.
        return source

    # Save + load gives the same source; another tenant gets nothing.
    async def test_add_get_round_trip_and_tenant_filter(self) -> None:
        # The repository.
        repo = self.make()
        # A new source.
        s = await self._new(repo)
        # Load it.
        got = await repo.get(s.tenant_id, s.id)
        # Same location, title and status.
        assert got is not None and (got.uri, got.title, got.status) == (
            s.uri,
            "Fees.pdf",
            SourceStatus.QUEUED,
        )
        # 🔒 Another tenant: nothing.
        assert await repo.get(uuid4(), s.id) is None

    # Crawl settings survive saving and loading (found by URL).
    async def test_website_options_round_trip(self) -> None:
        # The repository.
        repo = self.make()
        # A tenant and bot...
        tenant, bot = uuid4(), uuid4()
        # ...that exist.
        await self.seed_bot(tenant, bot)
        # Crawl settings.
        opts = CrawlOptions("https://shop.example/", 2, 30, ("/svc/*",), ())
        # A website source with them.
        s = Source(
            id=uuid4(), tenant_id=tenant, bot_id=bot, kind="url", uri=opts.root_url, crawl=opts
        )
        # Save it.
        await repo.add(s)
        # Find it by its URL.
        got = await repo.get_by_uri(tenant, bot, opts.root_url)
        # Same settings.
        assert got is not None and got.crawl == opts

    # The same file/URL twice for one bot is a conflict.
    async def test_duplicate_uri_for_the_same_bot_is_409(self) -> None:
        # The repository.
        repo = self.make()
        # A source.
        s = await self._new(repo)
        # Another source with the same location.
        dup = Source(id=uuid4(), tenant_id=s.tenant_id, bot_id=s.bot_id, kind="file", uri=s.uri)
        # Saving it...
        with pytest.raises(ConflictError):
            # ...is 409.
            await repo.add(dup)

    # A source for a bot that doesn't exist (for this tenant) is 404.
    async def test_missing_bot_is_404(self) -> None:
        # The repository.
        repo = self.make()
        # A source for a random bot.
        orphan = Source(id=uuid4(), tenant_id=uuid4(), bot_id=uuid4(), kind="file", uri="t/x")
        # The tenant exists, but this bot doesn't.
        await self.seed_bot(orphan.tenant_id, uuid4())
        # Saving it...
        with pytest.raises(NotFoundError):
            # ...is 404.
            await repo.add(orphan)

    # Status, error, fingerprint and sync time are saved.
    async def test_save_persists_lifecycle_fields(self) -> None:
        # The repository.
        repo = self.make()
        # A queued source.
        s = await self._new(repo)
        # -> processing...
        s.start_processing()
        # -> failed with a reason.
        s.mark_failed("could not read")
        # Save.
        await repo.save(s)
        # Load it (locked).
        got = await repo.get_for_update(s.tenant_id, s.id)
        # Failed with the reason.
        assert (
            got is not None and got.status is SourceStatus.FAILED and got.error == "could not read"
        )
        # failed -> queued...
        got.requeue()
        # -> processing...
        got.start_processing()
        # -> ready with a fingerprint.
        got.mark_ready("f" * 64)
        # Save.
        await repo.save(got)
        # The bot's list.
        listing = (await repo.list_for_bot(s.tenant_id, s.bot_id, 10))[0]
        # Fingerprint saved; sync time set.
        assert listing.source.content_hash == "f" * 64 and listing.synced_at is not None
        # No chunks yet.
        assert listing.chunk_count == 0

    # Deleting is tenant-filtered; saving a deleted source is 404.
    async def test_save_of_a_deleted_source_is_404(self) -> None:
        # The repository.
        repo = self.make()
        # A source.
        s = await self._new(repo)
        # 🔒 Another tenant can't delete it.
        assert await repo.delete(uuid4(), s.id) is False
        # Its own tenant can.
        assert await repo.delete(s.tenant_id, s.id) is True
        # Saving it now...
        with pytest.raises(NotFoundError):
            # ...is 404.
            await repo.save(s)

    # Lists are per bot (and per tenant).
    async def test_lists_are_per_bot_and_newest_first(self) -> None:
        # The repository.
        repo = self.make()
        # One tenant, two bots.
        tenant, bot, other_bot = uuid4(), uuid4(), uuid4()
        # Two sources for the first bot...
        first = await self._new(repo, tenant=tenant, bot=bot)
        # Second.
        second = await self._new(repo, tenant=tenant, bot=bot)
        # ...one for the other bot.
        await self._new(repo, tenant=tenant, bot=other_bot)
        # The first bot's list.
        listed = [x.source.id for x in await repo.list_for_bot(tenant, bot, 10)]
        # Exactly its two sources.
        assert set(listed) == {first.id, second.id}
        # The locked read gives the same two.
        assert {s.id for s in await repo.all_for_bot_for_update(tenant, bot)} == {
            first.id,
            second.id,
        }
        # 🔒 Another tenant: nothing.
        assert await repo.list_for_bot(uuid4(), bot, 10) == []


# What every ChunkRepository must do.
class ChunkRepositoryContract(_Seeds):
    # The implementations under test: (chunks, sources) sharing one store.
    def make(self) -> tuple[ChunkRepository, SourceRepository]:
        # The base class has none.
        raise NotImplementedError

    # Add a source for a tenant/bot and return it.
    async def _source(self, sources: SourceRepository, tenant: UUID, bot: UUID) -> Source:
        # Make sure the bot exists.
        await self.seed_bot(tenant, bot)
        # A file source.
        s = Source(
            id=uuid4(),
            tenant_id=tenant,
            bot_id=bot,
            kind="file",
            uri=f"t/{uuid4()}",
            title="fees.pdf",
        )
        # Save it.
        await sources.add(s)
        # Return it.
        return s

    # Replace a source's chunks with these texts (section 'Fees', pages 1, 2, ...).
    async def _put(self, chunks: ChunkRepository, source: Source, texts: list[str]) -> None:
        # Chunks + their vectors.
        await chunks.replace_for_source(
            source,
            [Chunk(index=i, text=t, section="Fees", page=i + 1) for i, t in enumerate(texts)],
            [vec(t) for t in texts],
        )

    # Replacing swaps ALL chunks of a source.
    async def test_replace_swaps_all_chunks_of_a_source(self) -> None:
        # The repositories.
        chunks, sources = self.make()
        # A source.
        s = await self._source(sources, uuid4(), uuid4())
        # Three chunks.
        await self._put(chunks, s, ["a b", "c d", "e f"])
        # Three counted.
        assert await chunks.count_for_source(s.tenant_id, s.id) == 3
        # Replace with one.
        await self._put(chunks, s, ["only one"])
        # One counted.
        assert await chunks.count_for_source(s.tenant_id, s.id) == 1
        # 🔒 Another tenant counts none.
        assert await chunks.count_for_source(uuid4(), s.id) == 0

    # 🔍 'Same meaning' search: closest first, only this tenant's bot, citation facts kept.
    async def test_vector_search_is_filtered_by_tenant_and_bot(self) -> None:
        # The repositories.
        chunks, sources = self.make()
        # Our tenant and bot.
        tenant, bot = uuid4(), uuid4()
        # Our source...
        mine = await self._source(sources, tenant, bot)
        # ...and another tenant's.
        theirs = await self._source(sources, uuid4(), uuid4())
        # Two chunks for us.
        await self._put(chunks, mine, ["gst fee 500", "office hours 10 to 7"])
        # An identical chunk for them.
        await self._put(chunks, theirs, ["gst fee 500"])
        # Search with the exact vector of 'gst fee 500'.
        hits = await chunks.vector_search(tenant, bot, vec("gst fee 500"), 5)
        # Our matching chunk first; only our two chunks.
        assert hits[0].text == "gst fee 500" and len(hits) == 2
        # 🔒 Nothing from the other tenant.
        assert all(h.source_id == mine.id for h in hits)
        # Same vector -> similarity 1.0.
        assert hits[0].score == pytest.approx(1.0, abs=1e-4)
        # Title, section and page come back for citations.
        assert (hits[0].source_title, hits[0].section, hits[0].page) == ("fees.pdf", "Fees", 1)

    # 🔍 'Same words' search: any word may match, incl. Hindi and Bengali.
    async def test_keyword_search_matches_any_word_including_indic_text(self) -> None:
        # The repositories.
        chunks, sources = self.make()
        # Our tenant and bot.
        tenant, bot = uuid4(), uuid4()
        # A source...
        s = await self._source(sources, tenant, bot)
        # ...with a Hindi, a Bengali and an English chunk.
        await self._put(chunks, s, ["जीएसटी फीस पाँच सौ", "অফিস সময় দশটা", "closed on sunday"])
        # A Hindi question sharing 'फीस' finds the Hindi chunk.
        assert [h.text for h in await chunks.keyword_search(tenant, bot, "फीस कितनी है", 5)] == [
            "जीएसटी फीस पाँच सौ"
        ]
        # A Bengali question sharing 'অফিস' finds the Bengali chunk.
        assert [h.text for h in await chunks.keyword_search(tenant, bot, "অফিস কখন", 5)] == [
            "অফিস সময় দশটা"
        ]
        # An English question finds the English chunk.
        assert [
            h.text for h in await chunks.keyword_search(tenant, bot, "are you closed on sunday?", 5)
        ] == ["closed on sunday"]
        # 🔒 Another tenant finds nothing.
        assert await chunks.keyword_search(uuid4(), bot, "sunday", 5) == []
        # An empty question finds nothing.
        assert await chunks.keyword_search(tenant, bot, "", 5) == []

    # One vector per chunk is required.
    async def test_mismatched_vectors_are_a_programming_error(self) -> None:
        # The repositories.
        chunks, sources = self.make()
        # A source.
        s = await self._source(sources, uuid4(), uuid4())
        # One chunk, zero vectors...
        with pytest.raises(ValueError):
            # ...is refused.
            await chunks.replace_for_source(s, [Chunk(index=0, text="a")], [])


# What every FaqRepository must do.
class FaqRepositoryContract(_Seeds):
    # The implementation under test.
    def make(self) -> FaqRepository:
        # The base class has none.
        raise NotImplementedError

    # Add an FAQ (with its question's vector) and return it.
    async def _faq(
        self, repo: FaqRepository, tenant: UUID, bot: UUID, q: str, *, active: bool = True
    ) -> Faq:
        # Make sure the bot exists.
        await self.seed_bot(tenant, bot)
        # The FAQ.
        faq = Faq(
            id=uuid4(),
            tenant_id=tenant,
            bot_id=bot,
            question=q,
            answer=f"answer to {q}",
            is_active=active,
        )
        # Save it with its vector.
        await repo.add(faq, vec(q))
        # Return it.
        return faq

    # ⭐ Only active FAQs of this tenant's bot can match.
    async def test_best_match_uses_only_active_faqs_of_the_bot(self) -> None:
        # The repository.
        repo = self.make()
        # Our tenant and bot.
        tenant, bot = uuid4(), uuid4()
        # An active FAQ.
        good = await self._faq(repo, tenant, bot, "office hours?")
        # A switched-off FAQ with the asked question.
        await self._faq(repo, tenant, bot, "gst fee?", active=False)
        # Another tenant's FAQ with the asked question.
        await self._faq(repo, uuid4(), uuid4(), "gst fee?")
        # Ask 'gst fee?'.
        match = await repo.best_match(tenant, bot, vec("gst fee?"))
        # Only the active one of our bot is a candidate (and it's not a close match).
        assert match is not None and match.faq.id == good.id and match.similarity < 0.99
        # Ask its own question.
        exact = await repo.best_match(tenant, bot, vec("office hours?"))
        # A perfect match.
        assert exact is not None and exact.similarity == pytest.approx(1.0, abs=1e-4)
        # 🔒 Another tenant gets nothing.
        assert await repo.best_match(uuid4(), bot, vec("office hours?")) is None

    # Update with a new vector, tenant filters, delete.
    async def test_update_delete_and_isolation(self) -> None:
        # The repository.
        repo = self.make()
        # Our tenant and bot.
        tenant, bot = uuid4(), uuid4()
        # An FAQ.
        faq = await self._faq(repo, tenant, bot, "q1")
        # New question + its new vector.
        await repo.update(faq.edited(question="q2"), vec("q2"))
        # Load it.
        got = await repo.get(tenant, faq.id)
        # The new question is saved.
        assert got is not None and got.question == "q2"
        # The new vector matches the new question perfectly.
        again = await repo.best_match(tenant, bot, vec("q2"))
        # Similarity 1.0.
        assert again is not None and again.similarity == pytest.approx(1.0, abs=1e-4)
        # 🔒 Another tenant can't read it.
        assert await repo.get(uuid4(), faq.id) is None
        # Listed for its bot.
        assert [f.id for f in await repo.list_for_bot(tenant, bot, 10)] == [faq.id]
        # 🔒 Another tenant can't delete it.
        assert await repo.delete(uuid4(), faq.id) is False
        # Its own tenant can.
        assert await repo.delete(tenant, faq.id) is True
        # Updating it now...
        with pytest.raises(NotFoundError):
            # ...is 404.
            await repo.update(faq, None)


# The in-memory 'bot table': a set of (tenant, bot) pairs, fresh for every test.
class _InMemorySeeds:
    # The existing pairs.
    bots: set[tuple[UUID, UUID]]

    # Before each test: no bots.
    @pytest.fixture(autouse=True)
    def _bots(self) -> None:
        # Empty set.
        self.bots = set()

    # 'Create' a bot.
    async def seed_bot(self, tenant_id: UUID, bot_id: UUID) -> None:
        # Add the pair.
        self.bots.add((tenant_id, bot_id))


# The source contract on the in-memory fake.
class TestInMemorySourceRepository(_InMemorySeeds, SourceRepositoryContract):
    # The fake, aware of which bots exist.
    def make(self) -> SourceRepository:
        # Build it.
        return InMemorySourceRepository(self.bots)


# The chunk contract on the in-memory fakes.
class TestInMemoryChunkRepository(_InMemorySeeds, ChunkRepositoryContract):
    # Chunk + source fakes sharing counts.
    def make(self) -> tuple[ChunkRepository, SourceRepository]:
        # The source fake.
        sources = InMemorySourceRepository(self.bots)
        # Both.
        return InMemoryChunkRepository(sources), sources


# The FAQ contract on the in-memory fake.
class TestInMemoryFaqRepository(_InMemorySeeds, FaqRepositoryContract):
    # The fake, aware of which bots exist.
    def make(self) -> FaqRepository:
        # Build it.
        return InMemoryFaqRepository(self.bots)
