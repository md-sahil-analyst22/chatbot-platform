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

SRC = Path(__file__).resolve().parents[2] / "src" / "saathi"
MODULES = SRC / "modules"
FORBIDDEN_IN_DOMAIN = ("fastapi", "starlette", "sqlalchemy", "pydantic", "httpx", "redis", "arq")


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_domain_layers_are_framework_free() -> None:
    offenders = [
        f"{f.relative_to(SRC)} imports {name}"
        for f in MODULES.glob("*/domain/**/*.py")
        for name in _imports(f)
        if name.split(".")[0] in FORBIDDEN_IN_DOMAIN
    ]
    assert not offenders, offenders


def test_domain_only_uses_shared_kernel() -> None:
    """Domain may import stdlib, its own module's domain, and saathi.platform.errors only."""
    offenders = []
    for f in MODULES.glob("*/domain/**/*.py"):
        own = f.relative_to(MODULES).parts[0]
        allowed = ("saathi.platform.errors", f"saathi.modules.{own}.domain")
        for name in _imports(f):
            if name.startswith("saathi") and not name.startswith(allowed):
                offenders.append(f"{f.relative_to(SRC)} -> {name}")
    assert not offenders, offenders


def test_routes_do_not_construct_adapters() -> None:
    """Routes get services via dependencies; only api/deps.py may import adapters.

    Covers every file in a module's api/ folder (routes.py, config_routes.py,
    public_routes.py, webhooks.py, schemas.py, ...) except deps.py.
    """
    offenders = [
        f"{f.relative_to(SRC)} -> {name}"
        for f in MODULES.glob("*/api/*.py")
        if f.name != "deps.py"
        for name in _imports(f)
        if ".adapters" in name
    ]
    assert not offenders, offenders


def test_modules_do_not_import_each_others_internals() -> None:
    offenders = []
    for f in MODULES.glob("*/**/*.py"):
        own = f.relative_to(MODULES).parts[0]
        for name in _imports(f):
            parts = name.split(".")
            if parts[:2] == ["saathi", "modules"] and len(parts) > 3 and parts[2] != own:
                offenders.append(f"{f.relative_to(SRC)} -> {name}")
    assert not offenders, offenders


def test_platform_does_not_import_modules() -> None:
    offenders = [
        f"{f.relative_to(SRC)} -> {name}"
        for f in (SRC / "platform").rglob("*.py")
        for name in _imports(f)
        if name.startswith(("saathi.modules", "saathi.api", "saathi.bootstrap"))
    ]
    assert not offenders, offenders
