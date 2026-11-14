# evals/

| Path | Purpose |
|---|---|
| `golden/` | Versioned golden datasets (`golden_v0.jsonl` in Phase 0, `golden_v1.jsonl` in Phase 3) |
| `runners/` | `validate_golden.py` (Phase 0), `run_golden.py` + RAGAS (Phase 2/6) |
| `reports/` | Generated eval reports (git-ignored except README) |

## Golden record schema (one JSON object per line)

| Field | Type | Notes |
|---|---|---|
| `id` | str | unique, e.g. `tm-001` |
| `bot` | str | `taxmitra` or `cliniccare` |
| `lang` | str | `en`, `hi`, `bn`, `hinglish`, `banglish` |
| `question` | str | what the user types |
| `expected_answer` | str or null | key facts the answer must contain |
| `expected_source` | str or null | file name in `demos/<bot>/docs/`; null if unanswerable |
| `answerable` | bool | false = bot must say it is not sure / refuse |
| `category` | str | e.g. `hours`, `fees`, `checklist`, `refusal`, `medical_refusal` |
| `expected_behavior` | str, optional | for refusals, e.g. `refuse_and_offer_callback` |

Target for v0: ~30 answerable + 5-8 unanswerable.
