# Python 3.8 + FastAPI 0.95.x compatible
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import init_db, get_db
from routers import (auth, materials, personnel, equipment,
                     purchase, requisition, warehouse, reports, users, logs, backup, roles)
from utils.permissions import (first_accessible_path, get_user_permissions,
                               page_context, require_login)

app = FastAPI(title="台州海昌物流进销存系统")
templates = Jinja2Templates(directory="templates")

import os
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Register routers
app.include_router(auth.router)
app.include_router(materials.router)
app.include_router(personnel.router)
app.include_router(equipment.router)
app.include_router(purchase.router)
app.include_router(requisition.router)
app.include_router(warehouse.router)
app.include_router(reports.router)
app.include_router(users.router)
app.include_router(logs.router)
app.include_router(backup.router)
app.include_router(roles.router)


# FastAPI 0.95 still supports on_event; use it for compatibility
@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    perms = get_user_permissions(db, user)
    if "dashboard.view" not in perms:
        # 没有仪表盘权限时，跳到该角色第一个可访问的页面
        target = first_accessible_path(perms)
        if target:
            return RedirectResponse(target)
        return templates.TemplateResponse("no_access.html", {
            "request": request, "user": user, "permissions": perms,
        }, status_code=403)
    return templates.TemplateResponse("dashboard.html", page_context(request, db, user))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
