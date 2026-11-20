#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Checks that docs/CODE_GUIDE.md mentions every class and function in the backend.
# Run: make code-guide-check (CI runs it too). Fails with a list of missing names.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""List backend classes/functions that docs/CODE_GUIDE.md doesn't mention yet.

Usage (from the repo root):  make code-guide-check
Exit code 1 if anything is missing, so the guide can be kept in step with the code each phase.
Dunder methods (__init__ etc.) are ignored; every other name must appear in the guide.
"""

# From __future__ — Python language switches: annotations = lets type hints mention classes
#   defined later.
from __future__ import annotations

# ast — reads Python source code as a tree.
import ast
# re — regular expressions (text patterns).
import re
# sys — Python runtime details (output streams, exit codes).
import sys
# From pathlib — file and folder paths: Path = a file or folder path.
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "backend" / "src" / "saathi"
GUIDE = ROOT / "docs" / "CODE_GUIDE.md"


# All class and function names defined in one Python file.
def names_in(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            found.append(node.name)
            found += [
                f"{node.name}.{m.name}"
                for m in node.body
                if isinstance(m, ast.FunctionDef | ast.AsyncFunctionDef)
                and not (m.name.startswith("__") and m.name.endswith("__"))
            ]
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            found.append(node.name)
    return found


# Compare the code's names with the guide's and report what's missing.
def main() -> int:
    guide = GUIDE.read_text(encoding="utf-8")
    words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", guide))
    missing: list[str] = []
    total = 0
    for path in sorted(SRC.rglob("*.py")):
        for name in names_in(path):
            total += 1
            # A method counts as covered if its own name appears (tables list it under its class).
            if name.split(".")[-1] not in words:
                missing.append(f"{path.relative_to(SRC)}: {name}")
    if missing:
        print(f"CODE_GUIDE.md is missing {len(missing)} of {total} names:")
        for m in missing:
            print(f"  - {m}")
        return 1
    print(f"CODE_GUIDE.md covers all {total} backend classes, functions and methods.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
