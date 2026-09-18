# Python 3.8 compatible - no dateutil dependency
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from database import get_db
from models import RequisitionOrder, PurchaseOrder, PurchaseItem, RequisitionItem, StockAdjustment, Material
from utils.pdf_generator import generate_report_pdf
from utils.excel_generator import generate_report_excel
from utils.permissions import page_context, require_any, require_permission

router = APIRouter(prefix="/reports", tags=["reports"])
templates = Jinja2Templates(directory="templates")

# 权限点见 utils/permissions.py，可在「权限配置」页面按角色勾选
PERM_VIEW   = "reports.view"
PERM_EXPORT = "reports.export"


def _require_view(request, db):
    return require_permission(request, db, PERM_VIEW)


def build_equipment_report(db, start_date, end_date):
    query = db.query(RequisitionOrder)
    if start_date:
        query = query.filter(
            RequisitionOrder.order_date >= datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        query = query.filter(
            RequisitionOrder.order_date < datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1))
    orders = query.all()
    stats = {}
    for o in orders:
        eq = o.equipment
        if not eq:
            continue
        if eq.id not in stats:
            stats[eq.id] = {
                "equipment_name": eq.name,
                "equipment_code": eq.code,
                "department": eq.department or "",
                "total_qty": 0,
                "total_amt": 0,
            }
        for item in o.items:
            stats[eq.id]["total_qty"] += item.quantity
            stats[eq.id]["total_amt"] += item.total_amount
    rows = list(stats.values())
    for r in rows:
        r["total_amt"] = round(r["total_amt"], 2)
    rows.sort(key=lambda x: x["total_amt"], reverse=True)
    return rows


def build_personnel_report(db, start_date, end_date):
    query = db.query(RequisitionOrder)
    if start_date:
        query = query.filter(
            RequisitionOrder.order_date >= datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        query = query.filter(
            RequisitionOrder.order_date < datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1))
    orders = query.all()
    stats = {}
    for o in orders:
        p = o.personnel
        if not p:
            continue
        if p.id not in stats:
            stats[p.id] = {
                "name": p.name,
                "employee_id": p.employee_id,
                "team": p.team or "",
                "total_qty": 0,
                "total_amt": 0,
            }
        for item in o.items:
            stats[p.id]["total_qty"] += item.quantity
            stats[p.id]["total_amt"] += item.total_amount
    rows = list(stats.values())
    for r in rows:
        r["total_amt"] = round(r["total_amt"], 2)
    rows.sort(key=lambda x: x["total_amt"], reverse=True)
    return rows


@router.get("", response_class=HTMLResponse)
def reports_page(request: Request,
                 report_type: str = "equipment",
                 start_date: str = "",
                 end_date: str = "",
                 db: Session = Depends(get_db)):
    user = _require_view(request, db)
    equipment_rows = build_equipment_report(db, start_date, end_date)
    personnel_rows = build_personnel_report(db, start_date, end_date)
    return templates.TemplateResponse("reports.html", page_context(
        request, db, user,
        report_type=report_type,
        equipment_rows=equipment_rows,
        personnel_rows=personnel_rows,
        start_date=start_date,
        end_date=end_date))


@router.get("/pdf")
def reports_pdf(request: Request,
                report_type: str = "equipment",
                start_date: str = "",
                end_date: str = "",
                db: Session = Depends(get_db)):
    require_permission(request, db, PERM_EXPORT)
    if report_type == "equipment":
        rows = build_equipment_report(db, start_date, end_date)
        columns = ["设备名称", "设备编码", "所在部门", "总领料件数", "总领料金额(元)"]
        data = [[r["equipment_name"], r["equipment_code"], r["department"],
                 r["total_qty"], r["total_amt"]] for r in rows]
        title = "按设备统计领料报表"
    else:
        rows = build_personnel_report(db, start_date, end_date)
        columns = ["姓名", "工号", "班组", "总领料件数", "总领料金额(元)"]
        data = [[r["name"], r["employee_id"], r["team"],
                 r["total_qty"], r["total_amt"]] for r in rows]
        title = "按人员统计领料报表"
    pdf_bytes = generate_report_pdf(title, columns, data, start_date, end_date)
    return StreamingResponse(
        iter([pdf_bytes]), media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=report_{}.pdf".format(report_type)}
    )


@router.get("/excel")
def reports_excel(request: Request,
                  report_type: str = "equipment",
                  start_date: str = "",
                  end_date: str = "",
                  db: Session = Depends(get_db)):
    require_permission(request, db, PERM_EXPORT)
    if report_type == "equipment":
        rows = build_equipment_report(db, start_date, end_date)
        columns = ["设备名称", "设备编码", "所在部门", "总领料件数", "总领料金额(元)"]
        data = [[r["equipment_name"], r["equipment_code"], r["department"],
                 r["total_qty"], r["total_amt"]] for r in rows]
        title = "按设备统计领料报表"
    else:
        rows = build_personnel_report(db, start_date, end_date)
        columns = ["姓名", "工号", "班组", "总领料件数", "总领料金额(元)"]
        data = [[r["name"], r["employee_id"], r["team"],
                 r["total_qty"], r["total_amt"]] for r in rows]
        title = "按人员统计领料报表"
    excel_bytes = generate_report_excel(title, columns, data, start_date, end_date)
    return StreamingResponse(
        iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=report_{}.xlsx".format(report_type)}
    )


def _add_months(dt, months):
    """Pure stdlib: add months to a datetime (no dateutil)."""
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    import calendar
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


@router.get("/api/dashboard")
def dashboard_data(request: Request, db: Session = Depends(get_db)):
    # 仪表盘取数：报表查看权限或仪表盘权限均可
    require_any(request, db, [PERM_VIEW, "dashboard.view"])
    from routers.warehouse import get_stock_data
    # Purchase trend last 6 months - pure stdlib
    purchase_trend = []
    now = datetime.now()
    for i in range(5, -1, -1):
        ref = _add_months(now.replace(day=1), -i)
        month_end = _add_months(ref, 1)
        orders = db.query(PurchaseOrder).filter(
            PurchaseOrder.order_date >= ref,
            PurchaseOrder.order_date < month_end,
        ).all()
        total = sum(
            sum(it.total_amount for it in o.items) for o in orders
        )
        purchase_trend.append({
            "month": ref.strftime("%Y-%m"),
            "amount": round(total, 2),
        })

    eq_stats = build_equipment_report(db, "", "")[:10]
    p_stats = build_personnel_report(db, "", "")[:10]
    stock_rows = get_stock_data(db)
    low_stock_count = sum(1 for r in stock_rows if r["low_stock"])

    return {
        "purchase_trend": purchase_trend,
        "equipment_stats": eq_stats,
        "personnel_stats": p_stats,
        "total_materials": len(stock_rows),
        "low_stock_count": low_stock_count,
    }
