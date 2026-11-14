#!/usr/bin/env python3
"""Validate a golden JSONL file (Phase 0 exit check, also runs in CI).

Checks: valid JSON per line, required fields and types, unique ids, known bot,
expected_source exists in demos/<bot>/docs/ for answerable rows, null source for unanswerable.

Usage: python3 evals/runners/validate_golden.py evals/golden/golden_v0.jsonl
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BOTS = {"taxmitra", "cliniccare"}
LANGS = {"en", "hi", "bn", "hinglish", "banglish"}
REQUIRED: dict[str, type | tuple[type, ...]] = {
    "id": str,
    "bot": str,
    "lang": str,
    "question": str,
    "expected_answer": (str, type(None)),
    "expected_source": (str, type(None)),
    "answerable": bool,
    "category": str,
}


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    stats: Counter[str] = Counter()
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {n}: invalid JSON ({exc.msg})")
            continue
        for field, typ in REQUIRED.items():
            if field not in row:
                errors.append(f"line {n}: missing '{field}'")
            elif not isinstance(row[field], typ):
                errors.append(f"line {n}: '{field}' has wrong type")
        rid = row.get("id")
        if rid in seen:
            errors.append(f"line {n}: duplicate id '{rid}'")
        seen.add(str(rid))
        bot = row.get("bot")
        if bot not in BOTS:
            errors.append(f"line {n}: unknown bot '{bot}'")
        if row.get("lang") not in LANGS:
            errors.append(f"line {n}: unknown lang '{row.get('lang')}'")
        source = row.get("expected_source")
        if row.get("answerable") is True:
            if not source:
                errors.append(f"line {n}: answerable row needs expected_source")
            elif bot in BOTS and not (REPO_ROOT / "demos" / bot / "docs" / source).exists():
                errors.append(f"line {n}: source file not found: demos/{bot}/docs/{source}")
            stats["answerable"] += 1
        elif row.get("answerable") is False:
            if source is not None:
                errors.append(f"line {n}: unanswerable row must have expected_source null")
            stats["unanswerable"] += 1
        stats[f"bot:{bot}"] += 1
    print(f"{path.name}: {sum(1 for _ in seen)} records | " + ", ".join(f"{k}={v}" for k, v in sorted(stats.items())))
    return errors


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "evals/golden/golden_v0.jsonl"
    errors = validate(path)
    for e in errors:
        print("ERROR", e)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
