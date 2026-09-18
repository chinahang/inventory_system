from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from database import get_db
from models import User, Role
from utils.log_helper import write_log
from utils.permissions import page_context, require_permission

router = APIRouter(prefix="/users", tags=["users"])
templates = Jinja2Templates(directory="templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def require_manage(request, db):
    return require_permission(request, db, "user.manage")

@router.get("", response_class=HTMLResponse)
def list_users(request: Request, db: Session = Depends(get_db)):
    user = require_permission(request, db, "user.view")
    users = db.query(User).all()
    roles = db.query(Role).order_by(Role.id).all()
    return templates.TemplateResponse("users.html", page_context(
        request, db, user, users=users, roles=roles))

@router.post("/create")
def create_user(request: Request, username: str = Form(...), password: str = Form(...),
                full_name: str = Form(...), role: str = Form(...), db: Session = Depends(get_db)):
    current = require_manage(request, db)
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(400, detail="用户名已存在")
    if not db.query(Role).filter(Role.name == role).first():
        raise HTTPException(400, detail="角色不存在，请先在「权限配置」中创建")
    u = User(username=username, hashed_password=pwd_context.hash(password[:72]),
             full_name=full_name, role=role)
    db.add(u)
    write_log(db, current, "新建", "用户", f"用户名：{username} 角色：{role}", request)
    db.commit()
    return RedirectResponse("/users", status_code=302)

@router.post("/delete/{uid}")
def delete_user(uid: int, request: Request, db: Session = Depends(get_db)):
    current = require_manage(request, db)
    if current.id == uid:
        raise HTTPException(400, detail="不能删除当前登录用户")
    u = db.query(User).filter(User.id == uid).first()
    if not u: raise HTTPException(404)
    write_log(db, current, "删除", "用户", f"用户名：{u.username} 角色：{u.role}", request)
    db.delete(u)
    db.commit()
    return RedirectResponse("/users", status_code=302)

@router.post("/reset-password/{uid}")
def reset_password(uid: int, request: Request, new_password: str = Form(...), db: Session = Depends(get_db)):
    current = require_manage(request, db)
    u = db.query(User).filter(User.id == uid).first()
    if not u: raise HTTPException(404)
    u.hashed_password = pwd_context.hash(new_password[:72])
    write_log(db, current, "修改", "用户", f"重置密码：{u.username}", request)
    db.commit()
    return RedirectResponse("/users", status_code=302)

@router.post("/change-role/{uid}")
def change_role(uid: int, request: Request, role: str = Form(...), db: Session = Depends(get_db)):
    """调整用户角色（权限随角色走）。"""
    current = require_manage(request, db)
    u = db.query(User).filter(User.id == uid).first()
    if not u: raise HTTPException(404)
    if not db.query(Role).filter(Role.name == role).first():
        raise HTTPException(400, detail="角色不存在，请先在「权限配置」中创建")
    old_role = u.role
    u.role = role
    write_log(db, current, "修改", "用户", f"用户：{u.username} 角色：{old_role} → {role}", request)
    db.commit()
    return RedirectResponse("/users", status_code=302)
