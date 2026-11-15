# modules/analytics

**Phase 5 (P5.15) / Phase 6.** usage_log, cost per conversation, KPI rollups (resolution, handoff, unanswered, CSAT). Rollups run in the worker, never in the chat path.

Create `domain/`, `application/`, `ports/`, `adapters/`, `api/` only when the first task in this module starts.

`adapters/orm.py` already defines the `usage_logs` table (created by migration 0002, P1.4); the other layers arrive with the module's first task.
