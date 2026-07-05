from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from mes_py.domain.enums import WorkOrderStatus
from mes_py.domain.errors import DomainError
from mes_py.domain.models import Product, ProductionLine, WorkCenter, WorkOrder, ProductionReport
from mes_py.services.utils import ensure_time_range, normalize_code, optional_text, positive_decimal, require_text, utc_now


class WorkOrderService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_work_orders(self) -> list[WorkOrder]:
        return list(
            self.session.scalars(
                select(WorkOrder)
                .options(
                    selectinload(WorkOrder.product),
                    selectinload(WorkOrder.production_line).selectinload(ProductionLine.work_center),
                    selectinload(WorkOrder.reports),
                )
                .order_by(WorkOrder.created_at.desc())
            )
        )

    def create_work_order(
        self,
        order_no: str,
        product_id: str,
        production_line_id: str | None,
        planned_qty: str,
        planned_start_at: datetime | None = None,
        planned_end_at: datetime | None = None,
        remark: str | None = None,
    ) -> WorkOrder:
        normalized_order_no = normalize_code(order_no, "工單號碼")
        if self.session.scalar(select(WorkOrder).where(WorkOrder.order_no == normalized_order_no)):
            raise DomainError(f"工單號碼 {normalized_order_no} 已存在")

        self._ensure_active_product(product_id)
        line_id = self._read_active_line_id(production_line_id)
        ensure_time_range(planned_start_at, planned_end_at)

        work_order = WorkOrder(
            order_no=normalized_order_no,
            product_id=product_id,
            production_line_id=line_id,
            planned_qty=positive_decimal(planned_qty, "預計生產數量"),
            status=WorkOrderStatus.PLANNED.value,
            planned_start_at=planned_start_at,
            planned_end_at=planned_end_at,
            remark=optional_text(remark),
        )
        self.session.add(work_order)
        self.session.flush()
        return work_order

    def update_work_order(
        self,
        work_order_id: str,
        order_no: str,
        product_id: str,
        production_line_id: str | None,
        planned_qty: str,
        status: WorkOrderStatus,
        planned_start_at: datetime | None = None,
        planned_end_at: datetime | None = None,
        remark: str | None = None,
    ) -> WorkOrder:
        work_order = self.session.get(WorkOrder, work_order_id)
        if not work_order:
            raise DomainError("找不到工單")

        normalized_order_no = normalize_code(order_no, "工單號碼")
        duplicate = self.session.scalar(
            select(WorkOrder).where(WorkOrder.order_no == normalized_order_no, WorkOrder.id != work_order_id)
        )
        if duplicate:
            raise DomainError(f"工單號碼 {normalized_order_no} 已存在")
        if work_order.product_id != product_id:
            self._ensure_active_product(product_id)
        line_id = self._read_active_line_id(production_line_id, current_id=work_order.production_line_id)
        ensure_time_range(planned_start_at, planned_end_at)

        current_status = WorkOrderStatus(work_order.status)
        report_count = self.session.scalar(
            select(func.count())
            .select_from(ProductionReport)
            .where(ProductionReport.work_order_id == work_order_id)
        )
        if current_status in {WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED}:
            if status != current_status:
                raise DomainError("已完工或已取消的工單不可再變更狀態")
            if line_id != work_order.production_line_id:
                raise DomainError("已完工或已取消的工單不可重新指派產線")
        if report_count and status == WorkOrderStatus.PLANNED:
            raise DomainError("已有報工紀錄的工單不可改回計畫中")

        now = utc_now()
        work_order.order_no = normalized_order_no
        work_order.product_id = product_id
        work_order.production_line_id = line_id
        work_order.planned_qty = positive_decimal(planned_qty, "預計生產數量")
        work_order.status = status.value
        work_order.planned_start_at = planned_start_at
        work_order.planned_end_at = planned_end_at
        work_order.remark = optional_text(remark)
        work_order.started_at = None if status == WorkOrderStatus.PLANNED else work_order.started_at or now
        work_order.completed_at = work_order.completed_at or now if status == WorkOrderStatus.COMPLETED else None
        self.session.flush()
        return work_order

    def delete_work_order(self, work_order_id: str) -> None:
        work_order = self.session.get(WorkOrder, work_order_id)
        if not work_order:
            raise DomainError("找不到工單")
        report_count = self.session.scalar(
            select(func.count())
            .select_from(ProductionReport)
            .where(ProductionReport.work_order_id == work_order_id)
        )
        if report_count:
            raise DomainError("此工單已有報工紀錄，請改用取消狀態保留追溯資料")
        self.session.delete(work_order)
        self.session.flush()

    def _ensure_active_product(self, product_id: str) -> None:
        product = self.session.scalar(
            select(Product).where(Product.id == require_text(product_id, "產品"), Product.is_active.is_(True))
        )
        if not product:
            raise DomainError("請選擇有效且啟用中的產品")

    def _read_active_line_id(self, line_id: str | None, current_id: str | None = None) -> str | None:
        if not line_id:
            return None
        if current_id and line_id == current_id:
            return line_id
        line = self.session.scalar(
            select(ProductionLine)
            .join(ProductionLine.work_center)
            .where(
                ProductionLine.id == line_id,
                ProductionLine.is_active.is_(True),
                WorkCenter.is_active.is_(True),
            )
        )
        if not line:
            raise DomainError("請選擇有效且啟用中的產線")
        return line_id

