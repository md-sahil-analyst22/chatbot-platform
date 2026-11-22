# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: A small 'to-do list for after the save'. Code that must only run once the database
#       transaction has really committed (e.g. putting a background job on the queue) adds itself
#       here; the request's database dependency runs the list right after the commit.
# Why: If we queued a job BEFORE the commit, the worker could pick it up and find no row yet,
#      or the transaction could roll back and leave a job pointing at nothing.
# Pattern: Unit-of-work 'after commit' hook. Plain Python: no database or framework imports.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Callbacks that run only after a transaction commits (never after a rollback)."""

# From collections.abc — standard type names: Awaitable = something you can `await`;
#   Callable = a function type.
from collections.abc import Awaitable, Callable

# structlog — structured logging (JSON log lines).
import structlog

# The logger for this file.
log = structlog.get_logger()

# A callback = a function with no arguments that returns something awaitable.
AfterCommitCallback = Callable[[], Awaitable[None]]


# The per-transaction to-do list.
class AfterCommit:
    """Collects callbacks during a transaction; `run()` is called once, after COMMIT.

    A failing callback is logged and the rest still run: the data is already committed, so the
    caller can't undo it. Every callback must therefore be safe to lose and recoverable (for
    ingestion: the source stays `queued` and the resync endpoint queues it again).
    """

    # Fixed attributes (saves memory, prevents typos creating new ones).
    __slots__ = ("_callbacks", "_ran")

    # Start with an empty list.
    def __init__(self) -> None:
        # The callbacks, in the order they were added.
        self._callbacks: list[AfterCommitCallback] = []
        # True once run() has been called (a list runs at most once).
        self._ran = False

    # Add one callback to the list.
    def add(self, callback: AfterCommitCallback) -> None:
        # Adding after the list already ran would silently never run: refuse loudly instead.
        if self._ran:
            raise RuntimeError("after-commit callbacks already ran")
        # Remember it.
        self._callbacks.append(callback)

    # How many callbacks are waiting (used by tests).
    def __len__(self) -> int:
        # The length of the list.
        return len(self._callbacks)

    # Run every callback once. Call this ONLY after the transaction committed.
    async def run(self) -> None:
        # Mark as ran first, so a callback can't add more work to this list.
        self._ran = True
        # Take the callbacks and empty the list.
        callbacks, self._callbacks = self._callbacks, []
        # Run them in order...
        for callback in callbacks:
            # ...each one guarded separately...
            try:
                # ...run it;
                await callback()
            # ...a failure is logged (type only: no message, which could carry data) and the
            #   loop carries on with the next one.
            except Exception as exc:  # committed data can't be undone; log and go on
                log.error("after_commit.failed", error_type=type(exc).__name__)
