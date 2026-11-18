# Instructions for Claude in this repository

**Before writing or changing code, read [`docs/REPO_STRUCTURE.md`](docs/REPO_STRUCTURE.md), Part 0 and Part 1.** It's the coding rulebook for this repo: where each kind of code goes (§0.5), 45 numbered rules with reasons and examples, and the "before you say done" checklist (§1.12).

**Source of truth, highest first (R44):** `docs/planning/` features → architecture → process flows → build plan → ADRs (`docs/adr/`) → code → tests. Code never silently redefines a requirement.

## Documents: what to read, and what to update in the same PR

| Document | Read it when | Update it in the same PR when |
|---|---|---|
| [`docs/REPO_STRUCTURE.md`](docs/REPO_STRUCTURE.md) | Before any code change (Part 0 + Part 1) | A rule, folder or known gap (§4.7/§4.8) changes |
| [`docs/CODE_GUIDE.md`](docs/CODE_GUIDE.md) | You need to know how existing code and flows work | **You add, rename or remove any class or function, or change a flow** (`make code-guide-check` must pass) |
| `docs/planning/` (00–05) | Scoping a task; checking phase order and exit criteria | Only with the owner's agreement (R44) |
| `docs/adr/` (0001–0008) | Touching vendors, auth, hosting, data model, public APIs | A hard-to-undo decision is made or amended (R43) |
| [`docs/runbooks/vps-deploy.md`](docs/runbooks/vps-deploy.md) | Anything about the server, Traefik, `setup.sh`, the production compose file | Deploy steps, server setup or production settings change |
| [`docs/runbooks/deploy-and-daily-operations.md`](docs/runbooks/deploy-and-daily-operations.md) | Release, check or troubleshoot the live system | Release commands, checks or troubleshooting change |
| [`docs/runbooks/local-setup.md`](docs/runbooks/local-setup.md) | Running the stack or the real-Postgres tests locally | Local setup changes |
| `.env.example` | Adding or reading a setting | Every new environment variable (name only, R12) |

## Decisions already made (change only with a new or amended ADR)

- **ADR-0002:** Supabase for Postgres, Auth and Storage. The app connects as `saathi_app` through the **session pooler (port 5432)**, never the transaction pooler.
- **ADR-0006:** Gemini is the primary LLM and embedding vendor (`gemini-embedding-2` at 1,536 dimensions, platform-wide, R13); Sarvam does speech (`saaras` STT, `bulbul` TTS); Cohere reranks. Any vendor plugs in through ports + registries.
- **ADR-0007:** logins are Supabase JWTs verified against JWKS (ES256/RS256 only); the tenant and role come from `resolve_user_membership()`, exactly one membership per user; staging/production refuse to start without `AUTH_*`.
- **ADR-0008:** production is a single Hostinger VPS (n8n template). The front door is the server's **existing Traefik, shared with n8n: never stop, replace or reconfigure Traefik or n8n.** Saathi is routed by Traefik labels from `SAATHI_BASE_DOMAIN`. Releases are **manual** (no CI system has server access).

## Production facts

- Live: `https://api.saathi.sahil-aisolution.cloud` (API) and `https://app.saathi.sahil-aisolution.cloud` (Bot Studio). Health check: `/health`; `/docs` is off in production.
- Release on the server, from `~/Projects/chatbot-platform` as root: `docker compose --env-file .env -f infra/docker-compose.prod.yml down` → `git pull` → `... up -d --build`. `up` runs the migration first; the API starts only if it succeeds. Never `down -v`.
- Today deploys are **single-server and manual**, not rolling (ADR-0008); the "rolling deploys" and "Nginx `real_ip`" wording under *Production concerns* applies once we scale. Trusted proxy headers come from Traefik via `FORWARDED_ALLOW_IPS` (the fixed Docker gateway).
- ⚠️ Local development and production currently share the **same Supabase database**: never run destructive SQL or experimental migrations against it from a laptop. Real-Postgres tests use a throwaway database (`make test-db`), never Supabase.
- Secrets live only in `.env` files (git-ignored) and Supabase. Never print, log, commit or paste them into chats or PRs.

## The rules you must never break

- **R3:** `domain/` is plain Python: no FastAPI, SQLAlchemy, pydantic, httpx or Redis.
- **R4:** modules never import each other (use a port wired in `bootstrap/`, a facade with an ADR, or an event).
- **R6:** only a module's `api/deps.py` imports adapters; routes stay thin.
- **R7:** vendors only through ports + registries, chosen by configuration.
- **R8:** the tenant comes from the verified token (or the server-side widget-key lookup), never from the request.
- **R9:** the system prompt is built only by `prompt_builder.py`: platform rules first, tenant text sealed in `<tenant_instructions>`, retrieved text in `<context>`, angle brackets neutralised.
- **R10:** `/public/v1` returns an explicit, minimal response model. Never prompts, model names, plan or internal ids.
- **R14:** no tenant-specific code (`if tenant == ...`). Differences between tenants are configuration.
- **R15 / R23:** every query filters by `tenant_id`; every tenant table has `tenant_id NOT NULL`, forced RLS and tenant-scoped unique constraints.
- **R16:** fail closed: missing auth, key, signature or permission means deny.
- **R17:** secrets never in code, logs, errors or responses.
- **R19:** all outside input is untrusted: `extra="forbid"`, bounded lengths, uploads checked by real bytes (no SVG), webhooks verified before anything else.
- **R24 / R25:** the app connects as `saathi_app` only; schema changes only through Alembic migrations with a working `downgrade()`.
- **R29:** raise typed errors from `saathi.platform.errors`; no stack traces or internals to clients; another tenant's resource returns 404.

## How every piece of code is designed

Apply all of these to every change, however small. When they pull against each other, **security wins**.

- **Security first, at any cost.** Never trade security for speed, convenience or a shorter diff. Validate all input, deny by default (R16), least privilege everywhere (R24), tenant isolation in code *and* database (R8, R15, R23), no secrets or personal data in logs or responses (R17, R18). If the secure way is unclear, stop and ask.
- **SOLID.**
  - *Single responsibility:* one reason to change per class or module.
  - *Open/closed:* add vendors and features by adding code (ports + registries, R7), not by editing working code.
  - *Liskov:* every adapter and fake passes its port's contract suite (R35).
  - *Interface segregation:* small `Protocol`s (R21).
  - *Dependency inversion:* business code depends on ports; concrete classes are injected through constructors and wired only in `api/deps.py` / `bootstrap/` (R6, R21).
  - If a proposed design violates one of these, say which and why before implementing it.
- **Object-oriented design.** Domain objects protect their own rules, are immutable and change state only through named methods (R20). Encapsulate. Prefer composition over inheritance. Keep framework and vendor types out of `domain/` (R3).
- **Design patterns, when they solve a named problem.** Use the repo's established patterns: ports and adapters, registry + factory, repository, dependency injection, value objects, state machines. Don't invent a second way to do the same thing. Don't add a pattern or abstraction that solves no concrete problem you can name: that's over-engineering (R45).
- **System design.** Before writing code, think through scale and failure:
  - stateless API; name the scaling unit of anything you add (requests/s, open streams, queue depth, DB connections);
  - all I/O async (R32);
  - nothing slow in the chat reply path (R31). Ask: "must this happen before the customer sees the reply?" If not, it goes to the worker;
  - idempotent, bounded, tenant-scoped background jobs (R33);
  - timeouts on every outbound call;
  - one transaction per use case (R26);
  - indexes only for real queries, with a `-- serves:` comment (R23);
  - what happens when a dependency is down (fail closed, clear typed errors, R29).

## Working discipline: no guessing, no unnecessary changes, test first

### Don't guess
- Read the code before you describe it or change it. Never assume a function, file, setting, table, column, endpoint or library API exists, or how it behaves. Open it, search for it, or run it.
- Check vendor and library behaviour against the installed version (`uv.lock`, `package-lock.json`) or its official docs, not memory.
- If the requirement, the expected behaviour or the secure option is unclear, **stop and ask**. Don't fill the gap with an assumption. If you must proceed (for example, nobody is there to answer), write the assumption down in your reply and in the code or PR, and pick the option that's easiest to reverse.
- Never claim something works, passes or is fixed unless you ran it and saw the result. Say plainly what you couldn't run or verify.

### Don't alter what wasn't asked
- Change only what the task needs (R45). No drive-by refactors, renames, reformatting, dependency bumps, file moves or "improvements" outside the task. If you spot something worth fixing, report it and leave it alone.
- Don't change public behaviour as a side effect: API shapes, error codes, database schema, config keys, environment variable names, event payloads, `/public/v1` responses (R30).
- Never weaken a test, a lint rule, a type check or a CI step to make a change pass. If an existing test fails because of your change, assume your change is wrong until proven otherwise.
- Keep the diff small and reviewable. A diff that touches files unrelated to the task needs a reason for each one.

### Test before, during and after
1. **Before changing anything**, run the full quality gates (see "Before you finish") and record the result. That's the baseline. If something already fails, report it before you start, so pre-existing failures aren't mixed up with yours.
2. **Write or update the test first** where you can: a failing test that shows the bug or the missing behaviour, at the right layer (R34).
3. **After the change**, run all gates again: format, lint, types, import boundaries, unit, contract, integration, architecture, and dashboard typecheck/tests/build. Compare with the baseline. Nothing that passed before may fail now.
4. Cover the cases that matter for the change, not only the happy path:
   - **security:** 401 / 403 / wrong tenant → 404 / 422, smuggled `tenant_id`, injection, oversized input (R36);
   - **tenant isolation:** another tenant sees nothing, on real Postgres when tables are involved (R37);
   - **failure:** provider timeout, provider 5xx/429, Redis down, database error, duplicate and late events;
   - **concurrency:** two requests at once (double publish, duplicate webhook, re-run job);
   - **edge cases:** empty, maximum length, unicode and Hindi/Bengali text, missing optional fields, old stored JSON still loading (R22);
   - **migrations:** `upgrade` and `downgrade` both run on a real database (R25);
   - **performance**, when the change touches the chat path, a hot query or a job: measure p50/p95/p99 before and after, and check query plans for new queries.
5. In your reply, list exactly what you ran and the results. Don't summarise as "all good".

### Predict the impact before you change it
Before writing code, write a short impact analysis and include it in your reply:
- **Blast radius:** which modules, endpoints, jobs, tables, configs, the widget and Bot Studio this touches; who calls the code you're changing (search for every caller).
- **Compatibility:** does it break existing API clients, embedded widgets on tenants' sites, stored bot configs, queued jobs created by the old version, or data written before the change? Will it work during a rolling deploy, when old and new versions run side by side?
- **Future features:** check the plan in `docs/planning/` (`04_BUILD_PLAN.md`, `05_PHASEWISE_DEVELOPMENT_PLAN.md`) and name any upcoming feature this could block or make harder: for example WhatsApp and voice channels, tenants' own API keys (Phase 8), handoff, leads, analytics, more LLM or embedding vendors, a module later moving into its own service. Prefer the design that keeps those doors open, as long as it doesn't add abstraction nobody needs today (R45).
- **Risks:** security, tenant isolation, latency, cost (LLM tokens), data migration and rollback. Say how each is tested and how the change is rolled back if it goes wrong.
- If the analysis shows a real risk to current or planned features, raise it **before** implementing and recommend an alternative (R44).

## Production concerns the rulebook doesn't spell out yet

These aren't numbered rules in `REPO_STRUCTURE.md` yet, but they apply to every change.

- **Resilience.** Every outbound call (LLM, embeddings, reranker, WhatsApp, n8n, CRM) has connect and read timeouts. Retry only transient failures (timeouts, 429, 5xx) with a bounded attempt count, exponential backoff and jitter, and honour `Retry-After`. Never retry forever. When a provider keeps failing, degrade gracefully (the "I'm not sure, want a human?" path) rather than hanging the chat. On shutdown, stop taking new work and drain open SSE streams and running jobs.
- **Idempotency.** Anything that can be retried or delivered twice must be safe to replay: webhook processing (dedupe on the provider's message id), lead creation, job execution, outbound write-backs. Use a unique business constraint or an idempotency key, not "check then insert".
- **Database + queue consistency.** Enqueue jobs only *after* the transaction commits, and make the job tolerate a missing or changed row. Where losing the message is unacceptable (lead → n8n/CRM, billing events), use a transactional outbox table written in the same transaction and drained by the worker.
- **Webhooks, in and out.** Incoming: verify signature, then timestamp window (replay protection), then dedupe, then queue and return 200 fast. Outgoing (`lead.created` etc.): sign with HMAC, include a timestamp and event id, retry with backoff, record delivery status, keep failures in a dead-letter table for manual replay.
- **Caching.** For every cache, state what is cached, the key (always starting with the tenant: `t:{tenant_id}:...`), TTL, invalidation trigger (e.g. publish invalidates the published-config cache), the source of truth, and what happens when Redis is down. Non-security caches fall back to the database; security limits fail closed (R16).
- **Rate limiting.** Use the existing Redis token bucket in `platform/security/rate_limit.py`, never a new one. Say which kind each limit is: security (login, key validation), abuse (per IP / per widget key), business quota (plan limits), provider quota (LLM tokens/min), or concurrency (open streams per tenant). Keys are tenant-scoped; per-IP limits use the real client IP (see proxy headers below).
- **Outbound URLs and SSRF.** Any URL a tenant supplies (crawler, custom webhook tool, n8n target) is resolved and checked before every request: http/https only, no private, loopback, link-local or metadata addresses, re-checked after DNS, redirects off (the shared client already disables them, R11), size and time limits on the response.
- **LLM input and output.** Send providers only what the answer needs: no secrets, internal ids or other tenants' data. Treat model output as untrusted: the widget renders it as sanitised markdown/text, never raw HTML (same as R39), and tool calls the model asks for are validated against the bot's allowed tools and the caller's tenant.
- **Browser surfaces.** The widget's chat and config endpoints use a per-bot CORS origin allowlist; never `*` with credentials. Streaming endpoints check `Origin`.
- **Concurrency.** Name the race before writing code that updates shared rows: use the partial unique index plus `IntegrityError → ConflictError`, `SELECT ... FOR UPDATE`, or an optimistic `version` column. Avoid N+1 queries (batch or eager-load). Keep total pool size across all API and worker replicas under the database's connection limit.
- **Observability.** Bind `request_id`, `tenant_id`, `bot_id`, `conversation_id` and `config_version` to logs and traces, and pass `request_id` into background jobs so one chat can be followed end to end. Report latency as p50 / p95 / p99, never only the average. For the chat path, measure time to first token separately from total reply time.
- **Dependencies.** Don't add a library without saying what it does that existing code can't. Lock files (`uv.lock`, `package-lock.json`) are committed; no unpinned images in production.
- **Deployment and migrations.** A migration must work with the app version that is *already running* (expand → deploy code → contract in a later migration, R25). Deploys are rolling, with readiness checks and draining; rollback means redeploying the previous image, not running a data-destroying downgrade in production.
- **Proxy headers.** Never trust `X-Forwarded-For`, `X-Forwarded-Proto` or `X-Real-IP` unless they come from an explicitly configured trusted proxy (Nginx `real_ip`, uvicorn `--forwarded-allow-ips`).
- **Compliance wording.** Never write that something "is DPDP/GDPR compliant". Label each item as a technical control, a compliance requirement, or something that needs legal review. Design for per-tenant data export, deletion and retention from the start.

## Voice agent (Phase 8 only)

When working on `modules/channels/adapters/voice/` or anything on the live voice path:

- Budget: caller stops speaking → agent starts speaking in about **750 ms**, ceiling **800 ms**. Account for every stage (VAD, endpointing, streaming STT, context/RAG, LLM first token, guard, TTS first audio, transport) and measure each at p50/p95/p99.
- No database writes, analytics, external REST calls or file I/O on that path; do them after the turn or in the worker.
- STT, TTS, VAD, telephony and LiveKit are adapters behind ports (R7), never imported by business code.
- A deploy never cuts an active call: existing calls finish on the old worker; new calls go to the new version.

## How to respond

- Order: **why → what → how → test → deploy.** For larger work cover: current situation, problem, recommended design, where the code goes (§0.5), database, security and performance impact, implementation steps, tests, deployment, risks.
- Be critical. Don't agree with a weak design to be agreeable; say what's wrong and what you recommend.
- **Conflicts (R44):** when a request or the existing code conflicts with a planning doc or a rule, state what the document says, what the request or code does, the risk, and the fix you recommend. Then wait, or follow the documents.
- **Hard-to-undo decisions** (new vendor, new module, hosting, auth, embedding model, new public API) get an ADR in `docs/adr/` first (R43). Docs change in the same commit as the code they describe.
- **Code reviews:** never just "looks good". Report findings by severity (**BLOCKER, HIGH, MEDIUM, LOW, IMPROVEMENT**), each with the problem, why it matters, the impact, the exact change, and the test that proves the fix.
- **Done means production-ready**, not "works locally": tests at the right layer (R34–R37, including 401/403/404/422 for endpoints), typed errors, logs and metrics for the new path, `.env.example` and docs updated, migration and rollback considered, failure behaviour stated.

## Before you finish

```bash
cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy src && uv run lint-imports && uv run pytest
cd ../dashboard && npm run typecheck && npm test && npm run build && npm run audit:ci
cd .. && make code-guide-check
```

Also run, **when the change touches them** (CI enforces all of these):

| You changed... | Also run |
|---|---|
| Tables, repositories, RLS, migrations or anything tenant-isolation related | `make test-db` (real Postgres, throwaway database: see `docs/runbooks/local-setup.md`) |
| A migration | `make schema-sql` and commit `backend/migrations/schema.sql` (CI fails if it's stale) |
| `scripts/vps/*.sh` or `infra/docker-compose.prod.yml` | `shellcheck scripts/vps/*.sh` and `docker compose --env-file .env -f infra/docker-compose.prod.yml config -q` |
| `.github/workflows/*` | `actionlint` |
| Dashboard dependencies | `npm run audit:ci`; tolerate an advisory only through a reviewed, expiring entry in `dashboard/audit-exceptions.json`, approved by the owner |
| Something on the live server's path (auth, bots, config, public widget) | After release: `make smoke-live` |

Run these **before** you start (baseline) and **after** you finish, and report both results. Then walk through the §1.12 checklist in `docs/REPO_STRUCTURE.md`. Don't silence a check (`# noqa`, `# type: ignore`, a skipped test) without a comment explaining why (R42).

If a request conflicts with a rule or a planning document in `docs/planning/`, say so and recommend a fix (R44). Don't silently adapt.