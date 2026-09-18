from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import Personnel
from utils.log_helper import write_log
from utils.numbering import next_code, rule_hint
from utils.permissions import page_context, require_permission

router = APIRouter(prefix="/personnel", tags=["personnel"])
templates = Jinja2Templates(directory="templates")

def require_manage(request, db):
    return require_permission(request, db, "personnel.manage")

@router.get("", response_class=HTMLResponse)
def list_personnel(request: Request, db: Session = Depends(get_db)):
    user = require_permission(request, db, "personnel.view")
    personnel = db.query(Personnel).all()
    return templates.TemplateResponse("personnel.html", page_context(
        request, db, user, personnel=personnel,
        next_code=next_code(db, "personnel", Personnel.employee_id),
        code_hint=rule_hint("personnel")))

@router.post("/create")
def create_personnel(request: Request, name: str = Form(...), employee_id: str = Form(""),
                     team: str = Form(""), phone: str = Form(""), role: str = Form(""),
                     db: Session = Depends(get_db)):
    user = require_manage(request, db)
    employee_id = (employee_id or "").strip() or next_code(db, "personnel", Personnel.employee_id)
    if db.query(Personnel).filter(Personnel.employee_id == employee_id).first():
        raise HTTPException(400, detail="工号已存在：{}".format(employee_id))
    p = Personnel(name=name, employee_id=employee_id, team=team, phone=phone, role=role)
    db.add(p)
    write_log(db, user, "新建", "人员", f"姓名：{name} 工号：{employee_id}", request)
    db.commit()
    return RedirectResponse("/personnel", status_code=302)

@router.post("/update/{pid}")
def update_personnel(pid: int, request: Request, name: str = Form(...), employee_id: str = Form(""),
                     team: str = Form(""), phone: str = Form(""), role: str = Form(""),
                     db: Session = Depends(get_db)):
    user = require_manage(request, db)
    p = db.query(Personnel).filter(Personnel.id == pid).first()
    if not p: raise HTTPException(404)
    employee_id = (employee_id or "").strip() or p.employee_id
    dup = db.query(Personnel).filter(Personnel.employee_id == employee_id,
                                     Personnel.id != pid).first()
    if dup:
        raise HTTPException(400, detail="工号已存在：{}".format(employee_id))
    p.name = name; p.employee_id = employee_id; p.team = team; p.phone = phone; p.role = role
    write_log(db, user, "修改", "人员", f"姓名：{name} 工号：{employee_id}", request)
    db.commit()
    return RedirectResponse("/personnel", status_code=302)

@router.post("/delete/{pid}")
def delete_personnel(pid: int, request: Request, db: Session = Depends(get_db)):
    user = require_manage(request, db)
    p = db.query(Personnel).filter(Personnel.id == pid).first()
    if not p: raise HTTPException(404)
    write_log(db, user, "删除", "人员", f"姓名：{p.name} 工号：{p.employee_id}", request)
    db.delete(p)
    db.commit()
    return RedirectResponse("/personnel", status_code=302)

@router.get("/api/list")
def api_list(db: Session = Depends(get_db)):
    personnel = db.query(Personnel).filter(Personnel.is_active == True).all()
    return [{"id": p.id, "name": p.name, "employee_id": p.employee_id,
             "team": p.team, "phone": p.phone, "role": p.role} for p in personnel]
