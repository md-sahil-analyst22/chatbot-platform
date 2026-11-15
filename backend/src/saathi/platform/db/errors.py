"""Translate database integrity errors into the domain error taxonomy (R29).

Repositories catch IntegrityError and ask which constraint fired, then raise ConflictError with
a client-safe message. Unknown violations are re-raised unchanged (they're bugs, not conflicts).
"""

from sqlalchemy.exc import IntegrityError


def violated_constraint(exc: IntegrityError) -> str | None:
    """Name of the violated constraint or unique index, if the driver reports it (asyncpg does)."""
    cause = getattr(exc.orig, "__cause__", None) or exc.orig
    name = getattr(cause, "constraint_name", None)
    return name if isinstance(name, str) else None
