<div align="center">

# 🤖 Saathi AI — Customer Support Chatbot

### *A multilingual RAG support agent for Website + WhatsApp, with a self-serve Bot Studio, human handoff, lead capture and analytics*

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)
![Postgres](https://img.shields.io/badge/pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![WhatsApp](https://img.shields.io/badge/WhatsApp_Cloud_API-25D366?style=for-the-badge&logo=whatsapp&logoColor=white)
![React](https://img.shields.io/badge/React_+_Vite-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

**English · हिन्दी · বাংলা**

</div>

---

## 🎯 The one-line pitch

> **"Your business answers every customer question in seconds, on WhatsApp and your website, in their language, 24/7. It only calls a human when it really needs to."**

---

## 💡 Why this product, why now

| Signal | What it means for you |
|---|---|
| 📈 **AI Chatbot Development +71%** and **AI Integration +178%** on Upwork (In-Demand Skills 2026) | Buyers are actively spending, not just browsing |
| 💬 Most-repeated job post type on Upwork, Fiverr and Freelancer.com: **"RAG support bot on WhatsApp + website, with human handoff"** | Clear, repeatable scope that can be productized |
| ⚠️ Clients now say *"not a toy chatbot"*: they want handoff, CRM sync and analytics | Production quality is the differentiator |
| 🇮🇳 Very few freelancers offer **Hindi / Bengali** bots that actually work | Your unfair advantage |
| 🎛️ Clients want to **change their bot themselves** (tone, greeting, branding) without waiting for you | Bot Studio cuts your support load and makes the product feel like a platform |

---

## 🧩 What the product does: at a glance

```
 ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
 │ 🎛️ CONFIGURE│──▶│  📥 LEARN   │──▶│  💬 ANSWER  │──▶│  ⚡ ACT     │──▶│  📊 IMPROVE │
 │             │   │             │   │             │   │             │   │             │
 │ Bot Studio: │   │ PDFs, site, │   │ Website +   │   │ Capture     │   │ Dashboard,  │
 │ persona,    │   │ FAQs, Drive │   │ WhatsApp,   │   │ leads, book │   │ unanswered  │
 │ style,model,│   │ → vector DB │   │ EN/HI/BN,   │   │ meetings,   │   │ questions,  │
 │ branding    │   │             │   │ with sources│   │ hand off    │   │ CSAT, cost  │
 └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
```

| Module | Highlights |
|---|---|
| 🎛️ **Bot Studio** | Self-serve bot builder: persona, brand rules, banned topics, response-style presets, model + temperature (advanced), logo/header/footer/colours with live preview, draft → publish → rollback, test playground. *(Pro)* own provider API keys |
| 📚 **Knowledge Base (RAG)** | Upload PDF/DOCX, crawl website, Google Drive sync, hybrid search, reranking, source citations |
| 💬 **Channels** | Embeddable website widget (branding from Bot Studio) · WhatsApp Cloud API · *(Pro)* Voice via LiveKit + Sarvam |
| 🌐 **Multilingual** | Auto-detects English, Hindi, Bengali, and Hinglish/Banglish |
| 🙋 **Human Handoff** | Low-confidence, angry-sentiment or "talk to human" triggers → agent inbox takeover |
| 🎯 **Lead Capture** | In-chat forms → HubSpot / Zoho / Google Sheets via n8n |
| 📊 **Analytics** | Resolution rate, handoff rate, top questions, knowledge gaps, LLM cost per tenant |
| 🔐 **Security** | Multi-tenant isolation, PII redaction, prompt-injection guard, tenant prompts sealed below platform safety rules, encrypted tenant secrets, DPDP/GDPR-ready |

---

## 📁 Documentation index

| # | File | What's inside |
|---|---|---|
| 1 | [`01_FEATURES.md`](01_FEATURES.md) | Full feature catalogue (incl. Bot Studio), tier packaging, MoSCoW priorities |
| 2 | [`02_ARCHITECTURE_AND_STACK.md`](02_ARCHITECTURE_AND_STACK.md) | System architecture, tool stack with reasons, bot configuration design, data model, cost model |
| 3 | [`03_PROCESS_FLOWS.md`](03_PROCESS_FLOWS.md) | Message lifecycle, ingestion, handoff, lead capture, WhatsApp rules, Bot Studio publish, widget config, own API keys, client delivery |
| 4 | [`04_BUILD_PLAN.md`](04_BUILD_PLAN.md) | Original 6-week outline, evaluation plan, launch checklist, risks, go-to-market |
| 5 | [`05_PHASEWISE_DEVELOPMENT_PLAN.md`](05_PHASEWISE_DEVELOPMENT_PLAN.md) | **The current plan:** 9 phases, every task estimated, dates, exit criteria |
| 6 | [`06_REPO_STRUCTURE.md`](claude/06_REPO_STRUCTURE.md) | Every folder in the repository explained, with diagrams |
| — | `docs/adr/` (in the repo) | Decision records: 0001 layout · 0002 DB/hosting/auth · 0003 bot config · 0004 tenant API keys · 0005 Bot Studio frontend |

---

## 💰 Packaging for clients (suggested)

| | 🥉 **Starter** | 🥈 **Growth** | 🥇 **Pro** |
|---|---|---|---|
| Channels | Website widget | Website + WhatsApp | Website + WhatsApp + Voice |
| Knowledge sources | Up to 50 docs | Up to 300 docs + site crawl | Unlimited + Drive/Notion sync |
| Languages | English | EN + HI | EN + HI + BN + Hinglish |
| Bot Studio | Persona, presets, branding, publish/rollback | + advanced: model choice, temperature, custom instructions, playground | + own provider API keys (BYOK) |
| Human handoff | Email alert | Agent inbox | Agent inbox + routing rules |
| Lead capture / CRM | Google Sheets | HubSpot / Zoho | Any CRM + custom APIs |
| Analytics | Basic | Full dashboard | Dashboard + monthly report |
| **One-time setup** | **$400 – 700** | **$900 – 1,500** | **$2,000 – 3,500** |
| **Monthly retainer** | $50 – 80 | $120 – 200 | $250 – 400 |

> 💡 *Prices are suggested starting points for Upwork/Fiverr and Indian SMB clients. The **retainer** (hosting + monitoring + KB updates) is where long-term income comes from. LLM API costs are passed through or included with a usage cap. Pro tenants on their own API keys pay the provider directly; usage caps still apply.*

---

<div align="center">

**Built by Sahil · Senior AI Developer · Kolkata 🇮🇳**

</div>
