"""Authorization regression matrix over EVERY HTTP operation in the OpenAPI spec.

For each operation, a request is sent as: anonymous, and as a valid user holding
exactly one of: no role, CUSTOMER, WHOLESALER, SUPPORT, HUB_STAFF, OPERATIONS,
DELIVERY_PARTNER (path ids = 999999, body = {} - rejected by auth before any
business logic or validation if the caller is not allowed).

Two invariants are enforced:
  1. Anonymous callers get 401 on everything except the reviewed public list.
  2. The set of roles that can get past authorization on each operation equals
     the reviewed snapshot in tests/authz_golden.json. ADMIN-only operations are
     simply absent from the snapshot. A NEW endpoint, or a widened one, fails
     this test until a human reviews it and regenerates the snapshot:
         AUTHZ_REGEN=1 pytest tests/test_authz_matrix.py
"""

import json
import os
import re
from pathlib import Path

from app.main import app
from tests.firebase_fake import auth_headers_for
from tests.test_phase_9_rbac import _create_user_with_roles

GOLDEN = Path(__file__).with_name("authz_golden.json")
ROLES = ["NONE", "CUSTOMER", "WHOLESALER", "SUPPORT", "HUB_STAFF", "OPERATIONS", "DELIVERY_PARTNER"]


def _operations():
    for path, item in app.openapi()["paths"].items():
        for method in item:
            if method in ("get", "post", "put", "patch", "delete"):
                yield method.upper(), path


def test_every_operation_matches_the_reviewed_authorization_snapshot(client, db_session) -> None:
    headers = {}
    for i, role in enumerate(ROLES):
        user = _create_user_with_roles(db_session, *(() if role == "NONE" else (role,)), email=f"azm_{i}@example.com")
        headers[role] = auth_headers_for(db_session, user)

    public, reachable, server_errors = [], {}, []
    for method, path in _operations():
        url = re.sub(r"\{[^}]+\}", "999999", path)
        kwargs = {"json": {}} if method in ("POST", "PUT", "PATCH") else {}
        key = f"{method} {path}"
        anon = client.request(method, url, **kwargs).status_code
        if anon != 401:
            public.append(key)
        allowed = []
        for role in ROLES:
            code = client.request(method, url, headers=headers[role], **kwargs).status_code
            if code >= 500:
                server_errors.append((key, role, code))
            if code not in (401, 403):
                allowed.append(role)
        if anon == 401 and allowed:
            reachable[key] = allowed

    live = {"public": sorted(public), "reachable_by_role": reachable}
    if os.environ.get("AUTHZ_REGEN"):
        GOLDEN.write_text(json.dumps(live, indent=1, sort_keys=True), encoding="utf-8")
        return
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))

    assert not server_errors, f"5xx on auth probes: {server_errors[:5]}"
    assert live["public"] == golden["public"], (
        f"public (unauthenticated) surface changed: +{sorted(set(live['public']) - set(golden['public']))} "
        f"-{sorted(set(golden['public']) - set(live['public']))}"
    )
    drift = {
        k: {"golden": golden["reachable_by_role"].get(k, []), "live": live["reachable_by_role"].get(k, [])}
        for k in set(golden["reachable_by_role"]) | set(live["reachable_by_role"])
        if golden["reachable_by_role"].get(k, []) != live["reachable_by_role"].get(k, [])
    }
    assert not drift, f"role access changed on {len(drift)} operation(s): {dict(list(drift.items())[:5])}"
