from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import Equipment
from utils.log_helper import write_log
from utils.numbering import next_code, rule_hint
from utils.permissions import page_context, require_permission

router = APIRouter(prefix="/equipment", tags=["equipment"])
templates = Jinja2Templates(directory="templates")

def require_manage(request, db):
    return require_permission(request, db, "equipment.manage")

@router.get("", response_class=HTMLResponse)
def list_equipment(request: Request, db: Session = Depends(get_db)):
    user = require_permission(request, db, "equipment.view")
    equipment = db.query(Equipment).all()
    return templates.TemplateResponse("equipment.html", page_context(
        request, db, user, equipment=equipment,
        next_code=next_code(db, "equipment", Equipment.code),
        code_hint=rule_hint("equipment")))

@router.post("/create")
def create_equipment(request: Request, name: str = Form(...), code: str = Form(""),
                     model: str = Form(""), department: str = Form(""),
                     db: Session = Depends(get_db)):
    user = require_manage(request, db)
    code = (code or "").strip() or next_code(db, "equipment", Equipment.code)
    if db.query(Equipment).filter(Equipment.code == code).first():
        raise HTTPException(400, detail="设备编码已存在：{}".format(code))
    e = Equipment(code=code, name=name, model=model, department=department)
    db.add(e)
    write_log(db, user, "新建", "设备", f"编码：{code} 名称：{name}", request)
    db.commit()
    return RedirectResponse("/equipment", status_code=302)

@router.post("/update/{eid}")
def update_equipment(eid: int, request: Request, name: str = Form(...), code: str = Form(""),
                     model: str = Form(""), department: str = Form(""),
                     db: Session = Depends(get_db)):
    user = require_manage(request, db)
    e = db.query(Equipment).filter(Equipment.id == eid).first()
    if not e: raise HTTPException(404)
    code = (code or "").strip() or e.code
    dup = db.query(Equipment).filter(Equipment.code == code, Equipment.id != eid).first()
    if dup:
        raise HTTPException(400, detail="设备编码已存在：{}".format(code))
    e.code = code; e.name = name; e.model = model; e.department = department
    write_log(db, user, "修改", "设备", f"编码：{code} 名称：{name}", request)
    db.commit()
    return RedirectResponse("/equipment", status_code=302)

@router.post("/delete/{eid}")
def delete_equipment(eid: int, request: Request, db: Session = Depends(get_db)):
    user = require_manage(request, db)
    e = db.query(Equipment).filter(Equipment.id == eid).first()
    if not e: raise HTTPException(404)
    write_log(db, user, "删除", "设备", f"编码：{e.code} 名称：{e.name}", request)
    db.delete(e)
    db.commit()
    return RedirectResponse("/equipment", status_code=302)

@router.get("/api/list")
def api_list(db: Session = Depends(get_db)):
    equipment = db.query(Equipment).filter(Equipment.is_active == True).all()
    return [{"id": e.id, "code": e.code, "name": e.name,
             "model": e.model, "department": e.department} for e in equipment]
