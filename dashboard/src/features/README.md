# src/features/

One folder per Bot Studio feature. Each owns its page(s), its React Query hooks (`api.ts`) and its tests.

| Folder | Feature |
|---|---|
| `bots/` | List and create bots |
| `bot-config/` | Persona, presets, advanced settings, draft -> publish -> rollback, version history |
| `branding/` | Logo, header, footer, colours + live widget preview |
| `playground/` | Chat with the draft before publishing (Phase 3) |
| `credentials/` | Own provider API keys, write-only and masked (Pro, Phase 8) |

Features never import each other's internals; shared pieces go to `src/components/` or `src/lib/`.
