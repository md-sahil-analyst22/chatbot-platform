# 🔄 Saathi AI — Process Flows

| # | Flow | Type |
|---|---|---|
| 1 | [📨 Message lifecycle](#1--message-lifecycle-end-to-end) | Runtime |
| 2 | [📥 Knowledge ingestion](#2--knowledge-ingestion-pipeline) | Runtime |
| 3 | [🙋 Human handoff](#3--human-handoff-state-machine) | Runtime |
| 4 | [🎯 Lead capture](#4--lead-capture-flow) | Runtime |
| 5 | [🟢 WhatsApp rules](#5--whatsapp-specific-flow--rules) | Runtime |
| 6 | [🎛️ Bot Studio: create, configure, publish](#6-️-bot-studio-create-configure-publish) | Self-serve |
| 7 | [🎨 Widget loads its branding](#7--widget-loads-its-branding) | Runtime |
| 8 | [🔑 Tenant connects its own API key (Pro)](#8--tenant-connects-its-own-api-key-pro-phase-8) | Self-serve |
| 9 | [🔁 Continuous improvement loop](#9--continuous-improvement-loop) | Ops |
| 10 | [🤝 Client delivery process](#10--client-delivery-process-freelance) | Business |

---

## 1. 📨 Message lifecycle (end-to-end)

```mermaid
sequenceDiagram
    autonumber
    actor U as 👤 Customer
    participant CH as 📱 WhatsApp / Widget
    participant API as ⚡ FastAPI
    participant R as 🧠 Redis
    participant AG as 🤖 LangGraph Agent
    participant DB as 🗄️ Postgres+pgvector
    participant LLM as ☁️ LLM API
    participant LF as 📈 Langfuse

    U->>CH: "GST filing er fees koto?" (Banglish)
    CH->>API: Webhook / POST /chat
    API->>API: Verify signature, resolve tenant + bot
    API->>R: Rate-limit check + load session memory
    API->>R: Load bot's published config (cache 60 s, miss → DB)
    API->>AG: Run graph(state, config)
    AG->>AG: Guard → detect lang = banglish
    AG->>LLM: Rewrite → "What are the GST filing fees?"
    AG->>LLM: Classify intent → faq
    AG->>R: Semantic cache lookup
    R-->>AG: miss
    AG->>DB: Hybrid search (vector + keyword, tenant filter)
    DB-->>AG: Top 20 chunks
    AG->>AG: Rerank → top 5, confidence = 0.82 ✅
    AG->>AG: Build prompt: platform rules → sealed tenant persona → context
    AG->>LLM: Bot's model + temperature → grounded answer (Banglish) + citations
    LLM-->>AG: Answer (streamed)
    AG->>DB: Save message, citations, usage, config version
    AG-->>LF: Trace (latency, tokens, cost, config version)
    AG-->>API: Response
    API-->>CH: Stream / send message + quick-reply buttons
    CH-->>U: "GST return filing er fees ₹1,500/month theke shuru... 📄 Source: Pricing.pdf"
```

**⏱️ Latency budget (p95 target < 4 s):**

| Step | Budget |
|---|---|
| Webhook + tenant + Redis + cached bot config | 100 ms |
| Rewrite + intent (small model, in parallel) | 600 ms |
| Hybrid retrieval + rerank | 400 ms |
| Answer generation (first token) | 1,200 ms (bot's model; "Advanced" models may be slower) |
| Send to channel | 300 ms |

> The bot config must come from cache on the hot path. Publishing invalidates the cache key, so a change is live within seconds, at most 60 s.

---

## 2. 📥 Knowledge ingestion pipeline

```mermaid
flowchart LR
    A["📤 Upload / URL / Drive"] --> B["🗂️ Store raw file<br/>(S3 / Storage)"]
    B --> C["📬 Enqueue job<br/>(Redis / ARQ)"]
    C --> D{"📄 File type?"}
    D -- PDF/DOCX --> E1["Docling / PyMuPDF<br/>+ OCR fallback"]
    D -- Website --> E2["Crawl4AI<br/>→ clean markdown"]
    D -- CSV/XLSX --> E3["Row-to-text<br/>templating"]
    E1 --> F["🧹 Clean<br/>headers, footers, dupes"]
    E2 --> F
    E3 --> F
    F --> G["✂️ Heading-aware chunking<br/>500–800 tokens, 15% overlap"]
    G --> H["🏷️ Metadata<br/>source, page, section, lang"]
    H --> I["🔢 Embed (batch)"]
    I --> J[("🗄️ pgvector + tsvector")]
    J --> K["✅ Status = ready<br/>🔔 notify dashboard"]
```

**🔁 Re-sync logic:** hash each file → if the hash is unchanged, skip; if changed, delete old chunks for that source and re-ingest. Runs nightly for Drive/Notion/website sources.

---

## 3. 🙋 Human handoff state machine

```mermaid
stateDiagram-v2
    [*] --> BotActive
    BotActive --> HandoffRequested: user asks / low confidence ×2 / angry / VIP intent
    HandoffRequested --> AgentNotified: alert sent (Slack · email · WhatsApp)
    AgentNotified --> HumanActive: agent clicks "Take over"
    AgentNotified --> AfterHours: no agent within 5 min or outside hours
    AfterHours --> TicketCreated: bot collects details + promises callback
    TicketCreated --> [*]
    HumanActive --> BotActive: agent clicks "Return to bot"
    HumanActive --> Closed: agent resolves
    BotActive --> Closed: user satisfied / inactivity 30 min
    Closed --> [*]
```

**Messages the user sees:**

| State | Example message |
|---|---|
| HandoffRequested | "I'm connecting you with our team 🙋. They usually reply within a few minutes." |
| AfterHours | "Our team is offline right now (10am–7pm). I've noted your query and someone will call you tomorrow." |
| HumanActive | *(agent's messages appear with their name)* |

**🧾 What the agent receives:** AI summary (issue, language, sentiment, what the bot already tried) + full transcript + contact details.

---

## 4. 🎯 Lead capture flow

```mermaid
flowchart TD
    A["🎯 Intent = lead<br/>e.g. 'I want a quote'"] --> B{"Contact known?"}
    B -- "WhatsApp: phone known" --> C["Ask name + need"]
    B -- "Web: unknown" --> D["Ask name → phone/email → need<br/>one question at a time"]
    C --> E["✅ Validate<br/>phone/email format, dedupe"]
    D --> E
    E --> F["💾 Save LEAD"]
    F --> G["🔔 Webhook: lead.created"]
    G --> H["⚙️ n8n workflow"]
    H --> H1["📇 HubSpot / Zoho contact"]
    H --> H2["📊 Google Sheet row"]
    H --> H3["💬 Slack: 'New lead 🔥'"]
    F --> I["🤖 Confirm to user<br/>+ continue answering questions"]
```

> 💡 **Conversational, not a form.** Ask one field at a time, allow the user to skip, and keep answering their questions mid-flow. This converts much better than a pop-up form.

---

## 5. 🟢 WhatsApp-specific flow & rules

```mermaid
flowchart LR
    A["📩 Meta webhook POST"] --> B["🔐 Verify X-Hub-Signature-256"]
    B --> C["⚡ Return 200 immediately"]
    C --> D["📬 Queue message"]
    D --> E{"Message type"}
    E -- text --> F["🧠 Agent"]
    E -- voice note --> G["🎙️ Sarvam STT → text"] --> F
    E -- image/PDF --> H["📄 OCR / caption → text"] --> F
    E -- button reply --> F
    F --> I{"Inside 24h<br/>service window?"}
    I -- yes --> J["💬 Free-form reply<br/>text · buttons · lists"]
    I -- no --> K["📝 Approved template<br/>message only"]
```

| ⚠️ Rule | Why it matters |
|---|---|
| Acknowledge webhooks fast (process async) | Meta retries slow webhooks → duplicate replies |
| De-duplicate by `message.id` | Retries happen even when you're fast |
| 24-hour customer service window | Outside it you can only send pre-approved **template** messages |
| Max 3 reply buttons / 10 list rows | Design quick replies within these limits |
| Business verification + display name approval | Start this **on day 1** of a client project, as it can take days |
| Opt-in for proactive messages | Required by Meta policy; also good DPDP practice |

---

## 6. 🎛️ Bot Studio: create, configure, publish

**Who:** the tenant's Owner or Admin, in the React Bot Studio (`dashboard/`).

```mermaid
sequenceDiagram
    autonumber
    actor A as 👩‍💼 Tenant admin
    participant S as 🎛️ Bot Studio
    participant API as ⚡ API /api/v1
    participant SVC as BotConfigService
    participant DB as 🗄️ Postgres (RLS)
    participant R as 🧠 Redis

    A->>S: Create bot (name, languages)
    S->>API: POST /bots
    API->>DB: INSERT bot (tenant from token, public key pk_…)
    A->>S: Edit persona, style preset, branding (live preview)
    S->>S: Validate with Zod (mirrors backend)
    S->>API: POST /bots/{id}/config/versions
    API->>SVC: save_draft (ADMIN, model allowed on plan?)
    SVC->>DB: INSERT version N (draft)
    A->>S: Test in Playground (draft)
    A->>S: Publish
    S->>API: POST /bots/{id}/config/versions/N/publish
    API->>SVC: publish
    SVC->>DB: one transaction: live → archived, N → published
    API->>R: invalidate bot config cache
    API-->>S: published ✅
    Note over A,S: Wrong change? "Restore" an archived version →<br/>copied into a NEW version and published
```

| Rule | Why |
|---|---|
| Every save creates a new immutable version | Full history, nothing lost, auditable |
| Publish is one transaction + a partial unique index | Never zero or two live configs |
| Rollback creates a new version (doesn't rewrite history) | The audit trail stays true |
| Model choice validated against the tenant's plan | A Starter tenant can't enable an expensive model |
| Advanced settings and publish need ADMIN | Agents and viewers can't change live behaviour |
| Tenant text sits below fixed platform rules | Persona changes can't disable grounding or safety |

---

## 7. 🎨 Widget loads its branding

```mermaid
sequenceDiagram
    autonumber
    participant SITE as 🌐 Client website
    participant WJS as widget.js
    participant PUB as ⚡ /public/v1
    participant FN as 🔒 resolve_bot_public_key()
    participant DB as 🗄️ Postgres (RLS)

    SITE->>WJS: <script src=widget.js data-bot-key=pk_…>
    WJS->>PUB: GET /widgets/pk_…/config
    PUB->>FN: public key → (tenant_id, bot_id) only
    PUB->>DB: read published branding inside tenant's RLS scope
    PUB-->>WJS: header, subtitle, footer, greeting, colour, logo URL, languages<br/>Cache-Control: public, max-age=60
    WJS->>SITE: render launcher + chat window (text only, no HTML)
```

- Only public fields leave the server; prompt, model and settings never do.
- Unknown or malformed key → 404. The endpoint is rate-limited per IP and per bot.
- The bot's CORS allowlist (Phase 4) decides which sites may embed it.

---

## 8. 🔑 Tenant connects its own API key (Pro, Phase 8)

```mermaid
sequenceDiagram
    autonumber
    actor O as 👑 Tenant owner
    participant S as 🎛️ Bot Studio
    participant API as ⚡ API
    participant CS as CredentialService
    participant P as ☁️ Provider
    participant DB as 🗄️ Postgres

    O->>S: Paste key (password field)
    S->>API: PUT /credentials/anthropic {api_key}
    API->>CS: save_key (OWNER only)
    CS->>P: one cheap validation call
    P-->>CS: valid ✅
    CS->>CS: AES-256-GCM encrypt, bound to tenant + provider
    CS->>DB: revoke previous active key, store ciphertext + last 4
    API-->>S: {provider, masked: "••••abcd", status: active}
    Note over S: The key is never shown again.
```

**At chat time:** model resolution asks the credential source for a key → tenant key (decrypted in memory) → platform key only if the plan allows fallback → otherwise fail closed with a clear error in the Studio.

---

## 9. 🔁 Continuous improvement loop

```mermaid
flowchart LR
    A["💬 Live conversations"] --> B["📝 Log unanswered +<br/>👎 feedback + handoffs"]
    B --> C["🧩 Cluster similar<br/>questions weekly"]
    C --> D["🛠️ Dashboard:<br/>'Knowledge gaps' screen"]
    D --> E["✍️ Client / you add FAQ, document<br/>or adjust persona in Bot Studio"]
    E --> F["🧪 Re-run golden eval set<br/>(against the draft config)"]
    F --> G{"Scores ≥ baseline?"}
    G -- yes --> H["🚀 Publish"]
    G -- no --> I["🔧 Fix prompt / chunking"] --> F
    H --> A
```

> 💰 This loop **is** your monthly retainer. You show up each month with "we closed 23 knowledge gaps, resolution rate went from 68% → 79%". Because each conversation records its config version, you can show exactly which change moved the numbers.

---

## 10. 🤝 Client delivery process (freelance)

```mermaid
flowchart LR
    P1["1️⃣ Discovery call<br/>30 min"] --> P2["2️⃣ Proposal +<br/>fixed quote"]
    P2 --> P3["3️⃣ Onboarding<br/>docs · access · WA number"]
    P3 --> P4["4️⃣ Build &<br/>configure in Bot Studio"]
    P4 --> P5["5️⃣ UAT with<br/>client's 30 real questions"]
    P5 --> P6["6️⃣ Go-live<br/>+ Studio training"]
    P6 --> P7["7️⃣ Hypercare<br/>14 days"]
    P7 --> P8["8️⃣ Monthly<br/>retainer"]
```

| Phase | Duration | Your deliverables | Client provides |
|---|---|---|---|
| 1️⃣ **Discovery** | Day 0 | Ask: top 20 customer questions, channels, languages, CRM, handoff team, volume | Time + current FAQ/support inbox examples |
| 2️⃣ **Proposal** | Day 1 | Scope, tier, timeline, price, success metrics (resolution %, response time) | Approval + 50% advance |
| 3️⃣ **Onboarding** | Days 2–3 | Checklist + secure upload link; tenant + Studio login created | Docs, website URL, WhatsApp Business account, Meta Business verification, CRM access |
| 4️⃣ **Build** | Days 3–8 | KB ingestion, persona + branding in Bot Studio (with the client), tools, widget/WhatsApp connection | Brand colours, logo, persona preferences |
| 5️⃣ **UAT** | Days 8–10 | Eval report (accuracy %, sample answers), fixes | 30 real test questions + feedback |
| 6️⃣ **Go-live** | Day 10 | Publish config, 30-min Studio + dashboard training video (Loom), handoff SOP | Agent team availability |
| 7️⃣ **Hypercare** | Days 10–24 | Daily log review, quick fixes, gap filling | Feedback |
| 8️⃣ **Retainer** | Monthly | Hosting, monitoring, KB updates, monthly KPI report | Retainer payment |

**📋 Discovery questionnaire (copy into your proposal template):**

- [ ] What are the 20 questions customers ask most often?
- [ ] Which channels do customers use: website, WhatsApp, both?
- [ ] Which languages do customers write in?
- [ ] Who handles escalations, and during what hours?
- [ ] Which CRM / sheet should leads go into?
- [ ] Any actions needed: bookings, order status, ticket creation?
- [ ] Topics the bot must **never** answer (legal advice, pricing exceptions…)?
- [ ] Who on your team will edit the bot in Bot Studio (owner/admin)?
- [ ] Do you have your own AI provider account you want to use (Pro), or should we include usage in the plan?
- [ ] Expected monthly conversation volume?
- [ ] How will we measure success after 30 days?

---

⬅️ [Architecture & Stack](02_ARCHITECTURE_AND_STACK.md) · ➡️ [Build Plan](04_BUILD_PLAN.md)
