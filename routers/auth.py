# Python 3.8 compatible
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from itsdangerous import URLSafeTimedSerializer, BadSignature
from database import get_db
from models import User, OperationLog
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "haicang-inventory-secret-2024"
serializer = URLSafeTimedSerializer(SECRET_KEY)


def get_session_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        data = serializer.loads(token, max_age=86400)
        return db.query(User).filter(User.id == data["user_id"]).first()
    except Exception:
        return None


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})


@router.post("/login")
def login(request: Request,
          username: str = Form(...),
          password: str = Form(...),
          db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not pwd_context.verify(password[:72], user.hashed_password):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "用户名或密码错误"}
        )
    # Write login log
    ip = ""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        ip = fwd.split(",")[0]
    elif hasattr(request.client, "host"):
        ip = request.client.host or ""
    log = OperationLog(
        user_id=user.id, username=user.username,
        action="登录", module="系统",
        detail="用户 {} 登录系统".format(user.full_name),
        ip=ip,
    )
    db.add(log)
    db.commit()

    token = serializer.dumps({"user_id": user.id})
    resp = RedirectResponse(url="/", status_code=302)
    resp.set_cookie("session", token, httponly=True, max_age=86400)
    return resp


@router.get("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie("session")
    return resp
