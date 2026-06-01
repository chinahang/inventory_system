# Python 3.8 compatible
from fastapi import APIRouter, Depends, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import User
from routers.auth import get_session_user
from utils.backup import (
    perform_backup, perform_restore, list_backups, delete_backup,
    get_job_status, should_warn_retention
)
from utils.log_helper import write_log
import uuid

router = APIRouter(prefix="/backup", tags=["backup"])
templates = Jinja2Templates(directory="templates")

DATABASE_PATH = "./inventory.db"


def admin_only(request: Request, db: Session = Depends(get_db)):
    """Require admin role."""
    user = get_session_user(request, db)
    if not user or user.role != "管理员":
        return None
    return user


@router.get("", response_class=HTMLResponse)
def backup_page(request: Request, db: Session = Depends(get_db)):
    """Backup management page (admin only)."""
    user = admin_only(request, db)
    if not user:
        return JSONResponse({"error": "需要管理员权限"}, status_code=403)
    
    backups = list_backups()
    warn = should_warn_retention()
    
    return templates.TemplateResponse("backup.html", {
        "request": request,
        "user": user,
        "backups": backups,
        "warn_retention": warn,
        "max_backups": 7
    })


@router.post("/start")
def start_backup(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Start backup job."""
    user = admin_only(request, db)
    if not user:
        return JSONResponse({"error": "需要管理员权限"}, status_code=403)
    
    job_id = str(uuid.uuid4())
    
    # Run backup in background
    background_tasks.add_task(perform_backup, DATABASE_PATH, job_id)
    
    # Log action
    write_log(db, user, "创建备份", "备份管理", "开始备份任务", request)
    
    return JSONResponse({"success": True, "job_id": job_id})


@router.get("/status/{job_id}")
def backup_status(job_id: str, request: Request, db: Session = Depends(get_db)):
    """Get backup job status."""
    user = admin_only(request, db)
    if not user:
        return JSONResponse({"error": "需要管理员权限"}, status_code=403)
    
    status = get_job_status(job_id)
    if not status:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    
    return JSONResponse(status)


@router.post("/restore/{filename}")
def restore_backup(filename: str, request: Request, db: Session = Depends(get_db)):
    """Restore database from backup."""
    user = admin_only(request, db)
    if not user:
        return JSONResponse({"error": "需要管理员权限"}, status_code=403)
    
    # Log restore start
    write_log(db, user, "还原数据库", "备份管理", 
              "开始还原备份: {}".format(filename), request)
    
    result = perform_restore(filename, DATABASE_PATH)
    
    if result["success"]:
        # Log restore success
        write_log(db, user, "还原数据库", "备份管理",
                  "还原成功，回退点: {}".format(result.get("restore_point", "")), request)
    
    return JSONResponse(result)


@router.delete("/file/{filename}")
def delete_backup_file(filename: str, request: Request, db: Session = Depends(get_db)):
    """Delete a backup file."""
    user = admin_only(request, db)
    if not user:
        return JSONResponse({"error": "需要管理员权限"}, status_code=403)
    
    result = delete_backup(filename)
    
    if result["success"]:
        write_log(db, user, "删除备份", "备份管理",
                  "删除备份文件: {}".format(filename), request)
    
    return JSONResponse(result)


@router.get("/list")
def list_backup_files(request: Request, db: Session = Depends(get_db)):
    """List all backups."""
    user = admin_only(request, db)
    if not user:
        return JSONResponse({"error": "需要管理员权限"}, status_code=403)
    
    backups = list_backups()
    return JSONResponse({"backups": backups, "warn_retention": should_warn_retention()})
