# Saathi AI

Multilingual (EN / HI / BN / Hinglish / Banglish) support chatbot platform for Indian SMBs:
website widget + WhatsApp, cited answers from the client's own documents, human handoff,
lead capture, and **Bot Studio**, where each tenant configures its own bots (persona, response
style, model, temperature, logo, header, footer, colours; draft -> publish -> rollback).

> Architecture style: **modular monolith** with hexagonal (ports & adapters) modules.
> See `docs/REPO_STRUCTURE.md` and `docs/adr/0001-modular-monolith-layout.md`.

## Quick start (local)

```bash
cp .env.example .env              # fill in values; never commit .env
pre-commit install                # secret scan + lint on every commit
cd backend && uv sync && cd ..    # Python 3.12 deps
make up                           # redis + api + worker (database: Supabase)
make migrate                      # alembic upgrade head
make test                         # backend: unit, contract, integration, architecture tests
make studio                       # Bot Studio (React + Vite) on http://localhost:5173
make check-keys                   # Phase 0 exit check: every API key works
make validate-golden              # Phase 0 exit check: golden set is well-formed
```

API: http://localhost:8000/health · docs: http://localhost:8000/docs (non-production only)

## Repository map

| Path | What lives there |
|---|---|
| `backend/` | FastAPI API + ARQ worker (Python 3.12, uv) |
| `dashboard/` | Bot Studio + admin app (React + Vite + TypeScript) |
| `widget/` | Embeddable chat widget → single `widget.js` (Phase 4) |
| `evals/` | Golden datasets + evaluation runners |
| `demos/` | Demo tenants: TaxMitra (CA firm), ClinicCare (clinic) |
| `n8n/` | Exported n8n workflow JSONs (CRM, Sheets, Slack) |
| `infra/` | docker-compose, Postgres init, Nginx, deploy notes |
| `scripts/` | Operational scripts (key checks, seeding) |
| `docs/` | ADRs 0001-0005, planning docs, runbooks, structure guide |
| `sales/` | Onboarding kit, proposals, SOW (Phase 7) |
