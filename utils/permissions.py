# Python 3.8 compatible - no walrus operator, no PEP 604 union types
"""集中式权限定义与校验。

设计说明：
- 权限点清单以本文件为准（新增功能时必须在此登记），数据库只保存
  "角色 -> 权限" 的授予关系：roles 一个角色对应 role_permissions 多条记录（一对多）。
- 角色名沿用中文字符串（users.role == roles.name），不改动 users 表结构。
- "管理员" 为系统内置超级角色：始终拥有全部权限，且不可在页面上被修改（防止自锁）。
"""

SUPER_ROLE = "管理员"

# 权限清单：按模块分组，权限配置页按此渲染勾选矩阵
PERMISSION_GROUPS = [
    ("仪表盘", [
        ("dashboard.view", "查看首页仪表盘"),
    ]),
    ("采购管理", [
        ("purchase.view", "查看采购台账"),
        ("purchase.create", "新建采购单"),
        ("purchase.delete", "删除采购单"),
        ("purchase.export", "导出采购台账(PDF/Excel)"),
    ]),
    ("领料管理", [
        ("requisition.view", "查看领料台账"),
        ("requisition.create", "新建领料单"),
        ("requisition.delete", "删除领料单"),
        ("requisition.print", "打印领料单"),
        ("requisition.export", "导出领料台账(PDF/Excel)"),
    ]),
    ("库存管理", [
        ("warehouse.view", "查看库存"),
        ("warehouse.adjust", "库存调整(盘盈盘亏)"),
        ("warehouse.export", "导出库存报表(PDF/Excel)"),
    ]),
    ("统计报表", [
        ("reports.view", "查看统计报表"),
        ("reports.export", "导出统计报表(PDF/Excel)"),
    ]),
    ("基础数据", [
        ("material.view", "查看物料"),
        ("material.manage", "维护物料(新增/修改/删除)"),
        ("personnel.view", "查看人员"),
        ("personnel.manage", "维护人员(新增/修改/删除)"),
        ("equipment.view", "查看设备"),
        ("equipment.manage", "维护设备(新增/修改/删除)"),
    ]),
    ("系统管理", [
        ("user.view", "查看用户"),
        ("user.manage", "维护用户(新增/删除/重置密码)"),
        ("role.manage", "配置角色权限"),
        ("log.view", "查看操作日志"),
        ("backup.view", "查看备份"),
        ("backup.manage", "备份/还原/删除备份"),
    ]),
]

ALL_PERMISSIONS = [code for _module, _items in PERMISSION_GROUPS for code, _name in _items]
PERMISSION_NAMES = dict((code, name) for _module, _items in PERMISSION_GROUPS
                        for code, name in _items)

# 内置角色默认权限（仅在角色首次创建时写入；之后以权限配置页为准）
# 管理员为超级角色，无需存储权限行；其余角色默认值与改造前的硬编码行为一致。
DEFAULT_ROLE_PERMISSIONS = {
    SUPER_ROLE: None,
    "采购员": [
        "dashboard.view",
        "purchase.view", "purchase.create", "purchase.export",
        "requisition.view", "requisition.print", "requisition.export",
        "warehouse.view", "warehouse.export",
        "reports.view", "reports.export",
    ],
    "仓管员": [
        "dashboard.view",
        "purchase.view", "purchase.export",
        "requisition.view", "requisition.create", "requisition.print", "requisition.export",
        "warehouse.view", "warehouse.adjust", "warehouse.export",
        "reports.view", "reports.export",
    ],
    "普通操作员": [
        "dashboard.view",
        "purchase.view", "purchase.export",
        "requisition.view", "requisition.print", "requisition.export",
        "warehouse.view", "warehouse.export",
        "reports.view", "reports.export",
    ],
}

DEFAULT_ROLE_DESCRIPTIONS = {
    SUPER_ROLE: "系统内置角色，始终拥有全部权限，不可修改",
    "采购员": "采购单录入与采购台账",
    "仓管员": "领料单录入、库存调整",
    "普通操作员": "台账、库存与报表只读查询",
}

# 缺少 dashboard.view 时的兜底跳转顺序
PAGE_PERMISSIONS = [
    ("dashboard.view", "/"),
    ("purchase.create", "/purchase"),
    ("purchase.view", "/purchase/ledger"),
    ("requisition.create", "/requisition"),
    ("requisition.view", "/requisition/ledger"),
    ("warehouse.view", "/warehouse"),
    ("reports.view", "/reports"),
    ("material.view", "/materials"),
    ("personnel.view", "/personnel"),
    ("equipment.view", "/equipment"),
    ("user.view", "/users"),
    ("log.view", "/logs"),
    ("backup.view", "/backup"),
    ("role.manage", "/roles"),
]


def is_super_role(role_name):
    return role_name == SUPER_ROLE


def get_role_permissions(db, role_name):
    """取某个角色被授予的权限点集合。超级角色直接返回全集。"""
    if not role_name:
        return set()
    if is_super_role(role_name):
        return set(ALL_PERMISSIONS)
    from models import Role, RolePermission
    rows = (db.query(RolePermission.permission)
            .join(Role, Role.id == RolePermission.role_id)
            .filter(Role.name == role_name).all())
    return set(r[0] for r in rows)


def get_user_permissions(db, user):
    if not user:
        return set()
    return get_role_permissions(db, user.role)


def has_permission(db, user, code):
    return code in get_user_permissions(db, user)


def first_accessible_path(perms):
    for code, path in PAGE_PERMISSIONS:
        if code in perms:
            return path
    return ""


def require_login(request, db):
    from routers.auth import get_session_user
    user = get_session_user(request, db)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user


def require_permission(request, db, code):
    from fastapi import HTTPException
    user = require_login(request, db)
    if code not in get_user_permissions(db, user):
        raise HTTPException(status_code=403, detail="权限不足")
    return user


def require_any(request, db, codes):
    from fastapi import HTTPException
    user = require_login(request, db)
    perms = get_user_permissions(db, user)
    for code in codes:
        if code in perms:
            return user
    raise HTTPException(status_code=403, detail="权限不足")


def page_context(request, db, user, **extra):
    """统一的模板上下文：注入 request / user / permissions，避免每个页面各写一遍。"""
    ctx = {
        "request": request,
        "user": user,
        "permissions": get_user_permissions(db, user) if user else set(),
    }
    ctx.update(extra)
    return ctx
