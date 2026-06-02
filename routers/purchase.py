from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
from database import get_db
from models import PurchaseOrder, PurchaseItem, Material, Personnel, User
from routers.auth import get_session_user
from utils.pdf_generator import generate_purchase_ledger_pdf
from utils.excel_generator import generate_ledger_excel
from utils.log_helper import write_log

router = APIRouter(prefix="/purchase", tags=["purchase"])
templates = Jinja2Templates(directory="templates")

# 采购员 + 管理员 可新建/删除采购单；其他角色只读台账
PURCHASE_WRITE_ROLES = ["管理员", "采购员"]
LEDGER_VIEW_ROLES    = ["管理员", "采购员", "仓管员", "普通操作员"]

def require_write(request, db):
    user = get_session_user(request, db)
    if not user: raise HTTPException(302, headers={"Location": "/login"})
    if user.role not in PURCHASE_WRITE_ROLES: raise HTTPException(403, detail="权限不足")
    return user

def require_view(request, db):
    user = get_session_user(request, db)
    if not user: raise HTTPException(302, headers={"Location": "/login"})
    if user.role not in LEDGER_VIEW_ROLES: raise HTTPException(403, detail="权限不足")
    return user

def generate_order_no(db):
    today = datetime.now().strftime("%Y%m%d")
    prefix = f"CG{today}-"
    last = db.query(PurchaseOrder).filter(PurchaseOrder.order_no.like(f"{prefix}%")).order_by(PurchaseOrder.order_no.desc()).first()
    seq = (int(last.order_no.split("-")[-1]) + 1) if last else 1
    return f"{prefix}{seq:03d}"

def build_rows(orders):
    rows = []
    for o in orders:
        for item in o.items:
            rows.append({
                "order_id": o.id,
                "order_no": o.order_no,
                "order_date": o.order_date.strftime("%Y-%m-%d"),
                "material_name": item.material.name if item.material else "",
                "material_model": item.material.model if item.material else "",
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "total_amount": item.total_amount,
                "purchaser": o.purchaser.name if o.purchaser else "",
                "operator": o.operator.full_name if o.operator else "",
                "supplier_contact": o.supplier_contact or "",
                "remark": o.remark or "",
            })
    return rows

def query_orders(db, start_date, end_date):
    query = db.query(PurchaseOrder)
    if start_date:
        query = query.filter(PurchaseOrder.order_date >= datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        query = query.filter(PurchaseOrder.order_date < datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1))
    return query.order_by(PurchaseOrder.order_date.desc()).all()

@router.get("", response_class=HTMLResponse)
def purchase_page(request: Request, db: Session = Depends(get_db)):
    user = get_session_user(request, db)
    if not user: return RedirectResponse("/login")
    if user.role not in PURCHASE_WRITE_ROLES: return RedirectResponse("/")
    personnel = db.query(Personnel).filter(Personnel.is_active == True).all()
    materials = db.query(Material).all()
    materials_data = [{"id": m.id, "code": m.code, "name": m.name,
                       "model": m.model or "", "spec": m.spec or "", "unit": m.unit or ""}
                      for m in materials]
    return templates.TemplateResponse("purchase.html", {
        "request": request, "user": user,
        "personnel": personnel, "materials": materials_data
    })

@router.post("/create")
async def create_purchase(request: Request, db: Session = Depends(get_db)):
    user = require_write(request, db)
    form = await request.form()
    order_date_str = form.get("order_date", "")
    purchaser_id = int(form.get("purchaser_id", 0))
    supplier_contact = form.get("supplier_contact", "")
    remark = form.get("remark", "")
    items = json.loads(form.get("items", "[]"))
    if not items: raise HTTPException(400, detail="请至少添加一条物料明细")
    order_date = datetime.strptime(order_date_str, "%Y-%m-%d") if order_date_str else datetime.now()
    order_no = generate_order_no(db)
    order = PurchaseOrder(order_no=order_no, order_date=order_date,
                          purchaser_id=purchaser_id, operator_id=user.id,
                          supplier_contact=supplier_contact, remark=remark)
    db.add(order)
    db.flush()
    for item in items:
        mat = db.query(Material).filter(Material.id == int(item["material_id"])).first()
        if not mat: continue
        qty = float(item["quantity"]); price = float(item["unit_price"])
        db.add(PurchaseItem(order_id=order.id, material_id=mat.id,
                            quantity=qty, unit_price=price, total_amount=qty * price))
    write_log(db, user, "新建", "采购单", f"单号：{order_no}", request)
    db.commit()
    return RedirectResponse("/purchase/ledger", status_code=302)

@router.get("/ledger", response_class=HTMLResponse)
def ledger_page(request: Request, start_date: str = "", end_date: str = "",
                db: Session = Depends(get_db)):
    user = require_view(request, db)
    # Only query if date filters are provided
    rows = build_rows(query_orders(db, start_date, end_date)) if start_date or end_date else []
    today = datetime.now().strftime("%Y-%m-%d")
    return templates.TemplateResponse("purchase_ledger.html", {
        "request": request, "user": user, "rows": rows,
        "start_date": start_date, "end_date": end_date,
        "today": today,
    })

@router.get("/ledger/pdf")
def ledger_pdf(start_date: str = "", end_date: str = "", db: Session = Depends(get_db)):
    rows = build_rows(query_orders(db, start_date, end_date))
    pdf_bytes = generate_purchase_ledger_pdf(rows, start_date, end_date)
    return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=purchase_ledger.pdf"})

@router.get("/ledger/excel")
def ledger_excel(start_date: str = "", end_date: str = "", db: Session = Depends(get_db)):
    rows = build_rows(query_orders(db, start_date, end_date))
    columns = ["单号","采购日期","物料名称","型号","件数","单价(元)","总金额(元)","采购员","操作员","供应商联系方式","备注"]
    data = [[r["order_no"],r["order_date"],r["material_name"],r["material_model"],
             r["quantity"],r["unit_price"],r["total_amount"],r["purchaser"],r["operator"],
             r["supplier_contact"],r["remark"]] for r in rows]
    excel_bytes = generate_ledger_excel("采购台账", columns, data, start_date, end_date)
    return StreamingResponse(iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=purchase_ledger.xlsx"})

@router.post("/delete/{order_id}")
def delete_purchase(order_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_session_user(request, db)
    if not user: raise HTTPException(302, headers={"Location": "/login"})
    if user.role != "管理员": raise HTTPException(403, detail="仅管理员可删除采购单")
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not order: raise HTTPException(404)
    write_log(db, user, "删除", "采购单", f"单号：{order.order_no}", request)
    db.delete(order)
    db.commit()
    return RedirectResponse("/purchase/ledger", status_code=302)
