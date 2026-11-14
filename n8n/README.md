# n8n/

Exported workflow JSONs, version-controlled. Import via n8n UI -> Workflows -> Import from file.

| File | Trigger | Does |
|---|---|---|
| `workflows/lead_to_google_sheets.json` | Saathi `lead.created` webhook (signed) | Appends a row to a Google Sheet (Phase 5, P5.8) |

Rules
- Never export credentials; n8n stores them encrypted with `N8N_ENCRYPTION_KEY`.
- The first node must verify the Saathi webhook signature before doing anything else.
