# AGENTS.md — inventory_system

Python 3.8 / FastAPI 0.95 (server-side Jinja2 + Bootstrap 5) / SQLAlchemy 1.4 / SQLite.

## Python 3.8 + Windows 7 constraints

- No walrus `:=`, no PEP 604 union types (`X | Y`), no `match/case`.
- Use `datetime.strptime` and stdlib calendar — not `python-dateutil`.
- `requirements.txt` is pinned; install with `pip install -r requirements.txt`.

## Run the app

```bash
python main.py   # uvicorn on 0.0.0.0:8000
start.bat        # same thing with UTF-8 and pause-on-error
```

## No testing / linting / typechecking

There are zero test files, no pytest, no linter config, no mypy config. Do not invent test commands or frameworks. Do not add them without asking.

## Framework quirks (old FastAPI 0.95 style)

- Uses **deprecated** `@app.on_event("startup")` — not `lifespan`. Keep this pattern.
- Uses `declarative_base` from `sqlalchemy.ext.declarative`. Keep.
- Database migrations are raw `ALTER TABLE` in `database.py:_migrate()`. No Alembic.

## Auth

- Cookie-based sessions via `itsdangerous.URLSafeTimedSerializer`, 24h expiry.
- Passwords hashed with `passlib` + `bcrypt`, truncated to 72 chars (`password[:72]`).
- No CSRF protection. No OAuth.

## Project structure notes

- Root is **not** a Python package (no `__init__.py`). All imports are file-relative.
- Frontend assets are **vendored** under `static/cdn.jsdelivr.net/` — not from CDN.
- No `.gitignore` at root. Do not create one without asking.

## Role-based access (4 roles)

| Area | Required role(s) |
|---|---|
| Create/edit/delete Materials, Personnel, Equipment | admin |
| Create Purchase orders | admin, 采购员 |
| Delete Purchase/Requisition orders | admin |
| Create Requisition orders | admin, 仓管员 |
| Adjust stock | admin, 仓管员 |
| User management, Operation logs | admin |
| View ledgers, stock, reports | all roles |

## Stock calculation

`warehouse.py:get_stock_data()` computes stock **in memory** by summing purchase + requisition + adjustment records per material. No pre-computed stock table. O(n) over all materials.

## CodeGraph

`.codegraph/` is initialized. Use `codegraph_search`, `codegraph_callers`, `codegraph_context` etc. for structural questions instead of grep.
