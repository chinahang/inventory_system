from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db
from models import Material, PurchaseItem, RequisitionItem, StockAdjustment
from routers.auth import get_session_user
from utils.pdf_generator import generate_stock_report_pdf
from utils.excel_generator import generate_stock_excel
from utils.log_helper import write_log

router = APIRouter(prefix="/warehouse", tags=["warehouse"])
templates = Jinja2Templates(directory="templates")

VIEW_ROLES   = ["管理员", "仓管员", "采购员", "普通操作员"]
ADJUST_ROLES = ["管理员", "仓管员"]

def get_stock_data(db):
    rows = []
    for mat in db.query(Material).all():
        purchases    = db.query(PurchaseItem).filter(PurchaseItem.material_id == mat.id).all()
        requisitions = db.query(RequisitionItem).filter(RequisitionItem.material_id == mat.id).all()
        adjustments  = db.query(StockAdjustment).filter(StockAdjustment.material_id == mat.id).all()
        tpq = sum(p.quantity for p in purchases);   tpa = sum(p.total_amount for p in purchases)
        trq = sum(r.quantity for r in requisitions); tra = sum(r.total_amount for r in requisitions)
        taq = sum(a.quantity for a in adjustments);  taa = sum(a.amount for a in adjustments)
        avail_qty = tpq - trq + taq; avail_amt = tpa - tra + taa
        rows.append({
            "id": mat.id, "code": mat.code, "name": mat.name,
            "model": mat.model or "", "unit": mat.unit or "",
            "safety_stock": mat.safety_stock,
            "purchase_qty": tpq,  "purchase_amt": round(tpa, 2),
            "req_qty": trq,       "req_amt": round(tra, 2),
            "adj_qty": taq,       "adj_amt": round(taa, 2),
            "avail_qty": round(avail_qty, 2), "avail_amt": round(avail_amt, 2),
            "low_stock": avail_qty < mat.safety_stock,
        })
    return rows

@router.get("", response_class=HTMLResponse)
def warehouse_page(request: Request, db: Session = Depends(get_db)):
    user = get_session_user(request, db)
    if not user: return RedirectResponse("/login")
    if user.role not in VIEW_ROLES: return RedirectResponse("/")
    rows = get_stock_data(db)
    adjustments = db.query(StockAdjustment).order_by(StockAdjustment.created_at.desc()).limit(50).all()
    return templates.TemplateResponse("warehouse.html", {
        "request": request, "user": user, "rows": rows, "adjustments": adjustments,
        "now": datetime.now().strftime("%Y-%m-%d %H:%M")
    })

@router.post("/adjust")
def adjust_stock(request: Request, material_id: int = Form(...), quantity: float = Form(...),
                 amount: float = Form(...), reason: str = Form(...), db: Session = Depends(get_db)):
    user = get_session_user(request, db)
    if not user: raise HTTPException(302, headers={"Location": "/login"})
    if user.role not in ADJUST_ROLES: raise HTTPException(403, detail="权限不足")
    mat = db.query(Material).filter(Material.id == material_id).first()
    adj = StockAdjustment(material_id=material_id, quantity=quantity, amount=amount,
                          reason=reason, operator_id=user.id)
    db.add(adj)
    write_log(db, user, "库存调整", "库存",
              f"物料：{mat.name if mat else material_id}，数量：{quantity:+g}，原因：{reason}", request)
    db.commit()
    return RedirectResponse("/warehouse", status_code=302)

@router.get("/report/pdf")
def stock_pdf(request: Request, db: Session = Depends(get_db)):
    user = get_session_user(request, db)
    rows = get_stock_data(db)
    pdf_bytes = generate_stock_report_pdf(rows, user.full_name if user else "")
    return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=stock_report.pdf"})

@router.get("/report/excel")
def stock_excel(request: Request, db: Session = Depends(get_db)):
    user = get_session_user(request, db)
    rows = get_stock_data(db)
    excel_bytes = generate_stock_excel(rows, user.full_name if user else "")
    return StreamingResponse(iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=stock_report.xlsx"})
