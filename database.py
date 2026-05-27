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
                        StockAdjustment, OperationLog)
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
    finally:
        db.close()


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
