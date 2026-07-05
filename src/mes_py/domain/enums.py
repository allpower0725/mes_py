from __future__ import annotations

from enum import StrEnum


class UserStatus(StrEnum):
    PENDING_EMAIL_VERIFICATION = "PENDING_EMAIL_VERIFICATION"
    ACTIVE = "ACTIVE"


class WorkOrderStatus(StrEnum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


STATUS_LABELS: dict[WorkOrderStatus, str] = {
    WorkOrderStatus.PLANNED: "計畫中",
    WorkOrderStatus.IN_PROGRESS: "生產中",
    WorkOrderStatus.COMPLETED: "已完工",
    WorkOrderStatus.CANCELLED: "已取消",
}

