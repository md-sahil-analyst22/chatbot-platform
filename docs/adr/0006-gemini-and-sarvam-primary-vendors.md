# ADR-0006: Gemini and Sarvam as the primary AI vendors

- **Status:** Accepted
- **Date:** 2026-11-14
- **Deciders:** Sahil

## Context
The stack plan (`02_ARCHITECTURE_AND_STACK.md`) listed Anthropic models for the answer LLM, with
Gemini only as an alternative. It chose Google `gemini-embedding-001` for embeddings and Sarvam for
Indic speech. The code had only Anthropic (LLM), OpenAI (embeddings) and Cohere (reranker) adapters
and defaulted to `EMBEDDING_PROVIDER=openai`. That contradicted the plan (REPO_STRUCTURE §4.8).

The product owner decided that LLM, speech-to-text and text-to-speech must work with **any**
vendor, with **Gemini** and **Sarvam** as the primary ones.

## Problem
1. The default answer model was a vendor that is no longer primary.
2. Building ingestion on the OpenAI embedder would force re-indexing later (R13).
3. There were no speech ports, so voice notes (P4.9) and the voice channel (Phase 8.2) would have
   been built straight against one vendor.

## Decision
1. **LLM:** add a Gemini `CompletionClient` (`adapters/llm/gemini_llm.py`, registry key `gemini`).
   Gemini owns the plain catalog keys `standard` (`GEMINI_MODEL_SMALL`, currently
   `gemini-3.8-flash`) and `advanced` (`GEMINI_MODEL_LARGE`, currently `gemini-4-argon`, which
   needs a billed key). Model ids are configuration, so upgrades don't touch code or saved configs. Anthropic stays available as `claude-standard` / `claude-advanced`,
   offered only when its model ids are set. Each vendor gets its own catalog keys, so adding or
   removing a vendor never changes a saved bot config.
2. **Embeddings:** `gemini-embedding-2` (GA April 2026; text input only for now) shortened from
   3,072 to 1,536 dimensions, L2-normalised, is the platform default (`EMBEDDING_PROVIDER=gemini`).
   It replaces the plan's `gemini-embedding-001`; nothing has been ingested yet, so no re-index. OpenAI stays registered as a fallback. R13 still applies:
   choosing it is fixed before the first ingestion.
3. **Speech:** new ports `SpeechToText` and `TextToSpeech` in `modules/channels/ports/speech.py`,
   with registries `stt_registry` / `tts_registry`. Sarvam adapters are
   the defaults: STT `saaras:v4` (`mode=transcribe`), TTS `bulbul:v4-flash`, with `bulbul:v3` as
   the fallback for languages v4-flash doesn't support (Malayalam, Odia) (`STT_PROVIDER=sarvam`, `TTS_PROVIDER=sarvam`). Another vendor (for example Gemini
   or Google speech) is a new adapter file plus one import line.
4. **Reranker:** unchanged (Cohere).

## Alternatives considered
- **Keep Anthropic primary, add Gemini as an option.** Doesn't match the product decision.
- **One "AI vendor" setting for everything.** Speech, embeddings and answers have different best
  vendors; coupling them blocks mixing (for example Gemini answers + Sarvam speech).
- **Gemini for speech too.** Sarvam is stronger for Hindi/Bengali (the core market); Gemini speech
  can be added later through the same port.

## Advantages
- The code matches the plan for embeddings before Phase 2 ingestion starts.
- Voice notes and the voice channel are built against a port, not a vendor.
- One Gemini key covers answers and embeddings.

## Disadvantages
- Two vendor relationships (Google + Sarvam) instead of one, plus Cohere for reranking.
- Gemini and Anthropic answers differ, so golden-set evals must run against the Gemini models.

## Security impact
- New platform secrets: `GEMINI_API_KEY`, `SARVAM_API_KEY`. They are read only by adapter settings
  classes as `SecretStr`, never logged (R17). A missing **or empty** key fails closed (R16).
- Tenant keys for Gemini (Phase 8 BYOK) plug into the existing credential source under `gemini`.

## Performance impact
- Embedding batches are capped at 100 texts per request (Gemini limit).
- Sarvam TTS input is capped by `SARVAM_TTS_MAX_CHARS` (default 1,500); longer replies must be split
  by the caller (voice channel, Phase 8.2).

## Operational impact
- `make check-keys` checks the Gemini key and lists the chat model ids, so
  `GEMINI_MODEL_SMALL/LARGE` can be set to models that exist for the key.
- Spend caps must be set in Google AI Studio / Cloud and in the Sarvam dashboard (P0.2).

## Consequences
- `02_ARCHITECTURE_AND_STACK.md`, REPO_STRUCTURE §4.8 and `.env.example` are updated in the same
  change (R43).
- Sarvam returns WAV audio. WhatsApp voice replies, if added, need OGG/Opus conversion in the
  channel adapter.

## Model ids (checked 2026-11-14)
Sources disagreed on some ids, so `make check-keys` verifies that the configured Gemini models exist
for the key. `gemini-2.5-*` is retired (routes elsewhere from 1 Dec 2026), so don't use it.

## Revisit when
- Golden-set evals show another model clearly better for Bengali/Hindi answers.
- Sarvam or Gemini pricing or availability changes materially.
