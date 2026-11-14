"""Phase 1 exit criterion: tenant A cannot read tenant B's data (P1.6).

Enabled once the tenants/bots migration + RLS policies exist. Must connect as the NON-owner
app role (saathi_app); the owner role bypasses RLS and would make this test meaningless.

Test plan:
  1. As owner: insert tenant A, tenant B, and bot_b belonging to B.
  2. As saathi_app inside tenant_session(A): SELECT bot_b by id      -> no row.
  3. As saathi_app inside tenant_session(A): INSERT bot with tenant B -> RLS WITH CHECK error.
  4. As saathi_app with NO tenant set: SELECT * FROM bots             -> zero rows (fail closed).
  5. Through the API with a token for A: GET /api/v1/bots/{bot_b}     -> 404 (not 403).
"""

import os

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skipif(os.environ.get("RUN_DB_TESTS") != "1", reason="enable in Phase 1 (P1.6)")
def test_tenant_a_cannot_read_tenant_b() -> None:
    pytest.fail("implement in P1.6 following the plan in the module docstring")
