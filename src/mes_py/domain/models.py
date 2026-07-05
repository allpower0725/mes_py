from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from mes_py.domain.enums import UserStatus, WorkOrderStatus


def new_id() -> str:
    return uuid.uuid4().hex


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(40), default=UserStatus.ACTIVE.value, index=True
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(255))


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    spec: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(30), default="PCS")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    work_orders: Mapped[list[WorkOrder]] = relationship(back_populates="product")


class WorkCenter(Base, TimestampMixin):
    __tablename__ = "work_centers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    production_lines: Mapped[list[ProductionLine]] = relationship(back_populates="work_center")


class ProductionLine(Base, TimestampMixin):
    __tablename__ = "production_lines"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    work_center_id: Mapped[str] = mapped_column(ForeignKey("work_centers.id", ondelete="RESTRICT"))
    daily_capacity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    work_center: Mapped[WorkCenter] = relationship(back_populates="production_lines")
    work_orders: Mapped[list[WorkOrder]] = relationship(back_populates="production_line")


class WorkOrder(Base, TimestampMixin):
    __tablename__ = "work_orders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    order_no: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    production_line_id: Mapped[str | None] = mapped_column(
        ForeignKey("production_lines.id", ondelete="SET NULL"), index=True
    )
    planned_qty: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    status: Mapped[str] = mapped_column(
        String(40), default=WorkOrderStatus.PLANNED.value, index=True
    )
    planned_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    planned_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remark: Mapped[str | None] = mapped_column(Text)

    product: Mapped[Product] = relationship(back_populates="work_orders")
    production_line: Mapped[ProductionLine | None] = relationship(back_populates="work_orders")
    reports: Mapped[list[ProductionReport]] = relationship(
        back_populates="work_order", cascade="all, delete-orphan"
    )


class ProductionReport(Base, TimestampMixin):
    __tablename__ = "production_reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    work_order_id: Mapped[str] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), index=True
    )
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    good_qty: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    defect_qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0"))
    reporter_name: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)

    work_order: Mapped[WorkOrder] = relationship(back_populates="reports")

