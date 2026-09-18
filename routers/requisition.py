from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
from database import get_db
from models import RequisitionOrder, RequisitionItem, Material, Personnel, Equipment, User, PurchaseItem, StockAdjustment
from utils.pdf_generator import generate_requisition_pdf, generate_requisition_ledger_pdf
from utils.excel_generator import generate_ledger_excel
from utils.log_helper import write_log
from utils.numbering import next_code
from utils.permissions import (get_user_permissions, page_context,
                               require_any, require_permission)

router = APIRouter(prefix="/requisition", tags=["requisition"])
templates = Jinja2Templates(directory="templates")

# 权限点见 utils/permissions.py，可在「权限配置」页面按角色勾选
PERM_CREATE = "requisition.create"
PERM_VIEW   = "requisition.view"
PERM_DELETE = "requisition.delete"
PERM_PRINT  = "requisition.print"
PERM_EXPORT = "requisition.export"

def require_write(request, db):
    return require_permission(request, db, PERM_CREATE)

def require_view(request, db):
    return require_permission(request, db, PERM_VIEW)

def generate_order_no(db):
    """领料单号：LL + YYYYMMDD + - + 3位流水，例 LL20240917-001"""
    return next_code(db, "requisition", RequisitionOrder.order_no)

def get_stock(material_id, db):
    total_in  = sum(i.quantity for i in db.query(PurchaseItem).filter(PurchaseItem.material_id == material_id).all())
    total_out = sum(i.quantity for i in db.query(RequisitionItem).filter(RequisitionItem.material_id == material_id).all())
    total_adj = sum(a.quantity for a in db.query(StockAdjustment).filter(StockAdjustment.material_id == material_id).all())
    return total_in - total_out + total_adj

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
                "total_amount": item.total_amount,
                "equipment": o.equipment.name if o.equipment else "",
                "personnel": o.personnel.name if o.personnel else "",
                "operator": o.operator.full_name if o.operator else "",
            })
    return rows

def query_orders(db, start_date, end_date):
    query = db.query(RequisitionOrder)
    if start_date:
        query = query.filter(RequisitionOrder.order_date >= datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        query = query.filter(RequisitionOrder.order_date < datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1))
    return query.order_by(RequisitionOrder.order_date.desc()).all()

@router.get("", response_class=HTMLResponse)
def requisition_page(request: Request, db: Session = Depends(get_db)):
    user = require_view(request, db)
    if PERM_CREATE not in get_user_permissions(db, user):
        return RedirectResponse("/")
    personnel = db.query(Personnel).filter(Personnel.is_active == True).all()
    equipment = db.query(Equipment).filter(Equipment.is_active == True).all()
    materials = db.query(Material).all()
    materials_data = [{"id": m.id, "code": m.code, "name": m.name,
                       "model": m.model or "", "spec": m.spec or "", "unit": m.unit or ""}
                      for m in materials]
    equipment_data = [{"id": e.id, "code": e.code, "name": e.name,
                         "model": e.model or "", "department": e.department or ""}
                        for e in equipment]
    return templates.TemplateResponse("requisition.html", page_context(
        request, db, user,
        personnel=personnel, equipment=equipment_data, materials=materials_data))

@router.post("/create")
async def create_requisition(request: Request, db: Session = Depends(get_db)):
    user = require_write(request, db)
    form = await request.form()
    order_date_str = form.get("order_date", "")
    equipment_id = int(form.get("equipment_id", 0))
    personnel_id = int(form.get("personnel_id", 0))
    remark = form.get("remark", "")
    items = json.loads(form.get("items", "[]"))
    if not items: raise HTTPException(400, detail="请至少添加一条物料明细")
    for item in items:
        mat_id = int(item["material_id"])
        qty = float(item["quantity"])
        stock = get_stock(mat_id, db)
        mat = db.query(Material).filter(Material.id == mat_id).first()
        if stock < qty:
            raise HTTPException(400, detail=f"物料【{mat.name}】库存不足，当前库存：{stock}{mat.unit}")
    order_date = datetime.strptime(order_date_str, "%Y-%m-%d") if order_date_str else datetime.now()
    order_no = generate_order_no(db)
    order = RequisitionOrder(order_no=order_no, order_date=order_date,
                             equipment_id=equipment_id, personnel_id=personnel_id,
                             operator_id=user.id, remark=remark)
    db.add(order)
    db.flush()
    for item in items:
        mat_id = int(item["material_id"]); qty = float(item["quantity"]); price = float(item["unit_price"])
        db.add(RequisitionItem(order_id=order.id, material_id=mat_id,
                               quantity=qty, unit_price=price, total_amount=qty * price))
    write_log(db, user, "新建", "领料单", f"单号：{order_no}", request)
    db.commit()
    return JSONResponse({"success": True, "order_id": order.id, "order_no": order_no})

@router.post("/delete/{order_id}")
def delete_requisition(order_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_permission(request, db, PERM_DELETE)
    order = db.query(RequisitionOrder).filter(RequisitionOrder.id == order_id).first()
    if not order: raise HTTPException(404)
    write_log(db, user, "删除", "领料单", f"单号：{order.order_no}", request)
    db.delete(order)
    db.commit()
    return RedirectResponse("/requisition/ledger", status_code=302)

@router.get("/print/{order_id}")
def print_requisition(order_id: int, paper: str = "A4", request: Request = None, db: Session = Depends(get_db)):
    require_permission(request, db, PERM_PRINT)
    order = db.query(RequisitionOrder).filter(RequisitionOrder.id == order_id).first()
    if not order: raise HTTPException(404)
    paper_size = "A4" if paper == "A4" else "voucher"
    pdf_bytes = generate_requisition_pdf(order, paper_size)
    return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=requisition_{order.order_no}.pdf"})

@router.get("/ledger", response_class=HTMLResponse)
def ledger_page(request: Request, start_date: str = "", end_date: str = "", db: Session = Depends(get_db)):
    user = require_view(request, db)
    # Only query if date filters are provided
    rows = build_rows(query_orders(db, start_date, end_date)) if start_date or end_date else []
    today = datetime.now().strftime("%Y-%m-%d")
    return templates.TemplateResponse("requisition_ledger.html", page_context(
        request, db, user, rows=rows,
        start_date=start_date, end_date=end_date,
        today=today))

@router.get("/ledger/pdf")
def ledger_pdf(request: Request, start_date: str = "", end_date: str = "",
               db: Session = Depends(get_db)):
    require_permission(request, db, PERM_EXPORT)
    rows = build_rows(query_orders(db, start_date, end_date))
    pdf_bytes = generate_requisition_ledger_pdf(rows, start_date, end_date)
    return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=requisition_ledger.pdf"})

@router.get("/ledger/excel")
def ledger_excel(request: Request, start_date: str = "", end_date: str = "",
                 db: Session = Depends(get_db)):
    require_permission(request, db, PERM_EXPORT)
    rows = build_rows(query_orders(db, start_date, end_date))
    columns = ["单号","领料日期","物料名称","型号","件数","金额(元)","使用设备","领料人员","操作员"]
    data = [[r["order_no"],r["order_date"],r["material_name"],r["material_model"],
             r["quantity"],r["total_amount"],r["equipment"],r["personnel"],r["operator"]] for r in rows]
    excel_bytes = generate_ledger_excel("领料台账", columns, data, start_date, end_date)
    return StreamingResponse(iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=requisition_ledger.xlsx"})

@router.get("/api/material-price/{material_id}")
def get_material_price(material_id: int, request: Request, db: Session = Depends(get_db)):
    require_any(request, db, [PERM_CREATE, PERM_VIEW])
    purchases     = db.query(PurchaseItem).filter(PurchaseItem.material_id == material_id).all()
    requisitions  = db.query(RequisitionItem).filter(RequisitionItem.material_id == material_id).all()
    adjustments   = db.query(StockAdjustment).filter(StockAdjustment.material_id == material_id).all()
    total_qty = (sum(p.quantity for p in purchases)
                 - sum(r.quantity for r in requisitions)
                 + sum(a.quantity for a in adjustments))
    total_amt = (sum(p.total_amount for p in purchases)
                 - sum(r.total_amount for r in requisitions)
                 + sum(a.amount for a in adjustments))
    if total_qty > 0:
        avg_price = round(total_amt / total_qty, 4)
    else:
        last = db.query(PurchaseItem).filter(PurchaseItem.material_id == material_id).order_by(PurchaseItem.id.desc()).first()
        avg_price = round(last.unit_price, 4) if last else 0.0
    return {"material_id": material_id, "avg_price": avg_price, "stock_qty": round(total_qty, 4)}
