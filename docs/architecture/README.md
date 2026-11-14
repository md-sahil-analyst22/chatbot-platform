# Architecture notes

Keep diagrams here **only if they match the code**. Suggested files as the project grows:

- `c4-context.md`, `c4-container.md` - Mermaid C4 diagrams
- `data-model.md` - ER diagram (mirror of `backend/src/saathi/modules/*/adapters/orm.py`)
- `sequence-chat-turn.md` - one chat turn: channel -> agent -> RAG -> reply
- `trust-boundaries.md` - where untrusted input enters (widget, WhatsApp webhook, uploads, crawled pages)
