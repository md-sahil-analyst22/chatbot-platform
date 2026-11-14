# ✨ Saathi AI — Feature Catalogue

> Every feature is tagged with the tier it ships in: 🥉 Starter · 🥈 Growth · 🥇 Pro
> and its build priority: 🔴 **Must** · 🟠 **Should** · 🟢 **Could**

---

## 📑 Contents

1. [📚 Knowledge Base & RAG](#1--knowledge-base--rag)
2. [💬 Channels](#2--channels)
3. [🧠 Conversation Intelligence](#3--conversation-intelligence)
4. [⚡ Actions & Tools](#4--actions--tools)
5. [🙋 Human Handoff](#5--human-handoff)
6. [🎛️ Bot Studio (self-serve bot builder)](#6-️-bot-studio-self-serve-bot-builder)
7. [🛠️ Admin Dashboard](#7-️-admin-dashboard)
8. [📊 Analytics & Reporting](#8--analytics--reporting)
9. [🔌 Integrations](#9--integrations)
10. [🔐 Security & Compliance](#10--security--compliance)
11. [⚙️ Operations & Cost Control](#11-️-operations--cost-control)
12. [🗺️ MoSCoW Summary](#12-️-moscow-summary)

---

## 1. 📚 Knowledge Base & RAG

*The bot's brain. Answer quality depends on this module more than anything else.*

| Feature | Details | Tier | Priority |
|---|---|:---:|:---:|
| **File upload** | PDF, DOCX, TXT, MD, CSV, XLSX. Drag-and-drop in dashboard | 🥉 | 🔴 |
| **Website crawler** | Crawl from sitemap or root URL, depth limit, include/exclude patterns | 🥈 | 🔴 |
| **FAQ editor** | Manual Q&A pairs that **always win** over retrieved chunks (exact-answer override) | 🥉 | 🔴 |
| **Google Drive / Notion sync** | Scheduled re-sync, detects changed files only | 🥇 | 🟠 |
| **Smart chunking** | Heading-aware chunking (~500–800 tokens, 15% overlap) with section titles kept as metadata | 🥉 | 🔴 |
| **Hybrid search** | Vector similarity (pgvector) + keyword search (Postgres full-text), merged with Reciprocal Rank Fusion | 🥈 | 🔴 |
| **Reranking** | Cross-encoder rerank of top 20 → top 5 | 🥈 | 🟠 |
| **Source citations** | Each answer shows "📄 Source: Pricing.pdf, p.3" | 🥉 | 🔴 |
| **"I don't know" guardrail** | If retrieval confidence < threshold → admit uncertainty + offer human. **Never invent an answer** | 🥉 | 🔴 |
| **Multilingual retrieval** | Multilingual embeddings so a Bengali question finds an English document | 🥈 | 🔴 |
| **Versioning** | Roll back to an earlier KB snapshot | 🥇 | 🟢 |

---

## 2. 💬 Channels

| Channel | Details | Tier | Priority |
|---|---|:---:|:---:|
| 🌐 **Website widget** | One `<script>` tag. Logo, header title/subtitle, footer, greeting, colour and launcher position come from **Bot Studio** (published config, cached 60 s). Mobile-responsive | 🥉 | 🔴 |
| 🟢 **WhatsApp** | Meta WhatsApp Cloud API. Text, buttons, list messages, images, PDF in/out, voice notes (transcribed) | 🥈 | 🔴 |
| 🎙️ **Voice agent** | Phone/web voice via LiveKit + Sarvam (STT/TTS) for Hindi/Bengali | 🥇 | 🟠 |
| ✈️ **Telegram** | Bot API adapter (cheap to add once the core exists) | 🥇 | 🟢 |
| 📸 **Instagram DM / FB Messenger** | Via Meta Graph API | 🥇 | 🟢 |

> 🏗️ **Design rule:** every channel is a thin **adapter** that converts to one internal `Message` format. The core agent never knows which channel it's talking to.

---

## 3. 🧠 Conversation Intelligence

| Feature | Details | Tier | Priority |
|---|---|:---:|:---:|
| **Language auto-detect** | EN / HI / BN / Hinglish / Banglish. Reply in the user's language and script | 🥈 | 🔴 |
| **Conversation memory** | Last N turns + rolling summary per user. WhatsApp users are recognised by phone number | 🥉 | 🔴 |
| **Intent classification** | `faq` · `lead` · `booking` · `order_status` · `complaint` · `human` · `chitchat` · `out_of_scope` | 🥉 | 🔴 |
| **Sentiment detection** | Flags frustration so the bot can escalate early | 🥈 | 🟠 |
| **Persona & tone** | Name, tone, brand rules, banned topics, response style, all edited by the tenant in Bot Studio | 🥉 | 🔴 |
| **Per-bot model** | Each bot uses the model and temperature from its published config (chosen from a plan-gated catalog) | 🥈 | 🔴 |
| **Quick replies / buttons** | Suggested next questions after each answer | 🥉 | 🟠 |
| **Follow-up question rewriting** | "What about the price?" is rewritten to a standalone query before retrieval | 🥉 | 🔴 |
| **Out-of-scope handling** | Politely declines unrelated topics (no free general-purpose ChatGPT on the client's bill) | 🥉 | 🔴 |
| **Business hours awareness** | Different handoff message after hours | 🥈 | 🟢 |

---

## 4. ⚡ Actions & Tools

*Turns the bot from "answers questions" into "gets work done". This is what clients pay more for.*

| Tool | What it does | Tier | Priority |
|---|---|:---:|:---:|
| 🎯 **Lead capture** | Collects name, phone, email and need conversationally. Validates the format, deduplicates | 🥉 | 🔴 |
| 📅 **Appointment booking** | Checks slots via Google Calendar / Cal.com, books, sends confirmation | 🥈 | 🟠 |
| 📦 **Order / status lookup** | Calls the client's API (Shopify, custom REST) with the user's order ID | 🥇 | 🟠 |
| 🎫 **Ticket creation** | Creates a ticket in Freshdesk / Zoho Desk / email | 🥈 | 🟠 |
| 📄 **Send document** | Sends a brochure or price list PDF on WhatsApp | 🥈 | 🟢 |
| 🔗 **Custom webhook tool** | Any client API exposed as a tool via config (no code change) | 🥇 | 🟢 |

---

## 5. 🙋 Human Handoff

```
   Bot handling ──(trigger)──▶ Waiting for agent ──(agent joins)──▶ Human handling
        ▲                              │                                  │
        └──────────(timeout: bot apologises + creates ticket)            │
        └───────────────────────────(agent clicks "return to bot")──────┘
```

| Feature | Details | Tier | Priority |
|---|---|:---:|:---:|
| **Triggers** | ① user asks for a human ② low retrieval confidence twice ③ negative sentiment ④ high-value intent (e.g. bulk order) ⑤ keyword rules | 🥉 | 🔴 |
| **Alerts** | Email (🥉) → Slack / WhatsApp to agent (🥈) | 🥉 | 🔴 |
| **Agent inbox** | Live chat view in the dashboard. Agent sees full history + AI summary of the issue | 🥈 | 🔴 |
| **Takeover / return** | Bot pauses during takeover and resumes when the agent hands back | 🥈 | 🔴 |
| **Routing rules** | Route by language, topic or team | 🥇 | 🟢 |
| **Suggested replies** | AI drafts a reply for the agent (copilot mode) | 🥇 | 🟢 |

---

## 6. 🎛️ Bot Studio (self-serve bot builder)

*Lets each tenant create and run its own bots without waiting for you. Built as a React + Vite app (`dashboard/`).*

```
  Create bot ──▶ Configure (draft) ──▶ Preview + Playground ──▶ Publish ──▶ Widget / WhatsApp use it
                       ▲                                           │
                       └──────────── Roll back to any version ◀────┘
```

| Feature | Details | Tier | Priority |
|---|---|:---:|:---:|
| **Create bot** | Name + languages; gets a public widget key (`pk_…`) | 🥉 | 🔴 |
| **Persona & brand rules** | Free-text persona/tone, words to use or avoid, banned topics (max 20) | 🥉 | 🔴 |
| **Response-style presets** | Precise / Balanced / Friendly (maps to temperature 0.1 / 0.3 / 0.6). No jargon for non-technical owners | 🥉 | 🔴 |
| **Branding** | Logo (PNG/JPEG/WebP ≤ 512 KB, no SVG), header title + subtitle, footer text, greeting, primary colour, launcher position | 🥉 | 🔴 |
| **Live widget preview** | Branding changes shown instantly beside the form | 🥉 | 🔴 |
| **Draft → publish → rollback** | Every save is a new immutable version; one click publishes or restores an older version; full version history | 🥉 | 🔴 |
| **Advanced settings** *(admins)* | Model from a plan-gated catalog ("Standard", "Advanced"), manual temperature, max answer length, additional instructions | 🥈 | 🟠 |
| **Playground** | Chat with the **draft** before publishing | 🥈 | 🟠 |
| **Embed code** | Copy-paste `<script>` snippet with the bot's public key | 🥉 | 🔴 |
| **Own API keys (BYOK)** | Tenant connects its own provider account; key encrypted, write-only, shown as `••••abcd`, owner-only | 🥇 | 🟢 *(Phase 8)* |

> 🛡️ **Safety rule:** tenant-written text is always placed **below** the platform's fixed safety and grounding rules, in a sealed section. A tenant can change tone and topics, never "answer only from documents", citations, or medical/legal limits.

---

## 7. 🛠️ Admin Dashboard

*Lives in the same React app as Bot Studio.*

| Screen | Contents | Tier |
|---|---|:---:|
| 🏠 **Home** | Today's conversations, resolution rate, open handoffs, leads | 🥉 |
| 🎛️ **Bot Studio** | Bots, configuration, branding, versions, playground (see §6) | 🥉 |
| 📚 **Knowledge** | Upload, crawl, sync status, chunk preview, "test a question" playground | 🥉 |
| 💬 **Conversations** | Searchable list, filter by channel/language/outcome, full transcript + sources used | 🥉 |
| ❓ **Unanswered questions** | Questions the bot couldn't answer, grouped by similarity → "Add answer" button | 🥈 |
| 🙋 **Agent inbox** | Live handoffs | 🥈 |
| 🔌 **Integrations** | CRM, calendar, webhooks, WhatsApp number connection | 🥈 |
| 🔑 **API keys** | Own provider keys (Pro, Phase 8) | 🥇 |
| 👥 **Team** | Invite agents, roles (Owner / Admin / Agent / Viewer) | 🥈 |

> ⭐ **The "Unanswered questions" screen is your strongest selling feature.** It shows the client exactly where their documentation has gaps, and it supports the case for an ongoing retainer.

**Who can do what**

| Action | Owner | Admin | Agent | Viewer |
|---|:---:|:---:|:---:|:---:|
| View bots, configs, versions | ✅ | ✅ | ✅ | ✅ |
| Save draft, publish, roll back, advanced settings | ✅ | ✅ | — | — |
| Add / rotate / revoke own API keys | ✅ | — | — | — |
| See masked API keys | ✅ | ✅ | — | — |

---

## 8. 📊 Analytics & Reporting

| KPI | Definition | Target |
|---|---|---|
| ✅ **Resolution rate** | Conversations closed without a human | ≥ 70% |
| 🙋 **Handoff rate** | Conversations escalated | ≤ 20% |
| ❓ **Unanswered rate** | Bot said "I don't know" | ≤ 10% |
| 👍 **CSAT** | 👍/👎 at the end of each conversation | ≥ 85% positive |
| ⏱️ **First response time** | Message in → reply out | < 4 s (p95) |
| 🎯 **Leads captured** | Valid leads per week | client-specific |
| 💸 **Cost per conversation** | LLM + embedding spend / conversations | < ₹2 (≈ $0.02) |
| 🔥 **Top topics** | Clustered intents/questions | — |

**Extras:** 📅 automated monthly PDF report emailed to the client (🥇), and an optional Power BI export (your differentiator). KPIs can be compared **per config version**, so a client sees whether a persona change helped.

---

## 9. 🔌 Integrations

| Category | Tools | How |
|---|---|---|
| CRM | HubSpot, Zoho CRM, GoHighLevel, Salesforce | Native API for HubSpot/Zoho; others via **n8n** |
| Spreadsheets | Google Sheets, Airtable | n8n |
| Calendar | Google Calendar, Cal.com | Native tool |
| Helpdesk | Freshdesk, Zoho Desk | n8n |
| Alerts | Slack, email (SMTP/Resend), WhatsApp to agent | Native |
| Anything else | Generic outbound webhooks on events (`lead.created`, `handoff.requested`, `conversation.closed`) | Native |

---

## 10. 🔐 Security & Compliance

| Control | Implementation |
|---|---|
| 🏢 **Multi-tenant isolation** | `tenant_id` on every row + Postgres Row-Level Security. Vector search always filtered by tenant |
| 🕵️ **PII redaction** | Mask Aadhaar, PAN, card numbers and phone numbers in logs and LLM traces |
| 🛡️ **Prompt-injection guard** | System prompt hardening + input classifier + retrieved text marked as untrusted data |
| 🧱 **Tenant prompt sealing** | Platform rules first; tenant persona/instructions inside a sealed section that cannot close itself or override grounding |
| 🎨 **Branding safety** | Widget text validated (no control characters or `<`/`>`) and rendered as text; logos checked by content (no SVG) |
| 🌐 **Public widget endpoint** | Returns only public branding fields, resolved via the bot's public key; rate-limited and cacheable |
| 🚦 **Rate limiting** | Per user / per tenant (Redis) to stop abuse and cost spikes |
| 🔑 **Secrets** | Env vars / secret manager, never in the repo. Tenant secrets (WhatsApp tokens, own API keys) encrypted with AES-256-GCM bound to tenant + provider; write-only; owner-only |
| 📜 **Compliance** | India **DPDP Act 2023** + GDPR basics: consent notice, data-retention setting, delete-my-data endpoint *(technical controls; legal review still required)* |
| 🧾 **Audit log** | Who changed KB/settings/config versions/API keys and when |

---

## 11. ⚙️ Operations & Cost Control

| Feature | Why |
|---|---|
| **Model routing** | Small, cheap model for classification/rewriting; the bot's chosen model only for final answers |
| **Model catalog** | Tenants pick catalog keys, never raw vendor model ids; vendors and versions can change without touching saved configs |
| **Semantic cache** | Repeated questions answered from cache (often 20–40% of FAQ traffic) |
| **Provider fallback** | If the primary LLM API fails → secondary provider automatically |
| **Per-tenant usage caps** | Hard monthly token limit with an alert at 80% (also for tenants on their own keys) |
| **Tracing** | Every turn traced (prompt, chunks, latency, cost, config version) in Langfuse |
| **Health checks & uptime** | `/health` endpoint + UptimeRobot / Better Stack alerts |

---

## 12. 🗺️ MoSCoW Summary

| 🔴 **MUST** (MVP) | 🟠 **SHOULD** (v1.1) | 🟢 **COULD** (later) |
|---|---|---|
| File upload + FAQ editor | Website crawler polish | Telegram / Instagram |
| Chunking + hybrid search | Reranker | KB versioning |
| Citations + "I don't know" | Booking tool | Agent copilot replies |
| Website widget (Studio branding) | Sentiment-based escalation | Routing rules |
| WhatsApp channel | Unanswered-questions clustering | Monthly PDF reports |
| EN/HI/BN detection | Drive/Notion sync | Voice channel |
| Memory + query rewrite | Ticket creation | Custom webhook tools |
| Lead capture → Sheets/HubSpot | Semantic cache | Power BI export |
| Handoff + agent inbox | Provider fallback | **Own API keys (BYOK, Pro)** |
| **Bot Studio core:** persona, presets, branding, draft/publish/rollback | **Bot Studio advanced:** model, temperature, custom instructions, playground | |
| Basic dashboard + analytics | | |
| Tenant isolation + rate limits | | |

---

⬅️ [Back to README](00_README.md) · ➡️ [Architecture & Stack](02_ARCHITECTURE_AND_STACK.md)
