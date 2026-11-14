# ADR-0001: Modular-monolith repository layout with hexagonal modules

- **Status:** Proposed (accept before starting P1.1)
- **Date:** 2026-11-11
- **Deciders:** Sahil

## Context
`02_ARCHITECTURE_AND_STACK.md` section 5 sketches a **layer-flat** backend
(`app/api`, `app/rag`, `app/agent`, `app/channels`, `app/db`, ...). The project's engineering
standard requires a **modular monolith** with strict module boundaries, ports & adapters, and
vendor independence (Interface -> Registry -> Factory -> Adapter), so selected modules
(ingestion, voice, channels) can later become separate services.

## Problem
A layer-flat layout lets any file import any other. Within weeks, RAG code imports DB models
from conversations, vendor SDK calls spread into business logic, and nothing can be extracted
or tested in isolation.

## Decision
- `backend/src/saathi/modules/<module>/` - one folder per business capability:
  `tenancy` (incl. Bot Studio configuration), `knowledge`, `conversation`, `channels`,
  `handoff`, `leads`, `analytics`, `credentials` (tenants' own API keys, Phase 8).
- Inside each module: `domain/`, `application/`, `ports/`, `adapters/`, `api/`
  (only the layers the module actually needs).
- `backend/src/saathi/platform/` - cross-cutting technical code only (config, db engine,
  tenant context, logging, errors, security, provider registry). Platform never imports modules.
- Cross-module calls go through the other module's public `__init__.py` facade only.
- Rules are enforced in CI by `import-linter` and `tests/architecture/`.

Every path in the plan maps 1:1 to a new location (see `docs/REPO_STRUCTURE.md`, "Mapping").

## Alternatives considered
1. **Keep the flat layout** - fastest for week 1; coupling grows quickly; extraction is a rewrite.
2. **Microservices now** - correct boundaries but far too much ops for one developer.

## Advantages
Clear ownership, vendor swaps by config, testable domain logic, CI-enforced boundaries,
microservice extraction becomes a move, not a rewrite.

## Disadvantages
About 10-15% more files; slightly more ceremony for tiny modules.

## Security impact
Tenant context is applied in one place (`platform/db/tenant_context.py`); fewer ad-hoc query paths.

## Performance impact
None at runtime (same process).

## Operational impact
None - still one API image + one worker image.

## Consequences
Domain code may import only the standard library, its own module's `domain/`, and the
shared kernel `saathi.platform.errors` (enforced by `tests/architecture/test_layering.py`).
Small modules may merge `domain` + `application` until they grow. Vendor code always stays
behind `ports/` + `adapters/`; that rule is never relaxed.

## Revisit when
Solo velocity in Phase 2 drops noticeably because of ceremony, or a module needs independent
scaling (likely candidates: ingestion worker, voice in Phase 8.2).
