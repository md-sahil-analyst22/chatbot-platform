# evals/

| Path | Purpose |
|---|---|
| `golden/` | Versioned golden datasets (`golden_v0.jsonl` in Phase 0; `golden_v1.jsonl`, 38 rows over the first demo documents; `golden_v2.jsonl`, 65 rows = v1 + questions over the expanded demo documents; both drafted in Phase 2 and **pending owner review**) |
| `runners/` | `validate_golden.py` (Phase 0), `run_golden.py` (Phase 2: correctness + source match, `--sweep` tuning, `--smoke` offline check; see `docs/runbooks/local-setup.md`), RAGAS (Phase 6) |
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

Phase 2 exit criteria scored by `run_golden.py`: at least 80% of answerable rows correct (LLM judge
against `expected_answer`) **and** citing `expected_source`; every unanswerable row gets "I'm not
sure" (no invented answer).
