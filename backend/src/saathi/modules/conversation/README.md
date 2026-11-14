# modules/conversation

Owns: `conversation`, `message`, agent graph, memory, prompts. Phase 3.

- `domain/state.py` - `ChatState` and `Intent` (what flows through the graph)
- `application/graph.py` - builds the LangGraph `StateGraph` (guard -> language -> rewrite -> intent -> ...)
- `application/nodes/` - one file per node; nodes are plain functions using ports
- `ports/llm.py` - `CompletionClient` and `StreamingClient` (model, temperature and token limit chosen per request from the bot's config)
- `ports/credentials.py` - `CredentialSource`: which API key to use for a tenant + provider
- `application/llm_resolver.py` - bot's catalog model key -> provider + model id -> client with the right key
- `application/prompt_builder.py` - fixed platform rules first, tenant instructions in a sealed section, then context
- `adapters/llm/` - Gemini (primary) and Anthropic adapters; `adapters/memory/` - Redis session memory
- `prompts/` - `platform_rules_v1.md` (fixed safety rules, never tenant-editable)
- `api/routes.py` - `/api/v1/chat`, `/api/v1/chat/stream` (SSE)

Latency rule: anything that does not need to happen before the user sees the reply
(analytics, usage rollups, summaries) is enqueued, not awaited.
