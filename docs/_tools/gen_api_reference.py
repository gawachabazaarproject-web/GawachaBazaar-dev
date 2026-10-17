"""Generate docs/03-api/API_REFERENCE.md from the backend's router source (AST) and its
OpenAPI document. Read-only; never connects to a database.

Run from backend/:
    venv/Scripts/python.exe -I ../docs/_tools/gen_api_reference.py > ../docs/03-api/API_REFERENCE.md
"""

import ast
import os
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
os.environ["DATABASE_URL"] = "postgresql+psycopg://x:x@127.0.0.1:1/x"  # unroutable; never connects
sys.path.insert(0, str(BACKEND))
ROOT = BACKEND / "app" / "api" / "v1"

tree = ast.parse((ROOT / "router.py").read_text(encoding="utf-8"))
alias_to_mod = {}
for n in ast.walk(tree):
    if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("app.api.v1."):
        for a in n.names:
            alias_to_mod[a.asname or a.name] = (n.module.split(".")[-1], a.name)
prefix_of = {}
for n in ast.walk(tree):
    if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "include_router":
        alias = n.args[0].id
        pref = next((k.value.value for k in n.keywords if k.arg == "prefix"), "")
        prefix_of[alias_to_mod[alias]] = pref

AUTH_NAMES = ("get_current_user", "get_auth_context", "get_current_customer", "get_current_admin")


def txt(node):
    return ast.unparse(node) if node is not None else ""


CONSTS: dict = {}  # module-level assignments of the file currently being parsed


def expand_arg(a):
    """Render a require_roles/require_permission argument; resolve `*_SOME_TUPLE` constants."""
    if isinstance(a, ast.Starred) and isinstance(a.value, ast.Name) and a.value.id in CONSTS:
        val = CONSTS[a.value.id]
        if isinstance(val, (ast.Tuple, ast.List)):
            return ", ".join(txt(e) for e in val.elts)
    return txt(a)


def dep_calls(node):
    out = []
    for c in ast.walk(node):
        if isinstance(c, ast.Call):
            f = txt(c.func)
            if f in ("require_permission", "require_roles"):
                out.append(f"{f}({', '.join(expand_arg(a) for a in c.args)})")
            elif f in AUTH_NAMES:
                out.append(f)
        elif isinstance(c, ast.Name):
            if c.id in AUTH_NAMES:
                out.append(c.id)
            elif c.id in CONSTS and isinstance(CONSTS[c.id], ast.Call) and txt(CONSTS[c.id].func) == "Depends":
                out += dep_calls(CONSTS[c.id])  # e.g. _ADMIN_ONLY = Depends(require_roles(ADMIN))
    return out


rows = []
for f in sorted(ROOT.glob("*.py")):
    if f.name in ("router.py", "__init__.py"):
        continue
    mod = f.stem
    t = ast.parse(f.read_text(encoding="utf-8"))
    CONSTS.clear()
    for n in t.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            CONSTS[n.targets[0].id] = n.value
    routers = {}
    for n in t.body:
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and txt(n.value.func) == "APIRouter":
            kw = {k.arg: k.value for k in n.value.keywords}
            routers[n.targets[0].id] = dep_calls(kw["dependencies"]) if "dependencies" in kw else []
    for n in ast.walk(t):
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for d in n.decorator_list:
            if not (
                isinstance(d, ast.Call)
                and isinstance(d.func, ast.Attribute)
                and d.func.attr in ("get", "post", "put", "patch", "delete", "websocket")
                and getattr(d.func.value, "id", None) in routers
            ):
                continue
            rname = d.func.value.id
            path = d.args[0].value if d.args else ""
            kw = {k.arg: k.value for k in d.keywords}
            handler = []
            for dflt in n.args.defaults:
                handler += dep_calls(dflt)
            for dflt in n.args.kw_defaults:
                if dflt is not None:
                    handler += dep_calls(dflt)
            if "dependencies" in kw:
                handler += dep_calls(kw["dependencies"])
            rate = [
                txt(x.args[0]).strip("'\"")
                for x in n.decorator_list
                if isinstance(x, ast.Call) and txt(x.func) == "limiter.limit"
            ]
            rows.append(
                dict(
                    method="WS" if d.func.attr == "websocket" else d.func.attr.upper(),
                    path="/api/v1" + prefix_of.get((mod, rname), "<unmounted>") + path,
                    deps=routers[rname] + sorted(set(handler)),
                    module=mod,
                    line=n.lineno,
                    rate=rate,
                    file=f"backend/app/api/v1/{f.name}",
                )
            )

from app.main import app  # noqa: E402

spec = app.openapi()
ops = {}
for p, item in spec["paths"].items():
    for m, o in item.items():
        ref = lambda s: (s or "").split("/")[-1]  # noqa: E731
        body = None
        if o.get("requestBody"):
            content = o["requestBody"].get("content", {})
            c = next(iter(content.values()), {})
            body = ref(c.get("schema", {}).get("$ref")) or c.get("schema", {}).get("type") or "body"
            if "multipart/form-data" in content:
                body = "multipart: " + body
        resp = {}
        for code, v in o["responses"].items():
            if code == "422":
                continue
            s = next(iter(v.get("content", {}).values()), {}).get("schema", {})
            resp[code] = ref(s.get("$ref")) or (s.get("type") or "")
        ops[f"{m.upper()} {p}"] = dict(
            summary=o.get("summary", ""),
            params=[f"{x['name']}({x['in'][0]})" for x in o.get("parameters", [])],
            body=body,
            resp=resp,
        )


def auth_label(r):
    if r["method"] == "WS":
        return "Firebase ID token in `?token=` (checked in handler)"
    if r["path"].endswith("/auth/sync"):
        return "Bearer Firebase ID token verified in service (no existing app account needed; creates/links one)"
    if r["path"].endswith("/auth/legacy-migrate"):
        return "Public (rate-limited)"
    if "/payments/webhooks/" in r["path"]:
        return "Public; gateway signature verified in service"
    parts = []
    for d in r["deps"]:
        m = re.match(r"require_roles\((.*)\)", d)
        if m:
            parts.append("roles " + m.group(1).replace(", ", "/"))
        m = re.match(r"require_permission\((.*)\)", d)
        if m:
            parts.append("perm " + m.group(1).strip("'\""))
        if d == "get_current_user":
            parts.append("signed-in user")
        if d == "get_auth_context":
            parts.append("signed-in (email-verification gate skipped)")
        if d == "get_current_customer":
            parts.append("roles CUSTOMER")
        if d == "get_current_admin":
            parts.append("roles ADMIN")
    if any(p.startswith(("roles ", "perm ")) for p in parts):
        parts = [p for p in parts if p != "signed-in user"]  # implied by the role/permission gate
    return "; ".join(dict.fromkeys(parts)) or "Public"


extra = [
    dict(method="GET", path="/health", deps=[], module="platform", line=0, rate=[], file="backend/app/main.py"),
    dict(method="GET", path="/health/db", deps=[], module="platform", line=0, rate=[], file="backend/app/main.py"),
    dict(method="GET", path="/api/v1/ping", deps=[], module="platform", line=0, rate=[], file="backend/app/api/v1/router.py"),
]
allrows = rows + extra
groups = {}
for r in allrows:
    groups.setdefault(r["module"], []).append((r, ops.get(f"{r['method']} {r['path']}", {})))

print("# API Reference")
print()
print(
    f"> **Status:** Verified (generated from source). **Generated:** {date.today().isoformat()} by "
    "[`docs/_tools/gen_api_reference.py`](../_tools/gen_api_reference.py)."
)
print(
    "> **Evidence:** router decorators in [`backend/app/api/v1/`](../../backend/app/api/v1), router mounting in "
    "[`router.py`](../../backend/app/api/v1/router.py), the app's own OpenAPI document (`app.openapi()`), and the "
    "reviewed role matrix [`backend/tests/authz_golden.json`](../../backend/tests/authz_golden.json)."
)
print()
print(
    "Conventions (envelope, errors, pagination): [API_CONVENTIONS.md](API_CONVENTIONS.md). Webhook: "
    "[WEBHOOKS.md](WEBHOOKS.md). Roles and permissions: "
    "[USER_ROLES_AND_PERMISSIONS](../01-requirements/USER_ROLES_AND_PERMISSIONS.md)."
)
print()
n_http = sum(1 for r in allrows if r["method"] != "WS")
print(
    f"**{n_http} HTTP operations + 1 WebSocket.** Interactive docs (`/docs`, `/redoc`, `/openapi.json`) are served "
    "only when `APP_ENV` is not `production` ([`main.py`](../../backend/app/main.py))."
)
print()
print(
    "How to read the **Auth** column: `roles A/B` = caller must hold at least one of those roles (checked live "
    "against `user_roles`); `perm x.y` = the caller's roles must grant that permission in the static map "
    "([`permissions.py`](../../backend/app/core/permissions.py)); `signed-in user` = any ACTIVE user whose token "
    "verified (email/password users also need a verified email). Router-level role gates apply to every route in "
    "that router. **Request** column: `name(p|q|h)` are path/query/header parameters; the schema name is the JSON "
    "body model. **Response** lists declared success responses (`code: Schema`); every error uses the uniform "
    "envelope."
)
print()
print(
    f"Field-level request/response schemas live in the OpenAPI document ({len(spec['components']['schemas'])} schemas "
    "at generation time) and the Pydantic models in [`backend/app/schemas/`](../../backend/app/schemas); they are "
    "not repeated here to avoid drift."
)
print()
order = sorted(groups, key=lambda m: (m == "platform", m))
print("## Index")
print()
print("| Module | Operations |")
print("|---|---|")
for m in order:
    print(f"| [{m}](#{m.replace('_', '-')}) | {len(groups[m])} |")
print()
for m in order:
    print(f"## {m.replace('_', '-')}")
    print()
    files = sorted({r["file"] for r, _ in groups[m]})
    print("Source: " + ", ".join(f"[`{x}`](../../{x})" for x in files))
    print()
    print("| Method | Path | Auth | Request | Response | Notes |")
    print("|---|---|---|---|---|---|")
    for r, o in sorted(groups[m], key=lambda x: (x[0]["path"], x[0]["method"])):
        req = ", ".join(o.get("params", []) + ([o["body"]] if o.get("body") else [])) or "-"
        resp = ", ".join(f"{k}: {v}" if v else k for k, v in o.get("resp", {}).items()) or "-"
        notes = []
        if r["rate"]:
            notes.append("rate limit " + "/".join(r["rate"]) + " per client IP (in-process)")
        if o.get("summary"):
            notes.append(o["summary"])
        loc = f"[L{r['line']}](../../{r['file']}#L{r['line']})" if r["line"] else ""
        print(
            f"| {r['method']} | `{r['path']}` | {auth_label(r)} | {req} | {resp} | "
            f"{'; '.join(notes).replace('|', '/')} {loc} |"
        )
    print()
