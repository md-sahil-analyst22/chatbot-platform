# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Reads WHICH database rule was broken when an insert/update fails.
# Why: So a duplicate bot name or two simultaneous publishes become a friendly 409 'conflict'
#      instead of a crash.
# Used by: The tenancy repositories.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Translate database integrity errors into the domain error taxonomy (R29).

Repositories catch IntegrityError and ask which constraint fired, then raise ConflictError with
a client-safe message. Unknown violations are re-raised unchanged (they're bugs, not conflicts).
"""

from sqlalchemy.exc import IntegrityError


# Returns the name of the broken constraint (e.g. 'uq_bots_tenant_name'), or None.
def violated_constraint(exc: IntegrityError) -> str | None:
    """Name of the violated constraint or unique index, if the driver reports it (asyncpg does)."""
    cause = getattr(exc.orig, "__cause__", None) or exc.orig
    name = getattr(cause, "constraint_name", None)
    return name if isinstance(name, str) else None
