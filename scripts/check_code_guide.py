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

# The repository's top folder (two levels up from this file).
ROOT = Path(__file__).resolve().parents[1]
# Where the backend's Python code lives.
SRC = ROOT / "backend" / "src" / "saathi"
# The guide file to check.
GUIDE = ROOT / "docs" / "CODE_GUIDE.md"


# All class and function names defined in one Python file.
def names_in(path: Path) -> list[str]:
    # Read the file and turn it into a tree Python can walk through.
    tree = ast.parse(path.read_text(encoding="utf-8"))
    # The names we find.
    found: list[str] = []
    # Look at each top-level item in the file:
    for node in tree.body:
        # a class...
        if isinstance(node, ast.ClassDef):
            # ...add its name,
            found.append(node.name)
            # and add its methods as Class.method,
            found += [
                f"{node.name}.{m.name}"
                for m in node.body
                if isinstance(m, ast.FunctionDef | ast.AsyncFunctionDef)
                and not (m.name.startswith("__") and m.name.endswith("__"))
            ]
        # a top-level function...
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            # ...add its name.
            found.append(node.name)
    # Return everything found.
    return found


# Compare the code's names with the guide's and report what's missing.
def main() -> int:
    # Read the guide.
    guide = GUIDE.read_text(encoding="utf-8")
    # Every word in the guide that looks like a code name.
    words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", guide))
    # Names the guide doesn't mention.
    missing: list[str] = []
    # How many names we checked.
    total = 0
    # Go through every backend Python file, in order...
    for path in sorted(SRC.rglob("*.py")):
        # ...and every class/function/method in it:
        for name in names_in(path):
            # count it;
            total += 1
            # A method counts as covered if its own name appears (tables list it under its class).
            if name.split(".")[-1] not in words:
                # remember it with its file.
                missing.append(f"{path.relative_to(SRC)}: {name}")
    # Anything missing:
    if missing:
        # say how many,
        print(f"CODE_GUIDE.md is missing {len(missing)} of {total} names:")
        # list them one by one,
        for m in missing:
            # each on its own line,
            print(f"  - {m}")
        # and fail (exit code 1, which fails CI).
        return 1
    # Nothing missing: say so...
    print(f"CODE_GUIDE.md covers all {total} backend classes, functions and methods.")
    # ...and succeed (exit code 0).
    return 0


# Only when the file is run directly (not imported):
if __name__ == "__main__":
    # run main() and exit with its result.
    sys.exit(main())
