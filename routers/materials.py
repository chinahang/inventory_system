from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import Material
from routers.auth import get_session_user
from utils.log_helper import write_log

router = APIRouter(prefix="/materials", tags=["materials"])
templates = Jinja2Templates(directory="templates")

def admin_only(request, db):
    user = get_session_user(request, db)
    if not user: raise HTTPException(302, headers={"Location": "/login"})
    if user.role != "管理员": raise HTTPException(403, detail="权限不足")
    return user

@router.get("", response_class=HTMLResponse)
def list_materials(request: Request, db: Session = Depends(get_db)):
    user = get_session_user(request, db)
    if not user: return RedirectResponse("/login")
    materials = db.query(Material).all()
    return templates.TemplateResponse("materials.html", {"request": request, "materials": materials, "user": user})

@router.post("/create")
def create_material(request: Request, code: str = Form(...), name: str = Form(...),
                    model: str = Form(""), spec: str = Form(""), unit: str = Form(""),
                    safety_stock: float = Form(0), db: Session = Depends(get_db)):
    user = admin_only(request, db)
    if db.query(Material).filter(Material.code == code).first():
        raise HTTPException(400, detail="物料编码已存在")
    m = Material(code=code, name=name, model=model, spec=spec, unit=unit, safety_stock=safety_stock)
    db.add(m)
    write_log(db, user, "新建", "物料", f"编码：{code} 名称：{name}", request)
    db.commit()
    return RedirectResponse("/materials", status_code=302)

@router.post("/update/{material_id}")
def update_material(material_id: int, request: Request, code: str = Form(...), name: str = Form(...),
                    model: str = Form(""), spec: str = Form(""), unit: str = Form(""),
                    safety_stock: float = Form(0), db: Session = Depends(get_db)):
    user = admin_only(request, db)
    m = db.query(Material).filter(Material.id == material_id).first()
    if not m: raise HTTPException(404)
    m.code = code; m.name = name; m.model = model; m.spec = spec; m.unit = unit; m.safety_stock = safety_stock
    write_log(db, user, "修改", "物料", f"编码：{code} 名称：{name}", request)
    db.commit()
    return RedirectResponse("/materials", status_code=302)

@router.post("/delete/{material_id}")
def delete_material(material_id: int, request: Request, db: Session = Depends(get_db)):
    user = admin_only(request, db)
    m = db.query(Material).filter(Material.id == material_id).first()
    if not m: raise HTTPException(404)
    write_log(db, user, "删除", "物料", f"编码：{m.code} 名称：{m.name}", request)
    db.delete(m)
    db.commit()
    return RedirectResponse("/materials", status_code=302)

@router.get("/api/list")
def api_list_materials(db: Session = Depends(get_db)):
    materials = db.query(Material).all()
    return [{"id": m.id, "code": m.code, "name": m.name, "model": m.model,
             "spec": m.spec, "unit": m.unit, "safety_stock": m.safety_stock} for m in materials]
