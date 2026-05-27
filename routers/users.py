from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from database import get_db
from models import User
from routers.auth import get_session_user
from utils.log_helper import write_log

router = APIRouter(prefix="/users", tags=["users"])
templates = Jinja2Templates(directory="templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def admin_only(request, db):
    user = get_session_user(request, db)
    if not user: raise HTTPException(302, headers={"Location": "/login"})
    if user.role != "管理员": raise HTTPException(403, detail="权限不足")
    return user

@router.get("", response_class=HTMLResponse)
def list_users(request: Request, db: Session = Depends(get_db)):
    user = admin_only(request, db)
    users = db.query(User).all()
    return templates.TemplateResponse("users.html", {"request": request, "users": users, "user": user})

@router.post("/create")
def create_user(request: Request, username: str = Form(...), password: str = Form(...),
                full_name: str = Form(...), role: str = Form(...), db: Session = Depends(get_db)):
    current = admin_only(request, db)
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(400, detail="用户名已存在")
    u = User(username=username, hashed_password=pwd_context.hash(password[:72]),
             full_name=full_name, role=role)
    db.add(u)
    write_log(db, current, "新建", "用户", f"用户名：{username} 角色：{role}", request)
    db.commit()
    return RedirectResponse("/users", status_code=302)

@router.post("/delete/{uid}")
def delete_user(uid: int, request: Request, db: Session = Depends(get_db)):
    current = admin_only(request, db)
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
    current = admin_only(request, db)
    u = db.query(User).filter(User.id == uid).first()
    if not u: raise HTTPException(404)
    u.hashed_password = pwd_context.hash(new_password[:72])
    write_log(db, current, "修改", "用户", f"重置密码：{u.username}", request)
    db.commit()
    return RedirectResponse("/users", status_code=302)
