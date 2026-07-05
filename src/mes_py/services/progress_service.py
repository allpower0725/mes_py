from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from mes_py.domain.enums import WorkOrderStatus
from mes_py.domain.models import WorkOrder


@dataclass(frozen=True)
class ProgressRow:
    id: str
    order_no: str
    product_code: str
    product_name: str
    unit: str
    status: WorkOrderStatus
    planned_qty: Decimal
    good_qty: Decimal
    defect_qty: Decimal
    remaining_qty: Decimal
    completion_rate: float
    yield_rate: float


class ProgressService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_progress(self) -> list[ProgressRow]:
        work_orders = list(
            self.session.scalars(
                select(WorkOrder)
                .options(selectinload(WorkOrder.product), selectinload(WorkOrder.reports))
                .order_by(WorkOrder.status.asc(), WorkOrder.created_at.desc())
            )
        )
        rows: list[ProgressRow] = []
        for work_order in work_orders:
            planned = Decimal(work_order.planned_qty)
            good = sum(Decimal(report.good_qty) for report in work_order.reports)
            defect = sum(Decimal(report.defect_qty) for report in work_order.reports)
            total_reported = good + defect
            remaining = max(Decimal("0"), planned - good)
            completion = float((good / planned) * 100) if planned > 0 else 0.0
            yield_rate = float((good / total_reported) * 100) if total_reported > 0 else 0.0
            rows.append(
                ProgressRow(
                    id=work_order.id,
                    order_no=work_order.order_no,
                    product_code=work_order.product.code,
                    product_name=work_order.product.name,
                    unit=work_order.product.unit,
                    status=WorkOrderStatus(work_order.status),
                    planned_qty=planned,
                    good_qty=good,
                    defect_qty=defect,
                    remaining_qty=remaining,
                    completion_rate=completion,
                    yield_rate=yield_rate,
                )
            )
        return rows

