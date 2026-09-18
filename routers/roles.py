# Python 3.8 compatible
"""角色权限配置：角色 -> 权限（一对多）。

权限点清单在 utils/permissions.py 中以代码登记；本模块只维护"授予关系"。
"""
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from urllib.parse import quote

from database import get_db
from models import Role, RolePermission, User
from utils.log_helper import write_log
from utils.permissions import (ALL_PERMISSIONS, PERMISSION_GROUPS, SUPER_ROLE,
                               get_role_permissions, page_context,
                               require_permission)

router = APIRouter(prefix="/roles", tags=["roles"])
templates = Jinja2Templates(directory="templates")


def require_manage(request, db):
    return require_permission(request, db, "role.manage")


def _user_counts(db, roles):
    counts = {}
    for role in roles:
        counts[role.name] = db.query(User).filter(User.role == role.name).count()
    return counts


def _back(role_id=0, msg="", ok=1):
    """带提示信息跳回权限配置页（错误用页面提示而不是 JSON 报错）。"""
    url = "/roles"
    if role_id:
        url += "?role_id={}".format(role_id)
    if msg:
        url += ("&" if "?" in url else "?") + "ok={}&msg={}".format(ok, quote(msg))
    return RedirectResponse(url, status_code=302)


@router.get("", response_class=HTMLResponse)
def roles_page(request: Request, role_id: int = 0, msg: str = "", ok: int = 1,
               db: Session = Depends(get_db)):
    user = require_manage(request, db)
    roles = db.query(Role).order_by(Role.id).all()
    current = None
    if role_id:
        current = db.query(Role).filter(Role.id == role_id).first()
    if not current and roles:
        current = roles[0]
    selected = get_role_permissions(db, current.name) if current else set()
    return templates.TemplateResponse("roles.html", page_context(
        request, db, user,
        roles=roles,
        counts=_user_counts(db, roles),
        current=current,
        selected=selected,
        groups=PERMISSION_GROUPS,
        total_permissions=len(ALL_PERMISSIONS),
        super_role=SUPER_ROLE,
        msg=msg,
        ok=ok))


@router.post("/create")
def create_role(request: Request, name: str = Form(...), description: str = Form(""),
                db: Session = Depends(get_db)):
    user = require_manage(request, db)
    name = (name or "").strip()
    if not name:
        return _back(0, "角色名称不能为空", 0)
    if db.query(Role).filter(Role.name == name).first():
        return _back(0, "角色名称已存在：{}".format(name), 0)
    role = Role(name=name, description=(description or "").strip(), is_system=False)
    db.add(role)
    db.flush()
    write_log(db, user, "新建", "权限", "新建角色：{}".format(name), request)
    db.commit()
    return _back(role.id, "角色「{}」已创建，请在右侧勾选权限后保存".format(name), 1)


@router.post("/update/{role_id}")
def update_role(role_id: int, request: Request, name: str = Form(...),
                description: str = Form(""), db: Session = Depends(get_db)):
    user = require_manage(request, db)
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(404)
    if role.is_system:
        return _back(role.id, "系统内置角色不可修改", 0)
    name = (name or "").strip()
    if not name:
        return _back(role.id, "角色名称不能为空", 0)
    if db.query(Role).filter(Role.name == name, Role.id != role_id).first():
        return _back(role.id, "角色名称已存在：{}".format(name), 0)
    old_name = role.name
    role.name = name
    role.description = (description or "").strip()
    if old_name != name:
        # 角色改名：同步使用该角色的用户，避免用户失效
        db.query(User).filter(User.role == old_name).update({"role": name})
    write_log(db, user, "修改", "权限",
              "角色：{} → {}，描述：{}".format(old_name, name, role.description), request)
    db.commit()
    return _back(role.id, "角色信息已保存", 1)


@router.post("/save/{role_id}")
async def save_permissions(role_id: int, request: Request, db: Session = Depends(get_db)):
    """保存某角色的权限（先删后插，一个角色对应多条权限记录）。"""
    user = require_manage(request, db)
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(404)
    if role.is_system:
        return _back(role.id, "系统内置角色始终拥有全部权限，不可修改", 0)

    form = await request.form()
    codes = []
    seen = set()
    for code in form.getlist("perm"):
        if code in ALL_PERMISSIONS and code not in seen:
            seen.add(code)
            codes.append(code)

    db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()
    for code in codes:
        db.add(RolePermission(role_id=role.id, permission=code))
    write_log(db, user, "修改", "权限",
              "角色：{}，授予权限数：{}".format(role.name, len(codes)), request)
    db.commit()
    return _back(role.id, "角色「{}」的权限已保存（{} 项）".format(role.name, len(codes)), 1)


@router.post("/delete/{role_id}")
def delete_role(role_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_manage(request, db)
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(404)
    if role.is_system:
        return _back(role.id, "系统内置角色不可删除", 0)
    used = db.query(User).filter(User.role == role.name).count()
    if used:
        return _back(role.id, "该角色下还有 {} 个用户，请先在用户管理中调整角色".format(used), 0)
    role_name = role.name
    db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()
    write_log(db, user, "删除", "权限", "删除角色：{}".format(role_name), request)
    db.delete(role)
    db.commit()
    return _back(0, "角色「{}」已删除".format(role_name), 1)
