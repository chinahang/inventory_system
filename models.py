# Python 3.8 compatible - no walrus operator, no PEP 604 union types
from sqlalchemy import (Column, Integer, String, Float, DateTime, Boolean,
                        ForeignKey, Text, UniqueConstraint)
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    role = Column(String)       # 管理员/采购员/仓管员/普通操作员
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class Role(Base):
    """角色：一个角色对应 role_permissions 里的多条权限（一对多）。"""
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)   # 与 users.role 的中文角色名一致
    description = Column(String, default="")
    is_system = Column(Boolean, default=False)       # 系统内置（管理员）不可修改
    created_at = Column(DateTime, default=datetime.now)
    permissions = relationship("RolePermission", back_populates="role",
                               cascade="all, delete-orphan")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission", name="uq_role_permission"),)
    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id"))
    permission = Column(String)                      # 权限点，见 utils/permissions.py
    role = relationship("Role", back_populates="permissions")


class Material(Base):
    __tablename__ = "materials"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    name = Column(String)
    model = Column(String)
    spec = Column(String)
    unit = Column(String)
    safety_stock = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.now)


class Personnel(Base):
    __tablename__ = "personnel"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    employee_id = Column(String, unique=True)
    team = Column(String)
    phone = Column(String)
    role = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class Equipment(Base):
    __tablename__ = "equipment"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    name = Column(String)
    model = Column(String)
    department = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String, unique=True, index=True)
    order_date = Column(DateTime, default=datetime.now)
    purchaser_id = Column(Integer, ForeignKey("personnel.id"))
    operator_id = Column(Integer, ForeignKey("users.id"))
    supplier_contact = Column(String, default="")
    created_at = Column(DateTime, default=datetime.now)
    remark = Column(Text, default="")
    purchaser = relationship("Personnel", foreign_keys=[purchaser_id])
    operator = relationship("User", foreign_keys=[operator_id])
    items = relationship("PurchaseItem", back_populates="order", cascade="all, delete-orphan")


class PurchaseItem(Base):
    __tablename__ = "purchase_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("purchase_orders.id"))
    material_id = Column(Integer, ForeignKey("materials.id"))
    quantity = Column(Float)
    unit_price = Column(Float)
    total_amount = Column(Float)
    order = relationship("PurchaseOrder", back_populates="items")
    material = relationship("Material")


class RequisitionOrder(Base):
    __tablename__ = "requisition_orders"
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String, unique=True, index=True)
    order_date = Column(DateTime, default=datetime.now)
    equipment_id = Column(Integer, ForeignKey("equipment.id"))
    personnel_id = Column(Integer, ForeignKey("personnel.id"))
    operator_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now)
    remark = Column(Text, default="")
    equipment = relationship("Equipment", foreign_keys=[equipment_id])
    personnel = relationship("Personnel", foreign_keys=[personnel_id])
    operator = relationship("User", foreign_keys=[operator_id])
    items = relationship("RequisitionItem", back_populates="order", cascade="all, delete-orphan")


class RequisitionItem(Base):
    __tablename__ = "requisition_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("requisition_orders.id"))
    material_id = Column(Integer, ForeignKey("materials.id"))
    quantity = Column(Float)
    unit_price = Column(Float)
    total_amount = Column(Float)
    order = relationship("RequisitionOrder", back_populates="items")
    material = relationship("Material")


class StockAdjustment(Base):
    __tablename__ = "stock_adjustments"
    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"))
    quantity = Column(Float)
    amount = Column(Float)
    reason = Column(String)
    operator_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now)
    material = relationship("Material")
    operator = relationship("User")


class OperationLog(Base):
    __tablename__ = "operation_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    username = Column(String)
    action = Column(String)
    module = Column(String)
    detail = Column(Text, default="")
    ip = Column(String, default="")
    created_at = Column(DateTime, default=datetime.now)
    user = relationship("User", foreign_keys=[user_id])
