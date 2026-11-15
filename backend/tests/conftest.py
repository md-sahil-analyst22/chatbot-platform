"""Test defaults. Unit tests never need real services; integration tests opt in."""

import os

os.environ.setdefault("ENV", "test")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://saathi_app:test@localhost:5432/saathi_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

pytest_plugins = ["tests.db_fixtures"]
