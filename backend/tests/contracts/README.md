# Provider contract tests (Liskov substitution, proven)

Each port has ONE contract class (`*Contract`) describing behaviour every implementation must
have: shapes, ordering, empty input, and the error contract (vendor failures become
`ProviderError` / `ProviderTimeoutError`). Every implementation - real adapter (HTTP mocked
with `httpx.MockTransport`) and fake - subclasses it.

New vendor? Add `class TestMyVendorX(XContract)` with a `make()` method. If it passes, it is
safe to swap in by config.
