# AGENTS.md — inventory_system

进销存管理系统 (TZ Haichang Logistics). Python 3.8 / FastAPI 0.95.2 (server-rendered Jinja2 + Bootstrap 5) / SQLAlchemy 1.4 / SQLite.

## Python 3.8 + Windows 7 constraints

- No walrus `:=`, no PEP 604 unions (`X | Y`), no `match/case`, no f-strings are fine but keep to 3.8 syntax.
- Do **not** import `python-dateutil` even though it is pinned in `requirements.txt`. Use `datetime.strptime`, `timedelta`, and stdlib `calendar` (see `routers/reports.py:_add_months`).
- `requirements.txt` is pinned for Win7; install with `pip install -r requirements.txt`.

## Run

```bash
python main.py   # uvicorn 0.0.0.0:8000, reload=False -> restart to pick up edits
start.bat        # same, UTF-8 console + pause-on-error
```
Default login `admin` / `admin123` (seeded by `database.py:init_db`). No tests, no linter, no typechecker — do not invent commands or add them without asking.

## Framework quirks (intentionally old-style)

- `@app.on_event("startup")` (deprecated) — keep, not `lifespan`.
- `declarative_base` from `sqlalchemy.ext.declarative` — keep.
- Migrations are raw `ALTER TABLE` entries in `database.py:_migrate()`; no Alembic. Add new columns there too, not just to `models.py`.
- `templates.TemplateResponse("x.html", {"request": request, ...})` old signature.

## Auth & permissions

- Cookie `session` via `itsdangerous.URLSafeTimedSerializer`, 24h (`max_age=86400`). Secret key is hardcoded in `routers/auth.py`. No CSRF, no OAuth.
- Passwords: `passlib` bcrypt, truncated to 72 chars (`password[:72]`).
- Roles are **rows** in `roles` (Chinese `name`), and `users.role` still stores that Chinese string (`管理员` / `采购员` / `仓管员` / `普通操作员` by default). Role rename via `/roles` also updates `users.role`.
- Permissions are **not hardcoded in routers any more**: the catalog lives in `utils/permissions.py` (`PERMISSION_GROUPS` / `ALL_PERMISSIONS`, code → 中文 label), grants live in `role_permissions` (one role → many permission rows). `/roles` (`routers/roles.py` + `templates/roles.html`, permission `role.manage`) is the admin UI; `database.py:_seed_roles()` seeds built-in roles with the pre-permission behavior as defaults and never overwrites later edits.
- `管理员` is a locked super role: always all permissions, cannot be edited/deleted (`Role.is_system`) — prevents lockout. Delete a role only when no user has it.
- In routers use `require_permission(request, db, "<code>")` (302 → /login, 403 → JSON 权限不足), `require_any`, `has_permission`, `get_user_permissions`, and pass `page_context(request, db, user, ...)` to `TemplateResponse` so templates get `permissions`. Templates gate UI with `{% if 'x.y' in permissions %}`. Add new permission points to `utils/permissions.py` first, then grant them on `/roles`.
- Export/print endpoints carry their own `*.export` / `*.print` permission checks (`/purchase/ledger/pdf|excel`, `/requisition/ledger/pdf|excel`, `/requisition/print/{id}`, `/warehouse/report/*`, `/reports/pdf|excel`) — the page guard does not cover them.
- Still unguarded (anonymous): `/materials/api/list`, `/personnel/api/list`, `/equipment/api/list` — used by the create-order pages.

## Numbering

- `utils/numbering.py` is the single source of auto-numbering: `next_code(db, module, column)` scans existing values with the same prefix and takes max sequence + 1 (no counter table). Modules: `material` WL+4, `equipment` SB+4, `personnel` GH+4, `purchase` CG+YYYYMMDD-+3, `requisition` LL+YYYYMMDD-+3.
- Base-data forms leave the code field **empty** with a `留空自动生成` placeholder (context `next_code` / `code_hint`); the POST handler generates when blank and still rejects duplicates. Order numbers keep their original format.

## Stock

Computed in memory, no stock table. `routers/warehouse.py:get_stock_data()` sums purchase − requisition + adjustment per material (O(n) over all materials). `routers/requisition.py:get_stock()` and the moving-average price endpoint duplicate the same math. Requisition create rejects when `stock < qty`.

## Backup / restore

Admin-only. `utils/backup.py` uses SQLite online backup into `backups/`, keeps 7 (`MAX_BACKUPS`), metadata in `*.meta.json`, restore writes a `restore_point_*.db` first. Job status is in-memory only (`_jobs`), so it resets on restart. Endpoints under `/backup`.

## Project layout / gotchas

- Root is not a package; all imports are file-relative. `routers/` and `utils/` do have `__init__.py`.
- Frontend assets are vendored under `static/cdn.jsdelivr.net/` (Bootstrap, Chart.js) — not loaded from a CDN.
- `inventory.db` is **tracked in git** despite being listed in `.gitignore`, so schema/data changes appear in diffs. `backups/`, `.codegraph/`, `.venv3-8/` are ignored.
- Order numbers: `CG<YYYYMMDD>-NNN` (purchase) and `LL<YYYYMMDD>-NNN` (requisition), sequence derived from the latest existing order that day.
- PDF Chinese fonts are auto-detected from Windows paths with Linux fallbacks (`utils/pdf_generator.py`).
- UI text, log details, and role values are Chinese; keep new strings consistent.
