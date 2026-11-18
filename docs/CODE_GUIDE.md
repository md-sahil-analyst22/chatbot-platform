# 📘 Saathi Code Guide: every piece of code, explained simply

> **Who this is for:** anyone who wants to understand how Saathi's code works, even if you're
> new to programming. No jargon without an explanation. Lots of pictures.
>
> **Last updated:** Phase 1 complete (2026-11-18). This guide grows with every phase. See
> [How to keep this guide up to date](#-how-to-keep-this-guide-up-to-date).

---

## 🧭 Contents

1. [What Saathi is (in one minute)](#1--what-saathi-is-in-one-minute)
2. [The big picture](#2--the-big-picture)
3. [How the code is organised: the restaurant analogy](#3--how-the-code-is-organised-the-restaurant-analogy)
4. [Folder map](#4--folder-map)
5. [Journeys: what happens, step by step](#5--journeys-what-happens-step-by-step)
6. [Data: where it lives and how it moves](#6--data-where-it-lives-and-how-it-moves)
7. [Code reference: every class and function](#7--code-reference-every-class-and-function)
8. [Bot Studio (dashboard) and the widget](#8--bot-studio-dashboard-and-the-widget)
9. [Database migrations](#9--database-migrations)
10. [Tests: how we prove it works](#10--tests-how-we-prove-it-works)
11. [Servers, deploys and scripts](#11--servers-deploys-and-scripts)
12. [Built vs. planned, by phase](#12--built-vs-planned-by-phase)
13. [Glossary](#13--glossary)
14. [How to keep this guide up to date](#-how-to-keep-this-guide-up-to-date)

### Symbols used

| Symbol | Meaning |
|---|---|
| 🟢 | Built and working |
| 🟡 | Skeleton: the file exists, the real work arrives in a later phase |
| 🔒 | Security-relevant: read carefully before changing |
| ➡️ | "calls" or "sends data to" |

---

## 1. 💡 What Saathi is (in one minute)

Saathi is a **chatbot platform for businesses** (we call each business a **tenant**).

- A business owner logs in to **Bot Studio** (the dashboard) and creates a **bot**.
- They give it a **personality**, **branding** (colours, title, greeting) and later **documents** to learn from.
- The bot appears as a **chat widget** on their website (and later on WhatsApp and voice).
- Visitors ask questions in **English, Hindi or Bengali**; the bot answers from the business's documents.

One Saathi installation serves **many businesses at once**, and each business must **never** see
another's data. That rule shapes almost everything in the code.

---

## 2. 🗺️ The big picture

```mermaid
flowchart LR
    subgraph People
        OWNER["👩‍💼 Business owner"]
        VISITOR["🙋 Website visitor"]
    end

    subgraph Frontend["Browser"]
        STUDIO["🎛️ Bot Studio<br/>(React dashboard)"]
        WIDGET["💬 Chat widget<br/>(on the business's site)"]
    end

    subgraph Server["Saathi server (Docker)"]
        API["⚙️ API<br/>(FastAPI)"]
        WORKER["🏭 Worker<br/>(background jobs)"]
        REDIS[("⚡ Redis<br/>fast memory / queue")]
    end

    subgraph Cloud["Outside services"]
        SUPA[("🐘 Supabase<br/>Postgres + Login + Files")]
        AI["🤖 AI providers<br/>Gemini · Sarvam · Cohere"]
    end

    OWNER --> STUDIO --> API
    VISITOR --> WIDGET --> API
    API --> SUPA
    API --> REDIS
    WORKER --> REDIS
    WORKER --> SUPA
    API -. "Phase 2-3" .-> AI
    WORKER -. "Phase 2" .-> AI
```

| Part | Plain explanation |
|---|---|
| **Bot Studio** | The website where business owners set up their bots |
| **Widget** | The little chat bubble on the business's website |
| **API** | The "brain" that answers every request from Studio and the widget |
| **Worker** | A helper that does slow jobs in the background (e.g. reading PDFs), so nobody waits |
| **Redis** | Very fast temporary memory: job queue, recent chat turns, rate limits |
| **Supabase** | Holds the real data (database), handles logins, stores files |
| **AI providers** | Gemini writes answers and makes "embeddings", Sarvam does speech, Cohere ranks search results |

---

## 3. 🍽️ How the code is organised: the restaurant analogy

Think of the backend as a restaurant:

| Restaurant | Code folder | What lives there |
|---|---|---|
| 📜 **The recipes** (rules that never change) | `domain/` | Business rules: what a valid bot or config looks like. Plain Python only |
| 🧾 **The shopping list** ("we need flour", not "buy from shop X") | `ports/` | Small "contracts" describing what the code needs from the outside world |
| 👨‍🍳 **The chef** (does one dish = one task) | `application/` | Use cases: "create a bot", "publish a config" |
| 🚚 **The suppliers** (real shops) | `adapters/` | Real implementations: database code, Gemini, Supabase |
| 🧑‍💼 **The waiter** (takes orders) | `api/` | HTTP endpoints: receives requests, returns responses |
| 🏢 **The building** (water, power) | `platform/` | Shared plumbing: settings, database connection, security, logging |
| 🧑‍🏭 **The manager** (decides which supplier) | `bootstrap/` | Wires everything together at startup |

**The golden rule:** arrows only point **inward**. The recipes never know about the waiter or the
suppliers. That keeps business rules safe and testable.

```mermaid
flowchart TB
    API["🧑‍💼 api/<br/>routes · schemas · deps"] --> ADP["🚚 adapters/<br/>SQL · Gemini · Supabase"]
    ADP --> APP["👨‍🍳 application/<br/>services (use cases)"]
    APP --> PORT["🧾 ports/<br/>contracts (Protocols)"]
    PORT --> DOM["📜 domain/<br/>business rules"]
    BOOT["🧑‍🏭 bootstrap/"] -. "wires" .-> ADP
    PLAT["🏢 platform/"] -. "used by everyone" .-> APP
```

These rules are enforced automatically by a tool called **import-linter** (it fails CI if
someone breaks them). The full rulebook is in [`REPO_STRUCTURE.md`](REPO_STRUCTURE.md).

### Modules: the restaurant's departments

The backend is split into **modules**. Each has its own folders (domain, ports, …) and modules
**never import each other** (rule R4).

| Module | Job | Status |
|---|---|---|
| `tenancy` | Businesses, bots, bot configuration, logins → workspace | 🟢 Phase 1 |
| `credentials` | Businesses' own AI keys, stored encrypted | 🟡 logic ready, endpoints Phase 8 |
| `knowledge` | Documents, chunks, search (embeddings + reranking) | 🟡 adapters ready, flow Phase 2 |
| `conversation` | Chat: prompts, AI answers, memory | 🟡 adapters ready, flow Phase 3 |
| `channels` | Web widget, WhatsApp, voice, speech | 🟡 adapters ready, flow Phase 4 |
| `handoff` | Pass a chat to a human agent | 🟡 table only, Phase 5 |
| `leads` | Capture customer details | 🟡 table only, Phase 5 |
| `analytics` | Usage and cost tracking | 🟡 table only, Phase 5–6 |

---

## 4. 📁 Folder map

```
chatbot-platform/
├── backend/                     ⚙️ the API + worker (Python)
│   ├── src/saathi/
│   │   ├── main.py              🚪 starts the web app
│   │   ├── worker.py            🏭 starts the background worker
│   │   ├── api/                 🧑‍💼 shared HTTP pieces (health, errors, middleware, deps, router)
│   │   ├── bootstrap/           🧑‍🏭 wiring (container, providers, credentials)
│   │   ├── platform/            🏢 shared plumbing (config, db, security, logging, storage…)
│   │   └── modules/             🏬 the departments (tenancy, knowledge, conversation…)
│   ├── migrations/              🗄️ database changes (Alembic) + schema.sql
│   └── tests/                   🧪 unit, contract, integration, security, architecture
├── dashboard/                   🎛️ Bot Studio (React + TypeScript)
├── widget/                      💬 the chat bubble (placeholder until Phase 4)
├── infra/                       🐳 Docker Compose files (dev + production)
├── scripts/                     🛠️ helper scripts (key checks, VPS setup, live test)
├── docs/                        📚 plans, decisions (ADRs), runbooks, this guide
└── .github/                     🤖 CI pipeline, Dependabot, PR template
```

---

## 5. 🚶 Journeys: what happens, step by step

### 5.1 🚀 The app starts

```mermaid
sequenceDiagram
    autonumber
    participant U as uvicorn (web server)
    participant M as main.create_app
    participant L as logging.setup
    participant C as Container.build
    participant S as app.state

    U->>M: create_app()
    M->>M: get_settings() reads .env
    M->>L: configure_logging()
    M->>M: add middleware, error handlers, routes
    Note over M: app starts → "lifespan" runs
    M->>C: Container.build(settings)
    C->>C: database engine, Redis, HTTP client,<br/>model catalog, token verifier
    C-->>S: publish each resource on app.state
    Note over S: requests can now be served
    Note over C: on shutdown: Container.aclose()<br/>closes everything cleanly
```

**In plain words:** when the server starts, it reads settings, sets up logging, and builds one
**container** holding the shared tools (database connection, Redis, HTTP client…). Every request
borrows these tools; nobody creates their own.

### 5.2 📨 Every request (the common path)

```mermaid
flowchart LR
    REQ["📨 Request"] --> MW["RequestContextMiddleware<br/>gives it a request_id<br/>+ logs it"]
    MW --> R["Router<br/>finds the endpoint"]
    R --> D["Dependencies (deps.py)<br/>who is calling? which DB session?"]
    D --> H["Route function<br/>(thin)"]
    H --> SVC["Service<br/>(the real work)"]
    SVC --> RES["✅ Response"]
    SVC -. "error" .-> ERR["errors.py<br/>turns it into a clean JSON error"]
```

Every response carries an `x-request-id` header, so one request can be followed through the logs.

### 5.3 🔐 Logging in: how the API knows who you are

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser / script
    participant API as get_principal (deps.py)
    participant V as JwksTokenVerifier
    participant J as Supabase JWKS (public keys)
    participant DB as resolve_user_membership()

    B->>API: request + "Authorization: Bearer <token>"
    API->>V: verify(token)
    V->>V: check algorithm is ES256/RS256 🔒
    V->>J: get public keys (cached 10 min)
    V->>V: check signature, issuer, audience, expiry
    V->>DB: which workspace + role for this user?
    DB-->>V: exactly one (tenant_id, role)
    V-->>API: Principal(user, tenant, role)
    API-->>B: request continues as that tenant
```

| Situation | Result |
|---|---|
| No token | **401** "missing bearer token" |
| Bad / expired / forged token | **401** "invalid or expired token" |
| Valid login but no workspace | **403** |
| Valid login, in two workspaces | **403** (we never guess) |
| No verifier configured (local dev without `AUTH_*`) | **401** for every `/api/v1` call (fail closed 🔒) |

### 5.4 🤖 Creating a bot

```mermaid
sequenceDiagram
    autonumber
    participant S as Bot Studio
    participant R as routes.create_bot
    participant BS as BotService.create_bot
    participant B as Bot (domain)
    participant REPO as SqlAlchemyBotRepository
    participant PG as Postgres (RLS)

    S->>R: POST /api/v1/bots {name, languages}
    R->>R: BotCreate schema validates input<br/>(unknown fields like tenant_id → 422)
    R->>BS: create_bot(principal, command)
    BS->>BS: require_role(ADMIN)
    BS->>B: Bot(...) checks name, languages, key 🔒
    Note over BS: tenant_id comes from the TOKEN,<br/>never from the request
    BS->>REPO: add(bot)
    REPO->>PG: INSERT (RLS checks tenant matches)
    PG-->>REPO: ok / duplicate name
    REPO-->>R: bot or ConflictError (409)
    R-->>S: 201 + BotOut
```

### 5.5 📝 Save draft → publish → rollback (bot configuration)

A bot's settings are stored as **versions**. You never edit a version; you create a new one.

```mermaid
stateDiagram-v2
    [*] --> draft: Save (POST config/versions)
    draft --> published: Publish
    published --> archived: another version is published
    archived --> draft: Rollback copies it<br/>into a NEW draft…
    draft --> published: …which is then published
```

| Step | What the code does |
|---|---|
| **Save draft** | `BotConfigService.save_draft` checks the role, that the bot exists, that the chosen model is on the tenant's plan, then stores version N+1 as `draft` |
| **Publish** | `BotConfigService.publish` archives the current live version and publishes the target, in **one transaction**. A database rule allows only **one** published version per bot; if two publishes race, one gets **409** |
| **Rollback** | `BotConfigService.rollback` copies an old version into a new draft and publishes it. History is never rewritten |

### 5.6 💬 The widget loads its look (public, no login)

```mermaid
sequenceDiagram
    autonumber
    participant W as Widget on a business site
    participant DEP as get_resolved_widget (deps)
    participant FN as resolve_bot_public_key() 🔒
    participant SVC as PublicWidgetConfigService
    participant PG as Postgres (RLS)

    W->>DEP: GET /public/v1/widgets/pk_abc.../config
    DEP->>DEP: key format check (pk_ + 16-64 chars)
    DEP->>FN: which tenant + bot owns this key?
    FN-->>DEP: (tenant_id, bot_id) — nothing else
    DEP->>SVC: open a session for THAT tenant only
    SVC->>PG: bot + published config
    PG-->>SVC: rows (RLS-scoped)
    SVC-->>W: only the public look:<br/>title, colours, greeting, languages…
```

- Unknown key **and** bot without a published config both return the **same 404**, so outsiders
  can't discover which keys exist.
- The response never contains prompts, model names, plan or internal IDs (rule R10).
- It may be cached by browsers for 60 seconds.

### 5.7 ❤️ Health and readiness

| Endpoint | Question it answers | Checks |
|---|---|---|
| `GET /health` | "Is the app alive?" | Nothing external, always fast |
| `GET /ready` | "Can it serve traffic?" | Database + Redis, 2 s timeout each; returns only `ok`/`fail` |

### 5.8 🏭 Background jobs (worker)

```mermaid
flowchart LR
    API["API<br/>(e.g. upload, Phase 2)"] -- "enqueue job" --> Q[("Redis queue")]
    Q --> W["worker.py<br/>(ARQ)"]
    W --> JOB["ingest_source()<br/>🟡 placeholder until Phase 2"]
```

The worker retries a failed job up to 5 times, gives each job at most 600 seconds, and runs up
to 10 jobs at once.

---

## 6. 🗃️ Data: where it lives and how it moves

### 6.1 Where each kind of data lives

| Data | Lives in | Why there |
|---|---|---|
| Businesses, bots, configs, chats, documents' chunks | **Supabase Postgres** | Permanent, protected by row-level security |
| Logins (users, passwords) | **Supabase Auth** | We never store passwords ourselves |
| Uploaded files, logos | **Supabase Storage** (Phase 2/4) | Big files don't belong in the database |
| Job queue, recent chat turns, rate limits | **Redis** | Fast, temporary |
| Secrets (keys, passwords) | **`.env` file** on the server, never in git | 🔒 |
| Businesses' own AI keys (Phase 8) | Postgres, **encrypted** (AES-256-GCM) | 🔒 even a database leak doesn't reveal them |

### 6.2 🔒 How tenants are kept apart (row-level security)

```mermaid
flowchart TB
    REQ["Request from tenant A"] --> TS["tenant_session(tenant A)<br/>sets app.tenant_id = A<br/>for this transaction only"]
    TS --> Q["SELECT * FROM bots"]
    Q --> RLS{"Postgres policy<br/>tenant_id = app.tenant_id ?"}
    RLS -- "row of A" --> SEE["✅ returned"]
    RLS -- "row of B" --> HIDE["🚫 invisible"]
    NOTSET["No tenant set"] --> NONE["🚫 zero rows (fail closed)"]
```

Three walls protect every tenant:
1. **The code** always filters by `tenant_id` (rule R15).
2. **The database** hides other tenants' rows (forced row-level security), even if the code forgets.
3. **Composite foreign keys**: a row can't even *point at* another tenant's bot.

The app connects as the limited user `saathi_app`, which can't switch these walls off. Only
migrations use the owner account.

### 6.3 The tables (16)

```mermaid
erDiagram
    TENANTS ||--o{ USER_ACCOUNTS : "has logins"
    TENANTS ||--o{ BOTS : owns
    TENANTS ||--o{ PROVIDER_CREDENTIALS : "own AI keys (Phase 8)"
    TENANTS ||--o{ AUDIT_LOGS : records
    TENANTS ||--o{ CONTACTS : "end users"
    BOTS ||--o{ BOT_CONFIG_VERSIONS : "configured by"
    BOTS ||--o{ ASSETS : "logos"
    BOTS ||--o{ SOURCES : "learns from"
    SOURCES ||--o{ CHUNKS : "split into"
    BOTS ||--o{ FAQS : has
    BOTS ||--o{ CONVERSATIONS : handles
    CONTACTS ||--o{ CONVERSATIONS : starts
    CONVERSATIONS ||--o{ MESSAGES : contains
    CONVERSATIONS ||--o{ HANDOFFS : "may need a human"
    CONTACTS ||--o{ LEADS : becomes
    MESSAGES ||--o{ USAGE_LOGS : costs
```

| Table | Stores | Module |
|---|---|---|
| `tenants` | One row per business: name, plan, monthly token cap | tenancy |
| `user_accounts` | Which login belongs to which business, with which role | tenancy |
| `bots` | Each bot: name, persona, languages, public key | tenancy |
| `bot_config_versions` | Every saved configuration (draft / published / archived) | tenancy |
| `assets` | Logo files (the row stores the file's address, not the file) | tenancy |
| `audit_logs` | "Who did what" (append-only) | tenancy |
| `provider_credentials` | Businesses' own AI keys, encrypted | credentials |
| `sources` | Uploaded documents / URLs and their processing status | knowledge |
| `chunks` | Small passages of documents + their embedding (for search) | knowledge |
| `faqs` | Question/answer pairs | knowledge |
| `contacts` | End users (website visitor, WhatsApp number) | conversation |
| `conversations` | One chat session | conversation |
| `messages` | Each message in a chat | conversation |
| `handoffs` | Chats passed to a human | handoff |
| `leads` | Captured customer details | leads |
| `usage_logs` | Tokens and cost per AI call | analytics |

---

## 7. 📚 Code reference: every class and function

How to read each table: **Name** → **what it is** → **plain explanation**. Inside a class,
methods are listed after the class name.

### 7.1 🚪 Entry points

#### `main.py`
| Name | Kind | Plain explanation |
|---|---|---|
| `create_app` | function | Builds the whole web app: reads settings, sets up logging, adds middleware (request ids, CORS), error handlers and all routes. Its `lifespan` builds the `Container` at startup and closes it at shutdown |

#### `worker.py`
| Name | Kind | Plain explanation |
|---|---|---|
| `startup` | function | Runs when the worker starts; loads settings into the job context |
| `shutdown` | function | Runs when the worker stops (nothing to clean up yet) |
| `WorkerSettings` | class | Tells ARQ (the job runner) which jobs exist (`ingest_source`), where Redis is, max 5 tries, 600 s per job, 10 jobs at once |

### 7.2 🧑‍💼 Shared API pieces (`api/`)

#### `api/router.py`
| Name | Kind | Plain explanation |
|---|---|---|
| `build_api_router` | function | Collects every route: `/health`, `/ready`, `/api/v1/...` (login required) and `/public/v1/...` (widget) |

#### `api/health.py`
| Name | Kind | Plain explanation |
|---|---|---|
| `health` | function | `GET /health` → `{"status":"ok"}`. Proves the app is alive; touches nothing else |
| `_run` | function | Runs one readiness check with a 2-second limit; logs only the error type, never details 🔒 |
| `ready` | function | `GET /ready` → runs all checks (database, Redis) at once; `200 ready` or `503 not_ready` |
| `ReadinessCheck` | type alias | "A function that checks one dependency" |

#### `api/middleware.py`
| Name | Kind | Plain explanation |
|---|---|---|
| `RequestContextMiddleware` | class | Wraps every request: gives it a `request_id` (or accepts a safe one from the caller), adds it to every log line and the response header, and logs one `http.request` line (method, path, status, duration). Never logs query strings 🔒 |

#### `api/errors.py`
| Name | Kind | Plain explanation |
|---|---|---|
| `_status_for` | function | Maps our error types to HTTP codes (e.g. `NotFoundError` → 404) |
| `_body` | function | Builds the one standard error shape: `{"error": {code, message, request_id}}` |
| `register_error_handlers` | function | Installs handlers so **every** failure (our errors, bad input, unknown route, crashes) returns that clean shape with no stack traces 🔒 |

| Our error | HTTP |
|---|---|
| `ValidationError` | 422 |
| `NotFoundError`, `TenantIsolationError` | 404 |
| `ConflictError` | 409 |
| `AuthenticationError` | 401 |
| `AuthorizationError` | 403 |
| `RateLimitError` | 429 |
| `ProviderTimeoutError` / `ProviderError` | 504 / 502 |
| anything else | 500 "An internal error occurred." |

#### `api/deps.py` (shared "dependencies" that routes ask for)
| Name | Kind | Plain explanation |
|---|---|---|
| `get_sessionmaker` | function | Hands out the database session factory |
| `get_token_verifier` | function | Hands out the login checker (or nothing, if login isn't configured) |
| `get_model_catalog` | function | Hands out the list of AI models tenants may choose |
| `get_http_client` | function | Hands out the shared outbound HTTP client |
| `get_principal` | function | 🔒 Reads the `Authorization` header, verifies the token, returns **who is calling** (user, tenant, role). Missing token or no verifier → 401 |
| `get_tenant_db` | function | 🔒 Gives a database session already locked to the caller's tenant (row-level security) |
| `PrincipalDep`, `TenantDbDep`, `HttpClientDep` | shortcuts | Ready-made "give me this" labels used by routes |

### 7.3 🧑‍🏭 Wiring (`bootstrap/`)

#### `bootstrap/container.py`
| Name | Kind | Plain explanation |
|---|---|---|
| `Container` | class | The "toolbox" built once per process: settings, database engine + sessions, Redis, HTTP client, model catalog, token verifier |
| `Container.build` | method | Creates all the tools from the settings |
| `Container.readiness_checks` | method | Says which checks `/ready` runs (database, Redis) |
| `Container._ping_database` / `_ping_redis` | methods | Each does one tiny round trip to prove the dependency answers |
| `Container.aclose` | method | Closes everything at shutdown |
| `build_token_verifier` | function | 🔒 Builds the Supabase login checker if `AUTH_*` are set. In staging/production, missing settings **stop the app from starting** |

#### `bootstrap/providers.py` (picks which vendor to use)
| Name | Kind | Plain explanation |
|---|---|---|
| `build_llm_resolver` | function | Builds the thing that picks the right AI model + key per bot |
| `build_embedder` | function | Picks the embedding vendor from settings (`gemini` by default) |
| `build_reranker` | function | Picks the reranker (`cohere`) |
| `build_parser` | function | Picks a document parser (`pymupdf`) |
| `build_stt` / `build_tts` | functions | Pick speech-to-text / text-to-speech (`sarvam`) |
| `build_object_store` | function | Picks file storage (`supabase`), private or public bucket |

#### `bootstrap/credentials.py`
| Name | Kind | Plain explanation |
|---|---|---|
| `_reveal` | function | Safely reads a hidden secret value (or nothing) |
| `PlatformCredentialSource` | class | Hands out **Saathi's own** AI keys per provider (Phase 8 adds tenants' own keys) |
| `PlatformCredentialSource.api_key_for` | method | "Give me the key for provider X" |
| `platform_credentials_from_env` | function | Builds the source from the Gemini and Anthropic keys in `.env` |

### 7.4 🏢 Shared plumbing (`platform/`)

#### `platform/config/settings.py`
| Name | Kind | Plain explanation |
|---|---|---|
| `Settings` | class | All core settings from `.env`: environment, log level, CORS, database/Redis addresses, login (`AUTH_*`), and which vendor to use for embeddings, reranking, speech and storage |
| `get_settings` | function | Reads the settings once and reuses them |

#### `platform/config/model_catalog.py`
| Name | Kind | Plain explanation |
|---|---|---|
| `ModelOption` | class | One choosable model: key (e.g. `standard`), label, provider, real model id, token limit, which plans may use it |
| `ModelCatalog` | class | The list of allowed models |
| `ModelCatalog.get` | method | Finds a model by key (unknown → error) |
| `ModelCatalog.options_for_plan` | method | Models a plan may use (e.g. starter can't use `advanced`) |
| `ModelCatalog.is_allowed` | method | "May this plan use this model?" |
| `CatalogSettings` | class | Reads model ids from `.env` (`GEMINI_MODEL_SMALL/LARGE`, `ANTHROPIC_MODEL_*`) |
| `default_catalog` | function | Builds the catalog: Gemini owns `standard`/`advanced`; Claude appears as `claude-standard`/`claude-advanced` only if configured |

#### `platform/db/` (database plumbing)
| Name | File | Plain explanation |
|---|---|---|
| `Base` | `base.py` | Parent of every table class; makes all timestamps timezone-aware |
| `uuid_pk` / `tenant_fk` / `created_at` / `updated_at` | `base.py` | Reusable column recipes: id, tenant link, "created at", "updated at" |
| `build_engine` | `engine.py` | Creates the database connection pool |
| `build_sessionmaker` | `engine.py` | Creates the factory that makes database sessions |
| `ping_database` | `engine.py` | One `SELECT 1` to prove the database answers (used by `/ready`) |
| `set_tenant` | `tenant_context.py` | 🔒 Tells Postgres "this transaction belongs to tenant X" (resets at commit) |
| `tenant_session` | `tenant_context.py` | 🔒 Opens a session + transaction already locked to one tenant |
| `violated_constraint` | `errors.py` | Reads which database rule was broken (e.g. duplicate name), so we can return 409 |

#### `platform/errors/errors.py` (our error family)
| Name | Plain explanation |
|---|---|
| `SaathiError` | Parent of all our errors (has a `code` and a `message`) |
| `DomainError` | Parent of business-rule errors |
| `ValidationError` | "Your input breaks a rule" → 422 |
| `NotFoundError` | "Doesn't exist (for you)" → 404 |
| `ConflictError` | "Clashes with something else" (duplicate, race) → 409 |
| `AuthenticationError` | "We don't know who you are" → 401 |
| `AuthorizationError` | "You're not allowed" → 403 |
| `TenantIsolationError` | "That belongs to another tenant" → 404 (and logged as a security event) 🔒 |
| `RateLimitError` | "Too many requests" → 429 |
| `ProviderError` / `ProviderTimeoutError` | An AI vendor failed / was too slow → 502 / 504 |
| `InfrastructureError` / `ConfigurationError` | Something on our side is broken or misconfigured → 500 |

#### `platform/http/client.py`
| Name | Plain explanation |
|---|---|
| `build_http_client` | Creates the **one** shared HTTP client: timeouts, connection limits, never follows redirects 🔒 |

#### `platform/logging/setup.py`
| Name | Plain explanation |
|---|---|
| `configure_logging` | Makes every log line structured (JSON in production), including uvicorn and library logs; adds `request_id`/`tenant_id`; hides noisy/unsafe logs |

#### `platform/observability/tracing.py`
| Name | Plain explanation |
|---|---|
| `Tracer` | Contract for "record how long each step took": `span(name, …)` wraps one step (Langfuse arrives in Phase 3) |
| `NoopTracer` | A do-nothing tracer used until then (its `span` records nothing) |

#### `platform/providers/registry.py`
| Name | Plain explanation |
|---|---|
| `ProviderRegistry` | A phone book of vendors: adapters `register` themselves by name; the app `create`s one by the name in settings; `available` lists them. Unknown name → clear error |

#### `platform/security/` 🔒
| Name | File | Plain explanation |
|---|---|---|
| `Role` | `auth.py` | viewer < agent < admin < owner |
| `Principal` | `auth.py` | "Who is calling": user id, tenant id, role |
| `TokenVerifier` | `auth.py` | Contract: "turn a token into a Principal, or refuse" |
| `Membership` / `MembershipLookup` | `auth.py` | A (tenant, role) pair / contract for finding a user's memberships |
| `require_role` | `auth.py` | Stops the request with 403 if the role is too low |
| `JwksTokenVerifier` | `jwt_verifier.py` | The real login checker for Supabase tokens (see 5.3) |
| `JwksTokenVerifier.verify` | `jwt_verifier.py` | Checks the token, then finds exactly one workspace |
| `JwksTokenVerifier._verified_claims` | `jwt_verifier.py` | Checks algorithm, signature, issuer, audience, expiry, user id |
| `JwksTokenVerifier._key_for` / `_refresh` | `jwt_verifier.py` | Get the right public key; refresh at most once a minute for unknown keys; keep old keys during outages |
| `JwksTokenVerifier._reject` | `jwt_verifier.py` | Logs why (never the token) and answers 401 with a generic message |
| `AesGcmCipher` | `crypto.py` | Encrypts/decrypts secrets with AES-256-GCM, bound to their owner ("associated data"), with key rotation support |
| `AesGcmCipher.from_env_value` / `encrypt` / `decrypt` / `needs_rotation` | `crypto.py` | Load keys from `.env` / lock / unlock / "was this locked with an old key?" |
| `_b64e` / `_b64d` | `crypto.py` | Small helpers to turn bytes into text and back |
| `redact` | `pii.py` | Masks emails, card numbers, Aadhaar, phone numbers and PAN in text (for logs) |
| `BucketPolicy` / `RedisTokenBucket` | `rate_limit.py` | Rate limiter: "N requests, refilling at R per second"; decides what happens if Redis is down (security limits deny) |
| `RedisTokenBucket.allow` | `rate_limit.py` | "May this subject make one more request?" |
| `ImageInfo` / `sniff_image` / `validate_logo` | `uploads.py` | Checks an upload's **real bytes** (not its name) are PNG/JPEG/WebP and ≤ 512 KB; refuses SVG |

#### `platform/storage/`
| Name | File | Plain explanation |
|---|---|---|
| `ObjectStore` | `object_store.py` | Contract for file storage: `put`, `get`, `delete`, `public_url` |
| `SupabaseStorageSettings` | `supabase_store.py` | Supabase address, secret key, bucket names |
| `SupabaseObjectStore` | `supabase_store.py` | Real storage on Supabase: private bucket for documents, public bucket for logos |
| `SupabaseObjectStore.put` / `get` / `delete` / `public_url` / `_url` | `supabase_store.py` | Upload / download / delete / public address / build the address |
| `_check_key` | `supabase_store.py` | 🔒 File paths must start with `t/{tenant}/` and can't climb out with `..` |
| `_is_not_found` | `supabase_store.py` | Understands Supabase's two ways of saying "not found" |
| `create_supabase_store` | `supabase_store.py` | Registry factory; refuses to start without URL + key 🔒 |

### 7.5 🏬 Module: `tenancy` (businesses, bots, configs) 🟢

#### Domain (the rules)
| Name | File | Plain explanation |
|---|---|---|
| `Tenant` | `domain/entities.py` | A business: id, name, plan, token cap |
| `Bot` | `domain/entities.py` | A bot. Checks itself: name 1–100 chars, at least one supported language (`en`, `hi`, `bn`), valid public key format |
| `Bot.renamed` / `with_languages` / `with_persona` / `with_settings` | `domain/entities.py` | Return a **new, re-checked** bot with one thing changed (bots are never edited in place) |
| `ResponseStyle` | `domain/bot_config.py` | Presets: precise (0.1), balanced (0.3), friendly (0.6) creativity |
| `ConfigStatus` | `domain/bot_config.py` | draft / published / archived |
| `PromptSettings` | `domain/bot_config.py` | Persona, brand rules, custom instructions, banned topics (with length limits, no control characters) |
| `GenerationSettings` | `domain/bot_config.py` | Model key, style, optional temperature, max answer length |
| `GenerationSettings.effective_temperature` / `uses_advanced_settings` | `domain/bot_config.py` | The creativity actually used / "did the admin change advanced settings?" |
| `Branding` | `domain/bot_config.py` | Widget look: title, subtitle, footer, greeting, hex colour, left/right, logo. Refuses `<` `>` 🔒 |
| `BotConfig` | `domain/bot_config.py` | Prompt + generation + branding together |
| `BotConfigVersion` | `domain/bot_config.py` | One saved version with its status |
| `BotConfigVersion.published` / `archived` | `domain/bot_config.py` | Allowed status changes only: draft → published → archived |
| `_plain_text` / `_ui_text` | `domain/bot_config.py` | Text checkers: length, no control characters, (for widget text) no angle brackets |

#### Ports (the contracts)
| Name | Plain explanation |
|---|---|
| `BotRepository` | Store bots: `add`, `update`, `delete`, `get`, `list_for_tenant` (always with `tenant_id`) |
| `TenantRepository` | Read a tenant's plan: `get_plan` |
| `BotConfigRepository` | Store config versions: `next_version`, `add`, `update_status`, `get`, `latest_draft`, `published`, `list_versions` |
| `PublicBotRef` | The only thing a widget key resolves to: (tenant_id, bot_id) |
| `PublicBotLookup` | Contract: `resolve(public_key)` |

#### Application (the use cases)
| Name | File | Plain explanation |
|---|---|---|
| `CreateBotCommand` / `UpdateBotCommand` | `services.py` | The inputs for creating / changing a bot (update: `None` = leave unchanged) |
| `BotService` | `services.py` | Bot use cases |
| `BotService.create_bot` | `services.py` | Admin only; tenant from the token; generates the public key; stores the bot |
| `BotService.list_bots` / `get_bot` | `services.py` | Viewer+; only your tenant's bots; another tenant's bot → 404 |
| `BotService.update_bot` | `services.py` | Admin only; applies changes through the bot's named methods |
| `BotService.delete_bot` | `services.py` | Admin only; deletes the bot and everything under it |
| `BotConfigService` | `config_service.py` | Configuration use cases (see 5.5) |
| `BotConfigService.model_options` | `config_service.py` | Models your plan may use |
| `BotConfigService.save_draft` / `publish` / `rollback` | `config_service.py` | Save a new draft / make one live (one transaction) / restore an old version as new |
| `BotConfigService.get_draft` / `get_published` / `list_versions` | `config_service.py` | Read the latest draft / the live version / the history |
| `BotConfigService._require_bot` / `_plan` | `config_service.py` | Helpers: "bot must exist in your tenant" / "your plan (default starter)" |
| `_utcnow` | `config_service.py` | The current time (replaceable in tests) |
| `PublicWidgetConfig` | `config_service.py` | The widget's public look only |
| `PublicWidgetConfigService.get` | `config_service.py` | Reads the bot + its published config and returns only the public look |

#### Adapters (the real database code)
| Name | File | Plain explanation |
|---|---|---|
| `TenantRow`, `UserAccountRow`, `BotRow`, `BotConfigVersionRow`, `AssetRow`, `AuditLogRow` | `adapters/orm.py` | Table definitions (see 6.3) |
| `SqlAlchemyBotRepository` | `adapters/repository.py` | Real `BotRepository`: SQL with a `tenant_id` filter on every query; duplicate name → 409 |
| `SqlAlchemyBotRepository._to_domain` | `adapters/repository.py` | Turns a database row back into a `Bot` |
| `SqlAlchemyTenantRepository.get_plan` | `adapters/repository.py` | Reads a tenant's plan |
| `_conflict_or_raise` | `repository.py`, `config_repository.py` | Turns "duplicate"/"two published" database errors into a friendly 409 |
| `SqlAlchemyBotConfigRepository` | `adapters/config_repository.py` | Real `BotConfigRepository` (all its methods, tenant-filtered) |
| `SqlAlchemyBotConfigRepository._scope` | `adapters/config_repository.py` | The shared "this tenant + this bot" filter |
| `_to_domain` | `adapters/config_repository.py` | Row → `BotConfigVersion` |
| `config_to_json` / `config_from_json` | `adapters/config_mapper.py` | Turn a `BotConfig` into stored JSON and back (with a schema version for future changes) |
| `SqlAlchemyPublicBotLookup.resolve` | `adapters/public_lookup.py` | 🔒 Calls `resolve_bot_public_key()` for the widget |
| `SqlAlchemyMembershipLookup.memberships` | `adapters/membership_lookup.py` | 🔒 Calls `resolve_user_membership()` at login (max 20 rows) |

#### API (the endpoints)
| Name | File | Endpoint / plain explanation |
|---|---|---|
| `create_bot` | `api/routes.py` | `POST /api/v1/bots` |
| `list_bots` | `api/routes.py` | `GET /api/v1/bots` (max 100) |
| `get_bot` | `api/routes.py` | `GET /api/v1/bots/{id}` |
| `update_bot` | `api/routes.py` | `PATCH /api/v1/bots/{id}` (send only what changes) |
| `delete_bot` | `api/routes.py` | `DELETE /api/v1/bots/{id}` → 204 |
| `_out` | `api/routes.py` | Bot → response shape |
| `list_model_options` | `api/config_routes.py` | `GET /api/v1/model-options` |
| `save_draft` / `list_versions` / `get_draft` / `get_published` | `api/config_routes.py` | `POST/GET .../config/versions`, `GET .../config/draft`, `GET .../config/published` |
| `publish` / `rollback` | `api/config_routes.py` | `POST .../config/versions/{n}/publish`, `.../rollback` |
| `to_domain` / `to_out` | `api/config_routes.py` | Request → `BotConfig`; version → response |
| `widget_config` | `api/public_routes.py` | `GET /public/v1/widgets/{key}/config` (no login, cached 60 s) |
| `get_bot_service` / `get_bot_config_service` | `api/deps.py` | Build the services with real SQL repositories |
| `ResolvedWidget` / `get_resolved_widget` | `api/deps.py` | 🔒 Resolve a widget key to its tenant, then open a session for that tenant only |
| `_Strict` | `api/schemas.py` | Base for all request shapes: **unknown fields are refused** (e.g. a smuggled `tenant_id`) 🔒 |
| `BotCreate` / `BotUpdate` / `BotOut` | `api/schemas.py` | Request / partial-update / response shapes for bots. `BotUpdate._not_empty` refuses an empty update or an explicit `null` |
| `PromptSettingsIn` / `GenerationSettingsIn` / `BrandingIn` / `BotConfigIn` | `api/schemas.py` | Request shapes for configuration (with limits) |
| `BotConfigVersionOut` / `ModelOptionOut` / `PublicWidgetConfigOut` | `api/schemas.py` | Response shapes (the public one has only the public look) |

### 7.6 🏬 Module: `credentials` (businesses' own AI keys) 🟡

| Name | File | Plain explanation |
|---|---|---|
| `CredentialStatus` | `domain/credential.py` | active / revoked |
| `ProviderCredential` | `domain/credential.py` | A stored key's **metadata** (never the key itself): provider, last 4 characters, status |
| `ProviderCredential.masked` / `revoked` | `domain/credential.py` | Show as `••••abcd` / mark as revoked |
| `associated_data` | `domain/credential.py` | 🔒 The "owner tag" that binds an encrypted key to one tenant + provider |
| `SecretCipher` / `KeyValidator` / `CredentialRepository` | `ports/vault.py` | Contracts: lock/unlock secrets, test a key with the provider (`is_valid`), store credentials |
| `CredentialService` | `application/services.py` | Use cases (owner only for changes) |
| `CredentialService.save_key` / `list_keys` / `revoke` / `resolve_api_key` | `application/services.py` | Validate + encrypt + store / list / revoke / decrypt for use at request time |
| `ProviderCredentialRow` | `adapters/orm.py` | The `provider_credentials` table |

### 7.7 🏬 Module: `knowledge` (documents and search) 🟡

| Name | File | Plain explanation |
|---|---|---|
| `SourceStatus` | `domain/entities.py` | queued → processing → ready / failed |
| `Source` | `domain/entities.py` | A document or URL. Its status can change **only** through these methods |
| `Source.start_processing` / `mark_ready` / `mark_failed` / `requeue` / `is_unchanged` / `_transition` | `domain/entities.py` | Allowed status moves; "same file as before?" (skip re-processing) |
| `ParsedPage` / `ParsedDocument` / `RerankResult` | `ports/providers.py` | Data shapes: one page of text / a whole document / a ranked result |
| `DocumentParser` / `Embedder` / `Reranker` | `ports/providers.py` | Contracts: read a file / turn text into numbers / sort results by relevance |
| `GeminiEmbedderSettings` / `GeminiEmbedder` | `adapters/embeddings/gemini_embedder.py` | Default embedder: `gemini-embedding-2` at 1,536 numbers, 100 texts per request |
| `GeminiEmbedder.embed` / `_embed_batch` | same | Embed a list of texts / one batch |
| `_l2_normalise` | same | Scales each vector to length 1 (needed for fair comparison) |
| `create_gemini_embedder` | same | Registry factory; refuses an empty key 🔒 |
| `OpenAIEmbedderSettings` / `OpenAIEmbedder` / `embed` / `create_openai_embedder` | `adapters/embeddings/openai_embedder.py` | Backup embedder (OpenAI) |
| `CohereSettings` / `CohereReranker` / `rerank` / `create_cohere_reranker` | `adapters/rerankers/cohere_reranker.py` | Re-sorts search results so the best passages come first |
| `PyMuPdfParser` / `parse` / `create_pymupdf_parser` | `adapters/parsers/pymupdf_parser.py` | Reads text from PDFs; flags scanned PDFs that need OCR |
| `SourceRow` / `ChunkRow` / `FaqRow` | `adapters/orm.py` | Tables; `chunks` has a vector index (meaning search) and a text index (keyword search) |
| `content_hash` | `application/ingestion.py` | A file fingerprint (SHA-256) so unchanged files aren't re-processed |
| `ingest_source` | `workers/ingest_job.py` | 🟡 The background job that will read, chunk and embed a document (Phase 2) |

### 7.8 🏬 Module: `conversation` (the chat brain) 🟡

| Name | File | Plain explanation |
|---|---|---|
| `Intent` | `domain/state.py` | What the user wants: faq, lead, booking, complaint, human… |
| `Citation` | `domain/state.py` | A source the answer came from |
| `ChatState` | `domain/state.py` | Everything known during one reply (message, language, intent, answer…) |
| `ChatMessage` / `LLMResponse` | `ports/llm.py` | One chat message / an AI answer with token counts |
| `CompletionClient` / `StreamingClient` | `ports/llm.py` | Contracts: "get a full answer" / "stream the answer word by word" |
| `CredentialSource` | `ports/credentials.py` | Contract: "which API key does this tenant use for provider X?" |
| `GeminiSettings` / `GeminiCompletionClient` / `complete` / `create_gemini_completion_client` | `adapters/llm/gemini_llm.py` | Primary AI model (Gemini) |
| `AnthropicSettings` / `AnthropicCompletionClient` / `complete` / `create_anthropic_completion_client` | `adapters/llm/anthropic_llm.py` | Optional Claude models |
| `RedisConversationMemory` | `adapters/memory/redis_memory.py` | Remembers the last 6 back-and-forths per chat for 24 h |
| `RedisConversationMemory.append` / `history` / `_key` | same | Add a message / read recent messages / the tenant-scoped Redis key |
| `ContactRow` / `ConversationRow` / `MessageRow` | `adapters/orm.py` | Tables for end users, chats and messages |
| `ModelSelection` / `select_model` | `application/llm_resolver.py` | Turns a bot's model choice into provider + model id + limits |
| `CompletionClientFactory` / `LlmResolver` / `resolve` | `application/llm_resolver.py` | 🔒 Builds the AI client with the right key; no key → refuse (never borrow another's) |
| `TenantPromptParts` | `application/prompt_builder.py` | The business's own prompt pieces |
| `load_platform_rules` | `application/prompt_builder.py` | Loads Saathi's fixed safety rules (`prompts/platform_rules_v1.md`) |
| `_neutralise` | `application/prompt_builder.py` | 🔒 Replaces `<` `>` so business or document text can't escape its section (prompt injection) |
| `build_system_prompt` | `application/prompt_builder.py` | Builds the AI's instructions in fixed layers: **platform rules first**, then business text, then language, then document context |
| `guard_node` | `application/nodes/guard.py` | First check on every message: not empty, not longer than 2,000 characters |
| `build_graph` | `application/graph.py` | 🟡 Wires the chat steps together (only the guard today; more in Phase 3) |

```mermaid
flowchart LR
    MSG["User message"] --> G["guard_node<br/>empty? too long?"]
    G -. "Phase 3" .-> LANG["detect language"] -.-> RAG["search documents"] -.-> ANS["build_system_prompt<br/>+ Gemini answer"]
```

### 7.9 🏬 Module: `channels` (web, WhatsApp, voice, speech) 🟡

| Name | File | Plain explanation |
|---|---|---|
| `Channel` | `domain/message.py` | web / whatsapp / voice |
| `InboundMessage` / `OutboundMessage` | `domain/message.py` | A message coming in (with its channel and message id) / going out (max 3 buttons) |
| `ChannelSender` | `ports/channel.py` | Contract: send a message on a channel |
| `Transcript` / `SynthesizedSpeech` | `ports/speech.py` | Speech-to-text result / generated audio |
| `SpeechToText` / `TextToSpeech` | `ports/speech.py` | Contracts for speech |
| `SarvamSettings` / `SarvamSpeechToText` / `SarvamTextToSpeech` | `adapters/speech/sarvam_speech.py` | Sarvam speech: `saaras:v4` (listen), `bulbul:v4-flash` (speak; Malayalam/Odia use `bulbul:v3`) |
| `transcribe` / `synthesize` | same | Audio → text / text → audio |
| `_settings_with_key` / `create_sarvam_stt` / `create_sarvam_tts` | same | Load settings; refuse an empty key 🔒; registry factories |
| `WhatsAppSettings` / `WhatsAppSender` / `send` | `adapters/whatsapp/client.py` | Sends WhatsApp messages through Meta's API (Phase 4) |
| `is_valid_signature` | `adapters/whatsapp/signature.py` | 🔒 Proves a WhatsApp webhook really came from Meta (fails closed) |
| `sse_event` | `adapters/web/sse.py` | Formats one streaming message for the widget |

### 7.10 🏬 Modules: `handoff`, `leads`, `analytics` 🟡

| Name | File | Plain explanation |
|---|---|---|
| `HandoffRow` | `handoff/adapters/orm.py` | A chat passed to a human: requested → notified → human → closed / after_hours |
| `LeadRow` | `leads/adapters/orm.py` | Captured customer details + CRM sync status |
| `UsageLogRow` | `analytics/adapters/orm.py` | Tokens and cost per AI call, and whose key paid |

---

## 8. 🎛️ Bot Studio (dashboard) and the widget

```mermaid
flowchart TB
    MAIN["main.tsx<br/>starts React"] --> APP["App.tsx<br/>routes + data cache"]
    APP --> LAYOUT["Layout<br/>sidebar + page"]
    LAYOUT --> BOTS["BotsPage<br/>/"]
    LAYOUT --> CFG["ConfigEditorPage<br/>/bots/:id/config"]
    LAYOUT --> PLAY["PlaygroundPage 🟡<br/>/bots/:id/playground"]
    LAYOUT --> KEYS["CredentialsPage 🟡<br/>/settings/api-keys"]
    CFG --> BRAND["BrandingEditor"]
    CFG --> PREV["WidgetPreview"]
    CFG --> HIST["VersionHistory"]
    BOTS & CFG & HIST --> HOOKS["api.ts hooks"] --> CLIENT["lib/api/client.ts<br/>adds the token, reads errors"] --> API["⚙️ API"]
```

| File | Name | Plain explanation |
|---|---|---|
| `main.tsx` | — | Starts React inside the page's `#root` element |
| `app/App.tsx` | `App` | Sets up the data cache (React Query) and the pages (routes) |
| `components/Layout.tsx` | `Layout` | Sidebar (Bots, API keys) + the current page |
| `components/Field.tsx` | `Field` | One form field with label, hint and error text |
| `features/bots/BotsPage.tsx` | `BotsPage` | Lists your bots and has the "Create a bot" form |
| `features/bots/api.ts` | `useBots` / `useCreateBot` | Load bots / create a bot (then refresh the list) |
| `features/bot-config/ConfigEditorPage.tsx` | `ConfigEditorPage` | The settings editor: personality, model, style, branding, save, publish |
| `features/bot-config/api.ts` | `useDraft` / `useVersions` / `useModelOptions` / `useSaveDraft` / `usePublish` / `useRollback` | Talk to the configuration endpoints |
| `features/bot-config/schema.ts` | `botConfigSchema` / `DEFAULT_CONFIG` | Checks the form in the browser with the same limits as the backend (the backend still decides) |
| `features/bot-config/presets.ts` | `STYLE_PRESETS` | Plain-language descriptions of precise / balanced / friendly |
| `features/bot-config/VersionHistory.tsx` | `VersionHistory` | Lists versions; "Restore" an archived one |
| `features/branding/BrandingEditor.tsx` | `BrandingEditor` | Title, subtitle, greeting, footer, colour, position (logo upload in Phase 4) |
| `features/branding/WidgetPreview.tsx` | `WidgetPreview` | Live preview of the chat bubble; shows business text as **plain text only** 🔒 |
| `features/playground/PlaygroundPage.tsx` | `PlaygroundPage` | 🟡 Test chat before publishing (Phase 3) |
| `features/credentials/CredentialsPage.tsx` | `CredentialsPage` | 🟡 Businesses' own AI keys (Phase 8) |
| `lib/api/client.ts` | `api` / `ApiError` | The **only** way the dashboard calls the API: adds the login token, turns errors into `ApiError` |
| `lib/api/types.ts` | types | TypeScript shapes matching the backend responses |
| `lib/auth/token.ts` | `setAccessToken` / `getAccessToken` | Keeps the login token **in memory only** (never in localStorage) 🔒 |
| `widget/src/index.ts` | `mount` | 🟡 Placeholder chat button; the real widget arrives in Phase 4 |

---

## 9. 🗄️ Database migrations

A **migration** is a numbered, reversible script that changes the database. Never change tables by hand.

| Migration | What it does |
|---|---|
| `0001` baseline | Turns on **pgvector** (needed for meaning-based search) |
| `0002` phase 1 schema | Creates all 16 tables, row-level security on each, the widget key lookup function, and safe permissions |
| `0003` membership lookup | Adds `resolve_user_membership()` for logins + its index |

`backend/migrations/schema.sql` is the same SQL in one file (regenerate with `make schema-sql`).

---

## 10. 🧪 Tests: how we prove it works

```mermaid
flowchart LR
    U["🧩 unit<br/>rules & services<br/>(fast, no database)"] --> C["🤝 contract<br/>every adapter and its fake<br/>behave the same"]
    C --> I["🔗 integration<br/>real HTTP requests<br/>(401/403/404/409/422)"]
    I --> S["🔒 security<br/>tenant isolation on<br/>REAL Postgres"]
    A["🏛️ architecture<br/>import rules"] -.-> U
```

| Folder | Proves | Example |
|---|---|---|
| `tests/unit/` | Business rules and services | A bot with no language is refused; forged tokens are rejected |
| `tests/contracts/` | Each real adapter behaves like its contract (and so does its fake) | Gemini, Sarvam, Supabase, SQL repositories |
| `tests/integration/` | Endpoints return the right codes and shapes | Viewer can't delete a bot (403) |
| `tests/security/` | Tenant A can never see tenant B, on a real database | Plus the widget lookup end to end |
| `tests/architecture/` | Folder rules aren't broken | `domain/` imports no frameworks |
| `tests/fakes/` | Pretend versions of databases and vendors used by fast tests | `InMemoryBotRepository` |

Run them: `make test` (fast) and `make test-db` (real Postgres).

---

## 11. 🐳 Servers, deploys and scripts

| File | Plain explanation |
|---|---|
| `infra/docker-compose.yml` | Local development: API (hot reload), worker, Redis |
| `infra/docker-compose.prod.yml` | Production on the VPS: migrate first, then API, worker, Redis, Bot Studio; routed by the server's Traefik with HTTPS |
| `backend/Dockerfile` | Recipe for the backend image (non-root user) |
| `dashboard/Dockerfile` + `nginx.conf.template` | Builds Bot Studio and serves it with strict security headers |
| `scripts/check_keys.py` | `make check-keys`: tests every API key with one cheap call |
| `scripts/smoke_live.py` | `make smoke-live`: real login on the live server, create + publish a test bot, then delete it |
| `scripts/vps/setup.sh` | One-time server hardening (firewall, SSH keys only, Docker), checks Traefik |
| `dashboard/scripts/audit-check.mjs` | Strict security audit of dashboard packages, with reviewed, expiring exceptions |
| `.github/workflows/ci.yml` | Runs every check on each pull request |

```mermaid
flowchart LR
    DEV["💻 Your Mac"] -- "git push" --> GH["GitHub"]
    GH -- "CI: lint, types,<br/>tests, audit, build" --> OK{"all green?"}
    OK -- "merge" --> MAIN["main"]
    MAIN -- "you run on the server:<br/>down → git pull → up --build" --> VPS["🖥️ VPS"]
    VPS --> LIVE["🌐 app.saathi… / api.saathi…"]
```

Daily commands: [`runbooks/deploy-and-daily-operations.md`](runbooks/deploy-and-daily-operations.md).

---

## 12. 🛣️ Built vs. planned, by phase

| Phase | Theme | Status |
|---|---|---|
| **0** | Accounts, keys, decisions | 🟢 Done |
| **1** | Foundation: database, security, login, bot API, CI, live deploy | 🟢 **Done** (2026-11-18) |
| **2** | Knowledge base: upload documents, chunk, embed, search | ⏳ Next |
| **3** | Chat brain: prompts, answers, streaming, playground | ⏳ |
| **4** | Channels: real widget, WhatsApp, logo upload | ⏳ |
| **5** | Studio login & screens, handoff, leads, analytics | ⏳ |
| **6** | Hardening: rate limits, privacy features, monitoring | ⏳ |
| **8** | Pro: businesses' own AI keys, voice | ⏳ |

---

## 13. 📖 Glossary

| Word | Meaning |
|---|---|
| **Tenant** | One business using Saathi |
| **Principal** | "Who is calling": user + tenant + role |
| **RLS (row-level security)** | Database rule that hides other tenants' rows |
| **Port** | A contract ("we need something that can do X") |
| **Adapter** | Real code that fulfils a port (e.g. Gemini, SQL) |
| **Registry** | A phone book of adapters, picked by name from settings |
| **Repository** | Code that saves and loads business objects |
| **Service** | Code for one user action ("create a bot") |
| **Domain object** | A business thing that checks its own rules (e.g. `Bot`) |
| **Migration** | Numbered, reversible database change |
| **Embedding** | A list of numbers capturing a text's meaning, used for search |
| **JWT / token** | The signed "ticket" a user gets after logging in |
| **JWKS** | Supabase's public keys used to check those tickets |
| **SECURITY DEFINER function** | A narrow database function allowed to look past RLS for one specific, safe question |
| **CI** | Automatic checks on every pull request |
| **Traefik** | The server's front door: HTTPS and routing to the right app |
| **Fail closed** | When unsure, refuse |

---

## 🔄 How to keep this guide up to date

At the end of **every phase** (or any PR that adds code):

1. Add new classes and functions to the right table in [section 7](#7--code-reference-every-class-and-function) (or [8](#8--bot-studio-dashboard-and-the-widget) for the dashboard).
2. Update the journeys (section 5) and diagrams if a flow changed.
3. Change 🟡 to 🟢 for anything that's now built, and update [section 12](#12--built-vs-planned-by-phase).
4. Update the **Last updated** line at the top and add a line to the log below.
5. Run the coverage check, which lists any backend class or function the guide doesn't mention yet:

```bash
make code-guide-check
```

### Update log

| Date | Phase | Change |
|---|---|---|
| 2026-11-18 | 1 complete | First version: all 142 classes and 271 functions/methods of the backend, the dashboard, flows, data, tests and deploys |
