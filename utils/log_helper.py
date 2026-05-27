# Python 3.8 compatible
from sqlalchemy.orm import Session
from models import OperationLog


def write_log(db, user, action, module, detail="", request=None):
    # type: (Session, object, str, str, str, object) -> None
    ip = ""
    if request is not None:
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            ip = fwd.split(",")[0]
        elif hasattr(request.client, "host"):
            ip = request.client.host or ""
    log = OperationLog(
        user_id=user.id if user else None,
        username=user.username if user else "unknown",
        action=action,
        module=module,
        detail=detail,
        ip=ip,
    )
    db.add(log)
