from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from mes_py.domain.enums import WorkOrderStatus
from mes_py.domain.models import ProductionLine, WorkOrder
from mes_py.domain.schedule_alerts import (
    ResourceScheduleOrder,
    ScheduleAlert,
    ScheduleAlertInput,
    calculate_resource_schedule_alerts,
    calculate_schedule_alerts,
)


@dataclass(frozen=True)
class ScheduleRow:
    id: str
    order_no: str
    product: str
    line: str
    status: WorkOrderStatus
    planned_qty: Decimal
    good_qty: Decimal
    alerts: list[ScheduleAlert]


class ScheduleService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_schedule(self) -> list[ScheduleRow]:
        orders = list(
            self.session.scalars(
                select(WorkOrder)
                .options(
                    selectinload(WorkOrder.product),
                    selectinload(WorkOrder.reports),
                    selectinload(WorkOrder.production_line).selectinload(ProductionLine.work_center),
                )
                .order_by(WorkOrder.planned_start_at.asc().nulls_last(), WorkOrder.order_no.asc())
            )
        )
        resource_alerts = calculate_resource_schedule_alerts(
            [
                ResourceScheduleOrder(
                    id=order.id,
                    order_no=order.order_no,
                    status=WorkOrderStatus(order.status),
                    planned_start_at=order.planned_start_at,
                    planned_end_at=order.planned_end_at,
                    production_line_id=order.production_line_id,
                    production_line_name=order.production_line.name if order.production_line else None,
                )
                for order in orders
            ]
        )
        rows: list[ScheduleRow] = []
        for order in orders:
            good_qty = sum(Decimal(report.good_qty) for report in order.reports)
            alerts = calculate_schedule_alerts(
                ScheduleAlertInput(
                    status=WorkOrderStatus(order.status),
                    planned_start_at=order.planned_start_at,
                    planned_end_at=order.planned_end_at,
                    planned_qty=float(order.planned_qty),
                    completed_good_qty=float(good_qty),
                )
            )
            alerts.extend(resource_alerts.get(order.id, []))
            line = (
                f"{order.production_line.work_center.code} / {order.production_line.code}"
                if order.production_line
                else "未指派"
            )
            rows.append(
                ScheduleRow(
                    id=order.id,
                    order_no=order.order_no,
                    product=f"{order.product.code} {order.product.name}",
                    line=line,
                    status=WorkOrderStatus(order.status),
                    planned_qty=Decimal(order.planned_qty),
                    good_qty=good_qty,
                    alerts=alerts,
                )
            )
        return rows

