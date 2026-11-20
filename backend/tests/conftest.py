# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Shared test settings (pytest loads this first). Unit tests never need real services.
# How to run: Used automatically by the tests; nothing to run directly.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Test defaults. Unit tests never need real services; integration tests opt in."""

# os — talks to the operating system (environment variables, files).
import os

# Tell the app it's running tests (unless already set).
os.environ.setdefault("ENV", "test")
# A dummy database address so the settings load; unit tests never connect to it.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://saathi_app:test@localhost:5432/saathi_test"
)
# A dummy Redis address, for the same reason.
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

# Load the real-Postgres helpers (db_fixtures.py) for every test.
pytest_plugins = ["tests.db_fixtures"]
