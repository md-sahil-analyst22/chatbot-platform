# dashboard/ - Bot Studio (React + Vite + TypeScript)

The admin app where a tenant creates and configures its bots: prompt, response style, model,
temperature, branding (logo, header, footer, colours), draft/publish/rollback, a test playground
and (Pro, Phase 8) its own provider API keys.

```bash
cd dashboard
cp .env.example .env.local     # VITE_API_BASE_URL=http://localhost:8000
npm install
npm run dev                    # http://localhost:5173
npm run typecheck && npm test && npm run build
```

## Structure

| Path | Purpose |
|---|---|
| `src/main.tsx` | Entry: mounts the app |
| `src/app/` | App shell: providers (React Query), routes, layout |
| `src/lib/api/` | Typed API client + DTO types mirroring the backend contract |
| `src/lib/auth/` | Access-token holder (Supabase Auth / Clerk SDK plugs in at P1.7) |
| `src/components/` | Shared UI pieces (layout, form fields) |
| `src/features/bots/` | List and create bots |
| `src/features/bot-config/` | Config editor: presets, advanced settings, draft / publish / rollback |
| `src/features/branding/` | Logo, header, footer, colours + live widget preview |
| `src/features/playground/` | Test chat against the draft config (P3.8) |
| `src/features/credentials/` | Own API keys (Pro, Phase 8): write-only, masked |
| `src/styles/` | Global CSS |

## Rules
- Talks only to the public API (`/api/v1/...`). Never to the database or vendors directly.
- Never renders tenant text as HTML (no `dangerouslySetInnerHTML`); React escapes text.
- API keys are write-only: the UI sends them once and only ever shows `••••abcd`.
- Access tokens are kept in memory by the auth SDK, not in `localStorage`.
- Validation in `features/bot-config/schema.ts` mirrors the backend; the backend is authoritative.
