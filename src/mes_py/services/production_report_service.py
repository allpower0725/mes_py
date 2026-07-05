from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from mes_py.domain.enums import WorkOrderStatus
from mes_py.domain.errors import DomainError
from mes_py.domain.models import ProductionReport, WorkOrder
from mes_py.services.utils import non_negative_decimal, optional_text, require_text, utc_now


class ProductionReportService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_reports(self) -> list[ProductionReport]:
        return list(
            self.session.scalars(
                select(ProductionReport)
                .options(selectinload(ProductionReport.work_order).selectinload(WorkOrder.product))
                .order_by(ProductionReport.reported_at.desc())
            )
        )

    def create_report(
        self,
        work_order_id: str,
        good_qty: str,
        defect_qty: str,
        reported_at: datetime | None = None,
        reporter_name: str | None = None,
        note: str | None = None,
    ) -> ProductionReport:
        work_order = self._find_reportable_work_order(work_order_id)
        good = non_negative_decimal(good_qty, "良品數")
        defect = non_negative_decimal(defect_qty, "不良數")
        if good + defect <= 0:
            raise DomainError("良品數與不良數合計必須大於 0")

        report_time = reported_at or utc_now()
        report = ProductionReport(
            work_order_id=work_order.id,
            reported_at=report_time,
            good_qty=good,
            defect_qty=defect,
            reporter_name=optional_text(reporter_name),
            note=optional_text(note),
        )
        work_order.status = WorkOrderStatus.IN_PROGRESS.value
        work_order.started_at = work_order.started_at or report_time
        self.session.add(report)
        self.session.flush()
        return report

    def delete_report(self, report_id: str) -> None:
        report = self.session.scalar(
            select(ProductionReport)
            .options(selectinload(ProductionReport.work_order))
            .where(ProductionReport.id == report_id)
        )
        if not report:
            raise DomainError("找不到報工紀錄")
        if report.work_order.status == WorkOrderStatus.CANCELLED.value:
            raise DomainError("已取消工單的報工紀錄不可刪除")

        remaining = self.session.scalar(
            select(func.count())
            .select_from(ProductionReport)
            .where(
                ProductionReport.work_order_id == report.work_order_id,
                ProductionReport.id != report_id,
            )
        )
        work_order = report.work_order
        self.session.delete(report)
        if remaining == 0 and work_order.status == WorkOrderStatus.IN_PROGRESS.value:
            work_order.status = WorkOrderStatus.PLANNED.value
            work_order.started_at = None
        self.session.flush()

    def _find_reportable_work_order(self, work_order_id: str) -> WorkOrder:
        work_order = self.session.scalar(
            select(WorkOrder).where(
                WorkOrder.id == require_text(work_order_id, "工單"),
                WorkOrder.status.in_([WorkOrderStatus.PLANNED.value, WorkOrderStatus.IN_PROGRESS.value]),
            )
        )
        if not work_order:
            raise DomainError("此工單不存在，或已完工／取消，無法報工")
        return work_order

