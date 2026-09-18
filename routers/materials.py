from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import Material
from utils.log_helper import write_log
from utils.numbering import next_code, rule_hint
from utils.permissions import page_context, require_permission

router = APIRouter(prefix="/materials", tags=["materials"])
templates = Jinja2Templates(directory="templates")

def require_manage(request, db):
    return require_permission(request, db, "material.manage")

@router.get("", response_class=HTMLResponse)
def list_materials(request: Request, db: Session = Depends(get_db)):
    user = require_permission(request, db, "material.view")
    materials = db.query(Material).all()
    return templates.TemplateResponse("materials.html", page_context(
        request, db, user, materials=materials,
        next_code=next_code(db, "material", Material.code),
        code_hint=rule_hint("material")))

@router.post("/create")
def create_material(request: Request, name: str = Form(...), code: str = Form(""),
                    model: str = Form(""), spec: str = Form(""), unit: str = Form(""),
                    safety_stock: float = Form(0), db: Session = Depends(get_db)):
    user = require_manage(request, db)
    code = (code or "").strip() or next_code(db, "material", Material.code)
    if db.query(Material).filter(Material.code == code).first():
        raise HTTPException(400, detail="物料编码已存在：{}".format(code))
    m = Material(code=code, name=name, model=model, spec=spec, unit=unit, safety_stock=safety_stock)
    db.add(m)
    write_log(db, user, "新建", "物料", f"编码：{code} 名称：{name}", request)
    db.commit()
    return RedirectResponse("/materials", status_code=302)

@router.post("/update/{material_id}")
def update_material(material_id: int, request: Request, name: str = Form(...), code: str = Form(""),
                    model: str = Form(""), spec: str = Form(""), unit: str = Form(""),
                    safety_stock: float = Form(0), db: Session = Depends(get_db)):
    user = require_manage(request, db)
    m = db.query(Material).filter(Material.id == material_id).first()
    if not m: raise HTTPException(404)
    code = (code or "").strip() or m.code
    dup = db.query(Material).filter(Material.code == code, Material.id != material_id).first()
    if dup:
        raise HTTPException(400, detail="物料编码已存在：{}".format(code))
    m.code = code; m.name = name; m.model = model; m.spec = spec; m.unit = unit; m.safety_stock = safety_stock
    write_log(db, user, "修改", "物料", f"编码：{code} 名称：{name}", request)
    db.commit()
    return RedirectResponse("/materials", status_code=302)

@router.post("/delete/{material_id}")
def delete_material(material_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_manage(request, db)
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
