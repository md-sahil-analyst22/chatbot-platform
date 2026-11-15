# modules/leads

**Phase 5 (P5.5 - P5.8).** Conversational lead capture and booking tools, signed outbound event webhooks (lead.created ...) consumed by n8n.

Create `domain/`, `application/`, `ports/`, `adapters/`, `api/` only when the first task in this module starts.

`adapters/orm.py` already defines the `leads` table (created by migration 0002, P1.4); the other layers arrive with the module's first task.
