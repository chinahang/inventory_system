from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import Equipment
from routers.auth import get_session_user
from utils.log_helper import write_log

router = APIRouter(prefix="/equipment", tags=["equipment"])
templates = Jinja2Templates(directory="templates")

def admin_only(request, db):
    user = get_session_user(request, db)
    if not user: raise HTTPException(302, headers={"Location": "/login"})
    if user.role != "管理员": raise HTTPException(403, detail="权限不足")
    return user

@router.get("", response_class=HTMLResponse)
def list_equipment(request: Request, db: Session = Depends(get_db)):
    user = get_session_user(request, db)
    if not user: return RedirectResponse("/login")
    equipment = db.query(Equipment).all()
    return templates.TemplateResponse("equipment.html", {"request": request, "equipment": equipment, "user": user})

@router.post("/create")
def create_equipment(request: Request, code: str = Form(...), name: str = Form(...),
                     model: str = Form(""), department: str = Form(""),
                     db: Session = Depends(get_db)):
    user = admin_only(request, db)
    e = Equipment(code=code, name=name, model=model, department=department)
    db.add(e)
    write_log(db, user, "新建", "设备", f"编码：{code} 名称：{name}", request)
    db.commit()
    return RedirectResponse("/equipment", status_code=302)

@router.post("/update/{eid}")
def update_equipment(eid: int, request: Request, code: str = Form(...), name: str = Form(...),
                     model: str = Form(""), department: str = Form(""),
                     db: Session = Depends(get_db)):
    user = admin_only(request, db)
    e = db.query(Equipment).filter(Equipment.id == eid).first()
    if not e: raise HTTPException(404)
    e.code = code; e.name = name; e.model = model; e.department = department
    write_log(db, user, "修改", "设备", f"编码：{code} 名称：{name}", request)
    db.commit()
    return RedirectResponse("/equipment", status_code=302)

@router.post("/delete/{eid}")
def delete_equipment(eid: int, request: Request, db: Session = Depends(get_db)):
    user = admin_only(request, db)
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
