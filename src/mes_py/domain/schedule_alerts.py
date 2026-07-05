from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum

from mes_py.domain.enums import WorkOrderStatus


class ScheduleAlertType(StrEnum):
    OVERDUE = "OVERDUE"
    NOT_STARTED_ON_TIME = "NOT_STARTED_ON_TIME"
    DUE_SOON = "DUE_SOON"
    BEHIND_SCHEDULE = "BEHIND_SCHEDULE"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    UNASSIGNED_RESOURCE = "UNASSIGNED_RESOURCE"


ALERT_LABELS: dict[ScheduleAlertType, tuple[str, str]] = {
    ScheduleAlertType.OVERDUE: ("已超過預計完工時間，工單仍未完工", "逾期"),
    ScheduleAlertType.NOT_STARTED_ON_TIME: ("已超過預計開始時間，工單仍未開始", "未準時開工"),
    ScheduleAlertType.DUE_SOON: ("預計完工時間將在 24 小時內到期", "即將到期"),
    ScheduleAlertType.BEHIND_SCHEDULE: ("良品完成率低於排程時間經過比例", "進度落後"),
    ScheduleAlertType.RESOURCE_CONFLICT: ("同一產線存在時間重疊的工單", "產線衝突"),
    ScheduleAlertType.UNASSIGNED_RESOURCE: ("工單將於 24 小時內開工，但尚未指派產線", "未指派產線"),
}


@dataclass(frozen=True)
class ScheduleAlert:
    type: ScheduleAlertType
    reason: str

    @property
    def short_label(self) -> str:
        return ALERT_LABELS[self.type][1]


@dataclass(frozen=True)
class ScheduleAlertInput:
    status: WorkOrderStatus
    planned_start_at: datetime | None
    planned_end_at: datetime | None
    planned_qty: float
    completed_good_qty: float


@dataclass(frozen=True)
class ResourceScheduleOrder:
    id: str
    order_no: str
    status: WorkOrderStatus
    planned_start_at: datetime | None
    planned_end_at: datetime | None
    production_line_id: str | None
    production_line_name: str | None = None


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def calculate_schedule_alerts(
    item: ScheduleAlertInput,
    now: datetime | None = None,
) -> list[ScheduleAlert]:
    current = now or datetime.now(timezone.utc)
    start = _aware(item.planned_start_at)
    end = _aware(item.planned_end_at)

    if item.status in {WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED}:
        return []

    alerts: list[ScheduleAlert] = []
    if end and current > end:
        alerts.append(ScheduleAlert(ScheduleAlertType.OVERDUE, ALERT_LABELS[ScheduleAlertType.OVERDUE][0]))

    if item.status == WorkOrderStatus.PLANNED and start and current > start:
        alerts.append(
            ScheduleAlert(
                ScheduleAlertType.NOT_STARTED_ON_TIME,
                ALERT_LABELS[ScheduleAlertType.NOT_STARTED_ON_TIME][0],
            )
        )

    if end and current <= end and end - current <= timedelta(hours=24):
        alerts.append(ScheduleAlert(ScheduleAlertType.DUE_SOON, ALERT_LABELS[ScheduleAlertType.DUE_SOON][0]))

    if start and end and end > start and start < current < end and item.planned_qty > 0:
        completion_ratio = max(0.0, item.completed_good_qty) / item.planned_qty
        elapsed_ratio = (current - start).total_seconds() / (end - start).total_seconds()
        if completion_ratio < elapsed_ratio:
            alerts.append(
                ScheduleAlert(
                    ScheduleAlertType.BEHIND_SCHEDULE,
                    (
                        f"{ALERT_LABELS[ScheduleAlertType.BEHIND_SCHEDULE][0]}"
                        f"（完成 {completion_ratio * 100:.1f}%，時間已經過 {elapsed_ratio * 100:.1f}%）"
                    ),
                )
            )

    return alerts


def calculate_resource_schedule_alerts(
    orders: list[ResourceScheduleOrder],
    now: datetime | None = None,
) -> dict[str, list[ScheduleAlert]]:
    current = now or datetime.now(timezone.utc)
    result: dict[str, list[ScheduleAlert]] = {}
    active = [
        order
        for order in orders
        if order.status not in {WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED}
    ]

    def add(order_id: str, alert: ScheduleAlert) -> None:
        result.setdefault(order_id, []).append(alert)

    for order in active:
        start = _aware(order.planned_start_at)
        if (
            not order.production_line_id
            and order.status == WorkOrderStatus.PLANNED
            and start
            and start >= current
            and start - current <= timedelta(hours=24)
        ):
            add(
                order.id,
                ScheduleAlert(
                    ScheduleAlertType.UNASSIGNED_RESOURCE,
                    ALERT_LABELS[ScheduleAlertType.UNASSIGNED_RESOURCE][0],
                ),
            )

    for index, first in enumerate(active):
        for second in active[index + 1 :]:
            if (
                not first.production_line_id
                or first.production_line_id != second.production_line_id
                or not first.planned_start_at
                or not first.planned_end_at
                or not second.planned_start_at
                or not second.planned_end_at
            ):
                continue

            first_start = _aware(first.planned_start_at)
            first_end = _aware(first.planned_end_at)
            second_start = _aware(second.planned_start_at)
            second_end = _aware(second.planned_end_at)
            if first_start and first_end and second_start and second_end:
                if first_start < second_end and first_end > second_start:
                    line_name = first.production_line_name or "同一產線"
                    add(
                        first.id,
                        ScheduleAlert(
                            ScheduleAlertType.RESOURCE_CONFLICT,
                            f"{line_name} 與工單 {second.order_no} 的排程重疊",
                        ),
                    )
                    add(
                        second.id,
                        ScheduleAlert(
                            ScheduleAlertType.RESOURCE_CONFLICT,
                            f"{line_name} 與工單 {first.order_no} 的排程重疊",
                        ),
                    )

    return result

