# ADR-0003: Versioned bot configuration, model catalog and prompt layering

- **Status:** Proposed (accept before P1.8)
- **Date:** 2026-11-12
- **Deciders:** Sahil

## Context
Tenants must configure their own bots in Bot Studio: persona, brand rules, banned topics,
response style, model, temperature, custom instructions, and widget branding (logo, header,
footer, colours, greeting). The original design stored a free-form `bots.settings` JSON and chose
one LLM for the whole platform from environment variables.

## Problem
1. Free-form JSON accepts anything; one bad edit can break a live bot with no way back.
2. Tenant-written prompts could remove the platform's grounding and safety rules.
3. A single platform-wide model cannot serve per-bot model choices.
4. The widget must read branding anonymously, but under Row-Level Security nothing is readable
   without a tenant context.

## Decision
1. **Typed, immutable config versions** (`bot_config_versions`): every save creates a DRAFT
   version; publishing archives the live version and publishes the target in one transaction;
   rollback copies an old version into a new draft and publishes it. A partial unique index
   guarantees one published version per bot.
2. **Presets first, advanced second.** Response style presets (Precise 0.1 / Balanced 0.3 /
   Friendly 0.6) for everyone; an optional temperature override, model choice, token limit and
   custom instructions for admins.
3. **Model catalog.** Bots store a catalog key (`standard`, `advanced`), never a vendor model id.
   The platform maps keys to provider + model id via configuration, and gates keys by plan.
4. **Per-request model resolution.** `LlmResolver` turns (catalog key, temperature, tokens) into a
   `CompletionClient` built with the right API key from a `CredentialSource`.
5. **Prompt layering.** Fixed platform rules first (not editable) → tenant text inside a sealed
   `<tenant_instructions>` section (angle brackets neutralised) → language → retrieved context.
6. **Public widget config** at `GET /public/v1/widgets/{public_key}/config`: the bot's public key is
   resolved to a tenant through a narrow `SECURITY DEFINER` function that returns only
   `(tenant_id, bot_id)`; the read then happens inside that tenant's RLS scope. Only public fields
   are returned; responses are cacheable for 60 s.
7. Embeddings and reranker stay **platform-wide**: changing the embedding model per bot would
   require re-indexing and break cross-bot assumptions.

## Alternatives
- Mutable single config row: simpler, but no audit trail and no rollback.
- Raw model ids from tenants: breaks when vendors retire models; no plan gating.
- Tenant writes the full system prompt: maximum flexibility, but removes safety guarantees.

## Advantages
Reversible changes, auditable history, vendor-neutral saved configs, safety rules that tenants
cannot remove, anonymous widget reads without weakening RLS.

## Disadvantages
More tables and endpoints; version rows accumulate (prune archived versions older than N).

## Security impact
Positive. Branding text rejects control characters and angle brackets and is rendered as text;
tenant prompt text cannot escape its section; the public endpoint exposes no prompt or settings.

## Performance impact
Chat path reads the published config once per conversation turn; cache it in Redis per bot
(key `t:{tenant}:bot:{bot}:config`, TTL 60 s, invalidated on publish).

## Operational impact
New tables `bot_config_versions`; new SQL function `resolve_bot_public_key`.

## Consequences
Config changes are released like code: draft → test in playground → publish → rollback if needed.

## Revisit when
Tenants need per-bot embeddings, A/B testing of configs, or approval workflows.
