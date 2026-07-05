from __future__ import annotations

from datetime import datetime, timedelta, timezone

from mes_py.domain.enums import WorkOrderStatus
from mes_py.domain.schedule_alerts import (
    ResourceScheduleOrder,
    ScheduleAlertInput,
    ScheduleAlertType,
    calculate_resource_schedule_alerts,
    calculate_schedule_alerts,
)


def test_overdue_and_not_started_alerts() -> None:
    now = datetime(2026, 7, 5, 8, 0, tzinfo=timezone.utc)
    alerts = calculate_schedule_alerts(
        ScheduleAlertInput(
            status=WorkOrderStatus.PLANNED,
            planned_start_at=now - timedelta(hours=8),
            planned_end_at=now - timedelta(hours=1),
            planned_qty=100,
            completed_good_qty=0,
        ),
        now=now,
    )

    assert [alert.type for alert in alerts] == [
        ScheduleAlertType.OVERDUE,
        ScheduleAlertType.NOT_STARTED_ON_TIME,
    ]


def test_resource_conflict_alerts_both_orders() -> None:
    now = datetime(2026, 7, 5, 8, 0, tzinfo=timezone.utc)
    orders = [
        ResourceScheduleOrder(
            id="a",
            order_no="WO-001",
            status=WorkOrderStatus.PLANNED,
            planned_start_at=now + timedelta(hours=1),
            planned_end_at=now + timedelta(hours=5),
            production_line_id="line-1",
            production_line_name="LINE-1",
        ),
        ResourceScheduleOrder(
            id="b",
            order_no="WO-002",
            status=WorkOrderStatus.PLANNED,
            planned_start_at=now + timedelta(hours=4),
            planned_end_at=now + timedelta(hours=7),
            production_line_id="line-1",
            production_line_name="LINE-1",
        ),
    ]

    alerts = calculate_resource_schedule_alerts(orders, now=now)

    assert alerts["a"][0].type == ScheduleAlertType.RESOURCE_CONFLICT
    assert alerts["b"][0].type == ScheduleAlertType.RESOURCE_CONFLICT

