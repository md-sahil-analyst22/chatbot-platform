## Why
<!-- The problem or plan task (e.g. P1.9). Link the planning doc / ADR. -->

## What
<!-- What changed. Where the code goes (REPO_STRUCTURE 0.5). -->

## Impact
<!-- Blast radius, compatibility (API clients, widgets, stored configs, rolling deploy),
     future features it could block, risks (security, tenant isolation, latency, cost). -->

## Tests
<!-- Exactly what you ran and the results. Baseline before vs after. -->

## Rollout / rollback

---

### Definition of done (REPO_STRUCTURE 1.12)

**Placement and boundaries**
- [ ] Every new file is in the folder 0.5 says, with a standard name
- [ ] No new imports between modules (R4); domain imports nothing technical (R3)
- [ ] Routes and schemas don't import adapters; wiring is in `api/deps.py` (R6)
- [ ] New vendor code is an adapter behind a port, registered and selected by config (R7)

**Security and tenancy**
- [ ] Tenant comes from the principal or the public-key lookup, never the request (R8)
- [ ] Every query filters by `tenant_id` (R15); new tables follow the checklist (R23)
- [ ] Missing auth, key or signature denies (R16)
- [ ] No secrets or personal data in code, logs, errors or responses (R17, R18)
- [ ] Inputs bounded and validated; uploads checked by bytes (R19)
- [ ] Public endpoints return only public fields (R10)

**Correctness**
- [ ] Domain objects validate themselves and are immutable (R20)
- [ ] Multi-row writes are in one transaction (R26)
- [ ] Errors are typed; no stack traces or internals reach the client (R29)
- [ ] Nothing slow was added to the chat reply path (R31); I/O is async (R32)

**Proof**
- [ ] Tests added at the right layer (R34); adapters pass contract suites (R35)
- [ ] Endpoints tested for 401 / 403 / 404 / 422 (R36)
- [ ] All quality gates pass (R42); migrations up and down on real Postgres (R25)
- [ ] `.env.example`, docs and ADRs updated in the same change (R12, R43)
- [ ] Any conflict with the plan or rules is stated, not hidden (R44)
