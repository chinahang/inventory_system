from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from database import get_db
from models import OperationLog
from utils.permissions import page_context, require_permission

router = APIRouter(prefix="/logs", tags=["logs"])
templates = Jinja2Templates(directory="templates")

def require_view(request: Request, db: Session = Depends(get_db)):
    return require_permission(request, db, "log.view")

@router.get("", response_class=HTMLResponse)
def logs_page(request: Request,
              start_date: str = "", end_date: str = "",
              module: str = "", action: str = "",
              db: Session = Depends(get_db)):
    user = require_view(request, db)
    
    # Only query if filters are provided
    if start_date or end_date or module or action:
        query = db.query(OperationLog)
        if start_date:
            query = query.filter(OperationLog.created_at >= datetime.strptime(start_date, "%Y-%m-%d"))
        if end_date:
            query = query.filter(OperationLog.created_at < datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1))
        if module:
            query = query.filter(OperationLog.module == module)
        if action:
            query = query.filter(OperationLog.action == action)
        logs = query.order_by(OperationLog.created_at.desc()).limit(500).all()
    else:
        logs = []

    # Distinct modules and actions for filter dropdowns
    all_modules = db.query(OperationLog.module).distinct().all()
    all_actions = db.query(OperationLog.action).distinct().all()
    
    today = datetime.now().strftime("%Y-%m-%d")

    return templates.TemplateResponse("logs.html", page_context(
        request, db, user, logs=logs,
        start_date=start_date, end_date=end_date,
        module_filter=module, action_filter=action,
        all_modules=[m[0] for m in all_modules if m[0]],
        all_actions=[a[0] for a in all_actions if a[0]],
        today=today))
