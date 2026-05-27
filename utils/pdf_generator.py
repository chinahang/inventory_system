# Python 3.8 compatible - robust Windows 7 Chinese font detection
import io
import os
from datetime import datetime

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

COMPANY_NAME = "台州海昌物流有限公司"

# Windows 7 Chinese font candidates (in priority order)
_WIN7_FONTS = [
    r"C:\Windows\Fonts\msyh.ttc",       # 微软雅黑
    r"C:\Windows\Fonts\simsun.ttc",     # 宋体
    r"C:\Windows\Fonts\simhei.ttf",     # 黑体
    r"C:\Windows\Fonts\simkai.ttf",     # 楷体
    r"C:\Windows\Fonts\simfang.ttf",    # 仿宋
    r"C:\Windows\Fonts\MSYH.TTF",
    r"C:\Windows\Fonts\SIMSUN.TTC",
]
_LINUX_FONTS = [
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]

_FONT_NAME = "Helvetica"  # fallback


def _register_font():
    global _FONT_NAME
    candidates = _WIN7_FONTS + _LINUX_FONTS
    for path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("ChineseFont", path))
                _FONT_NAME = "ChineseFont"
                return
            except Exception:
                continue


_register_font()


def _style(size=9, align=TA_CENTER, bold=False):
    return ParagraphStyle(
        "s",
        fontName=_FONT_NAME,
        fontSize=size,
        alignment=align,
        leading=size + 4,
        wordWrap="CJK",
    )


def _table_style(header_color=None):
    if header_color is None:
        header_color = colors.HexColor("#1a56db")
    return TableStyle([
        ("FONTNAME",    (0, 0), (-1, -1), _FONT_NAME),
        ("FONTSIZE",    (0, 0), (-1,  0), 9),
        ("FONTSIZE",    (0, 1), (-1, -1), 8),
        ("BACKGROUND",  (0, 0), (-1,  0), header_color),
        ("TEXTCOLOR",   (0, 0), (-1,  0), colors.white),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])


def generate_purchase_ledger_pdf(rows, start_date, end_date):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                             leftMargin=1.5*cm, rightMargin=1.5*cm,
                             topMargin=1.5*cm, bottomMargin=1.5*cm)
    ts = _style(16, TA_CENTER)
    ss = _style(10, TA_CENTER)
    rs = _style(9,  TA_RIGHT)
    elems = [
        Paragraph(COMPANY_NAME, ts),
        Paragraph("采购台账", ts),
        Paragraph("查询期间：{} 至 {}".format(start_date or "全部", end_date or "全部"), ss),
        Spacer(1, 0.3*cm),
    ]
    headers = ["单号", "采购日期", "物料名称", "型号", "件数", "单价(元)",
               "总金额(元)", "采购员", "操作员", "供应商联系", "备注"]
    data = [headers]
    tqty = 0
    tamt = 0.0
    for r in rows:
        data.append([
            r["order_no"], r["order_date"], r["material_name"],
            r.get("material_model", ""),
            r["quantity"], "{:.2f}".format(r["unit_price"]),
            "{:.2f}".format(r["total_amount"]),
            r["purchaser"], r["operator"],
            r.get("supplier_contact", ""), r.get("remark", ""),
        ])
        tqty += r["quantity"]
        tamt += r["total_amount"]
    data.append(["合计", "", "", "", tqty, "", "{:.2f}".format(tamt),
                 "", "", "", ""])
    cw = [3*cm,2.2*cm,2.8*cm,2.2*cm,1.5*cm,2*cm,2.2*cm,1.8*cm,1.8*cm,2.5*cm,2.5*cm]
    t = Table(data, colWidths=cw, repeatRows=1)
    st = _table_style()
    st.add("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e8f0fe"))
    t.setStyle(st)
    elems.append(t)
    elems.append(Spacer(1, 0.4*cm))
    elems.append(Paragraph("打印时间：{}".format(datetime.now().strftime("%Y-%m-%d %H:%M")), rs))
    doc.build(elems)
    return buf.getvalue()


def generate_requisition_pdf(order, paper="A4"):
    buf = io.BytesIO()
    if paper == "A4":
        pagesize = A4
        w = A4[0]
    else:
        w = 13.97 * cm
        h = 24.1  * cm
        pagesize = (w, h)
    doc = SimpleDocTemplate(buf, pagesize=pagesize,
                             leftMargin=1.5*cm, rightMargin=1.5*cm,
                             topMargin=1.5*cm, bottomMargin=2*cm)
    ts = _style(15, TA_CENTER)
    ns = _style(9,  TA_CENTER)
    elems = [
        Paragraph(COMPANY_NAME, ts),
        Paragraph("领  料  单", ts),
        Spacer(1, 0.3*cm),
    ]
    eq_name  = order.equipment.name if order.equipment else ""
    eq_dept  = order.equipment.department if order.equipment else ""
    p_name   = order.personnel.name if order.personnel else ""
    op_name  = order.operator.full_name if order.operator else ""
    info = [
        ["单据编号：{}".format(order.order_no),
         "领料日期：{}".format(order.order_date.strftime("%Y-%m-%d"))],
        ["使用设备：{}".format(eq_name),  "领料人员：{}".format(p_name)],
        ["所属部门：{}".format(eq_dept),  "操 作 员：{}".format(op_name)],
    ]
    half = (w - 3*cm) / 2
    it = Table(info, colWidths=[half, half])
    it.setStyle(TableStyle([
        ("FONTNAME",  (0,0),(-1,-1), _FONT_NAME),
        ("FONTSIZE",  (0,0),(-1,-1), 9),
        ("TOPPADDING",(0,0),(-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1), 3),
    ]))
    elems.append(it)
    elems.append(Spacer(1, 0.3*cm))

    headers = ["序号", "物料名称", "型号", "规格", "单位", "数量", "单价(元)", "金额(元)"]
    data = [headers]
    total = 0.0
    for i, item in enumerate(order.items, 1):
        mat = item.material
        data.append([
            str(i),
            mat.name  if mat else "",
            mat.model if mat else "",
            mat.spec  if mat else "",
            mat.unit  if mat else "",
            item.quantity,
            "{:.2f}".format(item.unit_price),
            "{:.2f}".format(item.total_amount),
        ])
        total += item.total_amount
    while len(data) < 8:
        data.append([""] * 8)
    data.append(["合计", "", "", "", "", "", "", "{:.2f}".format(total)])

    avail_w = w - 3*cm
    cw = [0.8*cm, avail_w*0.22, avail_w*0.17, avail_w*0.14,
          avail_w*0.10, avail_w*0.10, avail_w*0.13, avail_w*0.14]
    t = Table(data, colWidths=cw, repeatRows=1)
    t.setStyle(_table_style())
    elems.append(t)
    elems.append(Spacer(1, 0.8*cm))

    sig = Table([["制单人：___________",
                  "经办人：___________",
                  "审核人：___________",
                  "财务确认：___________"]])
    sig.setStyle(TableStyle([
        ("FONTNAME", (0,0),(-1,-1), _FONT_NAME),
        ("FONTSIZE", (0,0),(-1,-1), 9),
        ("ALIGN",    (0,0),(-1,-1), "CENTER"),
    ]))
    elems.append(sig)
    if order.remark:
        elems.append(Spacer(1, 0.3*cm))
        elems.append(Paragraph("备注：{}".format(order.remark), ns))
    doc.build(elems)
    return buf.getvalue()


def generate_requisition_ledger_pdf(rows, start_date, end_date):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                             leftMargin=1.5*cm, rightMargin=1.5*cm,
                             topMargin=1.5*cm, bottomMargin=1.5*cm)
    ts = _style(16, TA_CENTER)
    ss = _style(10, TA_CENTER)
    rs = _style(9,  TA_RIGHT)
    elems = [
        Paragraph(COMPANY_NAME, ts),
        Paragraph("领料台账", ts),
        Paragraph("查询期间：{} 至 {}".format(start_date or "全部", end_date or "全部"), ss),
        Spacer(1, 0.3*cm),
    ]
    headers = ["单号","领料日期","物料名称","型号","件数","金额(元)","使用设备","领料人员","操作员"]
    data = [headers]
    tqty = 0
    tamt = 0.0
    for r in rows:
        data.append([
            r["order_no"], r["order_date"], r["material_name"],
            r.get("material_model",""),
            r["quantity"], "{:.2f}".format(r["total_amount"]),
            r["equipment"], r["personnel"], r["operator"],
        ])
        tqty += r["quantity"]
        tamt += r["total_amount"]
    data.append(["合计","","","",tqty,"{:.2f}".format(tamt),"","",""])
    cw = [3.2*cm,2.2*cm,3*cm,2.2*cm,1.5*cm,2.2*cm,2.5*cm,2*cm,2*cm]
    t = Table(data, colWidths=cw, repeatRows=1)
    st = _table_style()
    st.add("BACKGROUND", (0,-1),(-1,-1), colors.HexColor("#e8f0fe"))
    t.setStyle(st)
    elems.append(t)
    elems.append(Spacer(1, 0.4*cm))
    elems.append(Paragraph("打印时间：{}".format(datetime.now().strftime("%Y-%m-%d %H:%M")), rs))
    doc.build(elems)
    return buf.getvalue()


def generate_stock_report_pdf(rows, operator_name):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                             leftMargin=1.5*cm, rightMargin=1.5*cm,
                             topMargin=1.5*cm, bottomMargin=1.5*cm)
    ts = _style(16, TA_CENTER)
    rs = _style(9,  TA_RIGHT)
    elems = [
        Paragraph(COMPANY_NAME, ts),
        Paragraph("库存报表", ts),
        Spacer(1, 0.3*cm),
    ]
    headers = ["物料编码","品名","型号","单位",
               "累计采购件数","累计采购金额",
               "累计领料件数","累计领料金额",
               "可用件数","可用金额"]
    data = [headers]
    for r in rows:
        data.append([
            r["code"], r["name"], r["model"], r["unit"],
            r["purchase_qty"], "{:.2f}".format(r["purchase_amt"]),
            r["req_qty"],      "{:.2f}".format(r["req_amt"]),
            r["avail_qty"],    "{:.2f}".format(r["avail_amt"]),
        ])
    cw = [2.5*cm,3*cm,2.5*cm,1.5*cm,
          2.5*cm,2.5*cm,2.5*cm,2.5*cm,2*cm,2*cm]
    t = Table(data, colWidths=cw, repeatRows=1)
    st = _table_style()
    for i, r in enumerate(rows, 1):
        if r["low_stock"]:
            st.add("BACKGROUND", (0,i),(-1,i), colors.HexColor("#fde8e8"))
    t.setStyle(st)
    elems.append(t)
    elems.append(Spacer(1, 0.4*cm))
    elems.append(Paragraph(
        "查询时间：{}　　操作员：{}".format(
            datetime.now().strftime("%Y-%m-%d %H:%M"), operator_name),
        rs))
    doc.build(elems)
    return buf.getvalue()


def generate_report_pdf(title, columns, data, start_date, end_date):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=1.5*cm, rightMargin=1.5*cm,
                             topMargin=1.5*cm, bottomMargin=1.5*cm)
    ts = _style(16, TA_CENTER)
    ss = _style(10, TA_CENTER)
    rs = _style(9,  TA_RIGHT)
    elems = [
        Paragraph(COMPANY_NAME, ts),
        Paragraph(title, ts),
        Paragraph("统计期间：{} 至 {}".format(start_date or "全部", end_date or "全部"), ss),
        Spacer(1, 0.3*cm),
    ]
    tdata = [columns] + [[str(v) for v in row] for row in data]
    cw_each = (A4[0] - 3*cm) / len(columns)
    t = Table(tdata, colWidths=[cw_each]*len(columns), repeatRows=1)
    t.setStyle(_table_style())
    elems.append(t)
    elems.append(Spacer(1, 0.4*cm))
    elems.append(Paragraph(
        "打印时间：{}".format(datetime.now().strftime("%Y-%m-%d %H:%M")), rs))
    doc.build(elems)
    return buf.getvalue()
