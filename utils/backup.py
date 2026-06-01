# Python 3.8 compatible
import os
import json
import sqlite3
import shutil
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

BACKUP_DIR = "./backups"
MAX_BACKUPS = 7

# In-memory job status tracking
_jobs = {}  # {job_id: {"status": "running"|"completed"|"failed", "progress": 0-100, "error": ""}}


def ensure_backup_dir():
    """Create backup directory if not exists."""
    os.makedirs(BACKUP_DIR, exist_ok=True)


def generate_backup_filename():
    """Generate timestamped backup filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return "backup_{}.db".format(timestamp)


def generate_restore_point_filename():
    """Generate restore point filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return "restore_point_{}.db".format(timestamp)


def get_data_summary(db_path: str) -> str:
    """Get data range summary from database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get earliest order date
        cursor.execute("""
            SELECT MIN(order_date) FROM (
                SELECT order_date FROM purchase_orders
                UNION ALL
                SELECT order_date FROM requisition_orders
            )
        """)
        result = cursor.fetchone()
        earliest = result[0] if result and result[0] else None
        
        conn.close()
        
        if earliest:
            return "{}起".format(earliest)
        else:
            return "无数据"
    except Exception:
        return "未知"


def create_backup_metadata(filename: str, db_path: str) -> Dict:
    """Create metadata file for backup."""
    backup_path = os.path.join(BACKUP_DIR, filename)
    file_size = os.path.getsize(backup_path)
    
    metadata = {
        "filename": filename,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "size_bytes": file_size,
        "size_human": format_file_size(file_size),
        "data_summary": get_data_summary(backup_path),
        "status": "completed"
    }
    
    meta_path = os.path.join(BACKUP_DIR, "{}.meta.json".format(filename))
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    return metadata


def format_file_size(size_bytes: int) -> str:
    """Format file size to human readable."""
    if size_bytes < 1024:
        return "{}B".format(size_bytes)
    elif size_bytes < 1024 * 1024:
        return "{:.1f}KB".format(size_bytes / 1024)
    else:
        return "{:.1f}MB".format(size_bytes / (1024 * 1024))


def perform_backup(source_db: str, job_id: str) -> Dict:
    """Perform SQLite backup with progress tracking."""
    ensure_backup_dir()
    
    filename = generate_backup_filename()
    backup_path = os.path.join(BACKUP_DIR, filename)
    
    _jobs[job_id] = {"status": "running", "progress": 0, "error": ""}
    
    try:
        # SQLite online backup
        source_conn = sqlite3.connect(source_db)
        backup_conn = sqlite3.connect(backup_path)
        
        # Progress callback
        def progress_callback(status, remaining, total):
            if total > 0:
                percent = int((total - remaining) * 100 / total)
                _jobs[job_id]["progress"] = percent
        
        source_conn.backup(backup_conn, pages=100, progress=progress_callback)
        
        source_conn.close()
        backup_conn.close()
        
        # Create metadata
        metadata = create_backup_metadata(filename, source_db)
        
        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["progress"] = 100
        
        return {"success": True, "filename": filename, "metadata": metadata}
        
    except Exception as e:
        # Clean up failed backup
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except Exception:
                pass
        
        error_msg = str(e)
        if "disk" in error_msg.lower() or "space" in error_msg.lower():
            error_msg = "磁盘空间不足，请清理后重试"
        elif "permission" in error_msg.lower():
            error_msg = "文件权限不足，请检查备份目录权限"
        else:
            error_msg = "备份失败: {}".format(error_msg)
        
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = error_msg
        
        return {"success": False, "error": error_msg}


def perform_restore(backup_filename: str, target_db: str) -> Dict:
    """Restore database from backup."""
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    if not os.path.exists(backup_path):
        return {"success": False, "error": "备份文件不存在"}
    
    try:
        # Create restore point first
        restore_point = generate_restore_point_filename()
        restore_point_path = os.path.join(BACKUP_DIR, restore_point)
        
        if os.path.exists(target_db):
            shutil.copy2(target_db, restore_point_path)
            create_backup_metadata(restore_point, target_db)
        
        # Perform restore
        shutil.copy2(backup_path, target_db)
        
        return {
            "success": True,
            "restore_point": restore_point,
            "message": "还原成功，回退点已保存为 {}".format(restore_point)
        }
        
    except Exception as e:
        error_msg = str(e)
        if "disk" in error_msg.lower() or "space" in error_msg.lower():
            error_msg = "磁盘空间不足"
        elif "permission" in error_msg.lower():
            error_msg = "文件权限不足"
        else:
            error_msg = "还原失败: {}".format(error_msg)
        
        return {"success": False, "error": error_msg}


def list_backups() -> List[Dict]:
    """List all backups with metadata."""
    ensure_backup_dir()
    
    backups = []
    for filename in os.listdir(BACKUP_DIR):
        if filename.endswith(".db"):
            meta_path = os.path.join(BACKUP_DIR, "{}.meta.json".format(filename))
            
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                    backups.append(metadata)
            else:
                # Fallback for backups without metadata
                backup_path = os.path.join(BACKUP_DIR, filename)
                file_size = os.path.getsize(backup_path)
                backups.append({
                    "filename": filename,
                    "created_at": datetime.fromtimestamp(os.path.getmtime(backup_path)).strftime("%Y-%m-%d %H:%M:%S"),
                    "size_bytes": file_size,
                    "size_human": format_file_size(file_size),
                    "data_summary": "未知",
                    "status": "completed"
                })
    
    # Sort by creation time descending
    backups.sort(key=lambda x: x["created_at"], reverse=True)
    return backups


def delete_backup(filename: str) -> Dict:
    """Delete a backup file and its metadata."""
    backup_path = os.path.join(BACKUP_DIR, filename)
    meta_path = os.path.join(BACKUP_DIR, "{}.meta.json".format(filename))
    
    try:
        if os.path.exists(backup_path):
            os.remove(backup_path)
        if os.path.exists(meta_path):
            os.remove(meta_path)
        
        return {"success": True, "message": "备份已删除"}
    except Exception as e:
        return {"success": False, "error": "删除失败: {}".format(str(e))}


def get_job_status(job_id: str) -> Optional[Dict]:
    """Get backup job status."""
    return _jobs.get(job_id)


def should_warn_retention() -> bool:
    """Check if backup count exceeds retention limit."""
    backups = list_backups()
    return len(backups) >= MAX_BACKUPS
