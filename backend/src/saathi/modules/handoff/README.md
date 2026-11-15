# modules/handoff

**Phase 5 (P5.1 - P5.4, P5.12).** Handoff state machine (bot -> requested -> notified -> human -> closed / after-hours), triggers, AI summary, alerts, agent inbox WebSocket.

Create `domain/`, `application/`, `ports/`, `adapters/`, `api/` only when the first task in this module starts.

`adapters/orm.py` already defines the `handoffs` table (created by migration 0002, P1.4); the other layers arrive with the module's first task.
