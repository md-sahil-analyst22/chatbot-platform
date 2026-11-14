# widget/ (Phase 4)

Embeddable chat widget built to a single `widget.js` (< 50 KB gzipped).

```html
<script src="https://cdn.example.com/widget.js" data-bot-key="pk_demo_xxx" defer></script>
```

- `src/` - widget source (Preact or vanilla TS)
- `demo/` - local test page (P4 exit criterion: embed on a plain HTML page)

Security: `data-bot-key` is a **public** key that only identifies the bot. The API enforces the
bot's CORS allowlist and rate limits; it grants no admin access.
