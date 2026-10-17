# Documentation tools

Small read-only scripts used to produce the generated reference documents. They import
the backend (without connecting to any database) or parse its source, and print Markdown.
They do **not** modify application code.

| Script | Produces | Run from `backend/` |
|---|---|---|
| `gen_api_reference.py` | [`../03-api/API_REFERENCE.md`](../03-api/API_REFERENCE.md) | `venv/Scripts/python.exe -I ../docs/_tools/gen_api_reference.py > ../docs/03-api/API_REFERENCE.md` |
| `gen_schema_reference.py` | [`../04-database/DATABASE_SCHEMA.md`](../04-database/DATABASE_SCHEMA.md) | `venv/Scripts/python.exe -I ../docs/_tools/gen_schema_reference.py > ../docs/04-database/DATABASE_SCHEMA.md` |

Both set a throw-away `DATABASE_URL` pointing at an unroutable address before importing
the app, so they never reach a real database. Regenerate after any change to a router,
model or migration; the scripts print today's date in the "Generated" line.

On Linux/macOS use `venv/bin/python` instead of `venv/Scripts/python.exe`.
