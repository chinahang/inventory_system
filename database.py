# Python 3.8 compatible
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base  # SQLAlchemy 1.4 path
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./inventory.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    # Import all models so Base knows about them
    from models import (User, Material, Personnel, Equipment,
                        PurchaseOrder, PurchaseItem,
                        RequisitionOrder, RequisitionItem,
                        StockAdjustment, OperationLog,
                        Role, RolePermission)
    Base.metadata.create_all(bind=engine)

    # Auto-migrate: add columns that may not exist in older DBs
    _migrate(engine)

    # Seed default admin
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            from passlib.context import CryptContext
            ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
            db.add(User(
                username="admin",
                hashed_password=ctx.hash("admin123"[:72]),
                full_name="系统管理员",
                role="管理员",
                is_active=True,
            ))
            db.commit()

        # Seed built-in roles + their default permissions
        _seed_roles(db)
    finally:
        db.close()


def _seed_roles(db):
    """内置角色与默认权限。

    只在角色首次创建时写入默认权限，之后以「权限配置」页面为准，
    重启不会覆盖管理员在页面上的调整。
    """
    from models import Role, RolePermission, User
    from utils.permissions import (DEFAULT_ROLE_PERMISSIONS,
                                   DEFAULT_ROLE_DESCRIPTIONS, SUPER_ROLE)
    changed = False

    for name, perms in DEFAULT_ROLE_PERMISSIONS.items():
        role = db.query(Role).filter(Role.name == name).first()
        if role:
            continue
        role = Role(name=name,
                    description=DEFAULT_ROLE_DESCRIPTIONS.get(name, ""),
                    is_system=(name == SUPER_ROLE))
        db.add(role)
        db.flush()
        for code in (perms or []):
            db.add(RolePermission(role_id=role.id, permission=code))
        changed = True

    # users 表里出现过的其它角色名，补建角色并给只读默认权限，
    # 避免历史数据里的自定义角色升级后一个页面都进不去
    read_only = DEFAULT_ROLE_PERMISSIONS.get("普通操作员") or []
    used_roles = db.query(User.role).distinct().all()
    for row in used_roles:
        name = row[0]
        if not name:
            continue
        if db.query(Role).filter(Role.name == name).first():
            continue
        role = Role(name=name,
                    description="由历史用户数据自动创建，默认只读权限，可在权限配置中调整",
                    is_system=(name == SUPER_ROLE))
        db.add(role)
        db.flush()
        if name != SUPER_ROLE:
            for code in read_only:
                db.add(RolePermission(role_id=role.id, permission=code))
        changed = True

    if changed:
        db.commit()


def _migrate(eng):
    """Add new columns to existing databases without losing data."""
    migrations = [
        ("purchase_orders",  "supplier_contact", "VARCHAR DEFAULT ''"),
    ]
    from sqlalchemy import text
    with eng.connect() as conn:
        for table, col, col_def in migrations:
            try:
                conn.execute(text(
                    "ALTER TABLE {} ADD COLUMN {} {}".format(table, col, col_def)
                ))
                # SQLAlchemy 1.4 requires explicit commit on raw connections
                conn.execute(text("SELECT 1"))  # keep connection alive
            except Exception:
                pass  # column already exists
