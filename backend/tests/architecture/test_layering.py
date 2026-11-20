# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What it tests: That code layers don't import what they mustn't (e.g. domain/ never imports
#                FastAPI).
# How to run: cd backend && uv run pytest tests/architecture.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Fast, dependency-free boundary checks (import-linter does the full job in CI)."""

# ast — reads Python source code as a tree.
import ast

# From pathlib — file and folder paths: Path = a file or folder path.
from pathlib import Path

# The backend source folder.
SRC = Path(__file__).resolve().parents[2] / "src" / "saathi"
# The modules folder.
MODULES = SRC / "modules"
# Libraries that must never appear in a domain/ folder (R3).
FORBIDDEN_IN_DOMAIN = ("fastapi", "starlette", "sqlalchemy", "pydantic", "httpx", "redis", "arq")


# Helper: every module name a Python file imports.
def _imports(path: Path) -> set[str]:
    # The names found.
    names: set[str] = set()
    # Walk through every node of the file's syntax tree:
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        # `import x`...
        if isinstance(node, ast.Import):
            # ...add x;
            names.update(a.name for a in node.names)
        # `from x import y`...
        elif isinstance(node, ast.ImportFrom) and node.module:
            # ...add x.
            names.add(node.module)
    # Return them.
    return names


# domain/ code never imports a framework or database library.
def test_domain_layers_are_framework_free() -> None:
    # Collect 'file imports name' for...
    offenders = [
        f"{f.relative_to(SRC)} imports {name}"
        for f in MODULES.glob("*/domain/**/*.py")
        for name in _imports(f)
        if name.split(".")[0] in FORBIDDEN_IN_DOMAIN
    ]
    # Pass only if the list of offenders is empty (otherwise print them).
    assert not offenders, offenders


# domain/ code only imports its own module's domain and our error types.
def test_domain_only_uses_shared_kernel() -> None:
    """Domain may import stdlib, its own module's domain, and saathi.platform.errors only."""
    # Offenders found.
    offenders = []
    # For every domain file:
    for f in MODULES.glob("*/domain/**/*.py"):
        # which module it belongs to,
        own = f.relative_to(MODULES).parts[0]
        # what it may import,
        allowed = ("saathi.platform.errors", f"saathi.modules.{own}.domain")
        # and for every import in it:
        for name in _imports(f):
            # our own code but not allowed...
            if name.startswith("saathi") and not name.startswith(allowed):
                # ...is an offender.
                offenders.append(f"{f.relative_to(SRC)} -> {name}")
    # Pass only if the list of offenders is empty (otherwise print them).
    assert not offenders, offenders


# Routes (api/*.py except deps.py) never import adapters directly (R6).
def test_routes_do_not_construct_adapters() -> None:
    """Routes get services via dependencies; only api/deps.py may import adapters.

    Covers every file in a module's api/ folder (routes.py, config_routes.py,
    public_routes.py, webhooks.py, schemas.py, ...) except deps.py.
    """
    # Collect offenders:
    offenders = [
        f"{f.relative_to(SRC)} -> {name}"
        for f in MODULES.glob("*/api/*.py")
        if f.name != "deps.py"
        for name in _imports(f)
        if ".adapters" in name
    ]
    # Pass only if the list of offenders is empty (otherwise print them).
    assert not offenders, offenders


# Modules never reach into another module's internals (R4).
def test_modules_do_not_import_each_others_internals() -> None:
    # Offenders found.
    offenders = []
    # For every module file:
    for f in MODULES.glob("*/**/*.py"):
        # its own module name,
        own = f.relative_to(MODULES).parts[0]
        # and every import:
        for name in _imports(f):
            # split it into parts,
            parts = name.split(".")
            # saathi.modules.<other>.<something> where <other> isn't our module...
            if parts[:2] == ["saathi", "modules"] and len(parts) > 3 and parts[2] != own:
                # ...is an offender.
                offenders.append(f"{f.relative_to(SRC)} -> {name}")
    # Pass only if the list of offenders is empty (otherwise print them).
    assert not offenders, offenders


# platform/ never imports modules, the API layer or bootstrap.
def test_platform_does_not_import_modules() -> None:
    # Collect offenders:
    offenders = [
        f"{f.relative_to(SRC)} -> {name}"
        for f in (SRC / "platform").rglob("*.py")
        for name in _imports(f)
        if name.startswith(("saathi.modules", "saathi.api", "saathi.bootstrap"))
    ]
    # Pass only if the list of offenders is empty (otherwise print them).
    assert not offenders, offenders
