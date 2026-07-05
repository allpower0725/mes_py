from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from mes_py.domain.errors import DomainError
from mes_py.domain.models import ProductionLine, WorkCenter, WorkOrder
from mes_py.services.utils import normalize_code, optional_text, positive_decimal, require_text


class ProductionResourceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_work_centers(self) -> list[WorkCenter]:
        return list(
            self.session.scalars(
                select(WorkCenter)
                .options(selectinload(WorkCenter.production_lines))
                .order_by(WorkCenter.is_active.desc(), WorkCenter.code.asc())
            )
        )

    def list_production_lines(self, only_active: bool = False) -> list[ProductionLine]:
        stmt = (
            select(ProductionLine)
            .options(selectinload(ProductionLine.work_center))
            .join(ProductionLine.work_center)
            .order_by(WorkCenter.code.asc(), ProductionLine.code.asc())
        )
        if only_active:
            stmt = stmt.where(ProductionLine.is_active.is_(True), WorkCenter.is_active.is_(True))
        return list(self.session.scalars(stmt))

    def create_work_center(
        self, code: str, name: str, description: str | None = None
    ) -> WorkCenter:
        normalized_code = normalize_code(code, "工作中心代碼")
        if self.session.scalar(select(WorkCenter).where(WorkCenter.code == normalized_code)):
            raise DomainError(f"工作中心代碼 {normalized_code} 已存在")
        center = WorkCenter(
            code=normalized_code,
            name=require_text(name, "工作中心名稱"),
            description=optional_text(description),
            is_active=True,
        )
        self.session.add(center)
        self.session.flush()
        return center

    def update_work_center(
        self,
        center_id: str,
        code: str,
        name: str,
        description: str | None,
        is_active: bool,
    ) -> WorkCenter:
        center = self.session.get(WorkCenter, center_id)
        if not center:
            raise DomainError("找不到工作中心")
        normalized_code = normalize_code(code, "工作中心代碼")
        duplicate = self.session.scalar(
            select(WorkCenter).where(WorkCenter.code == normalized_code, WorkCenter.id != center_id)
        )
        if duplicate:
            raise DomainError(f"工作中心代碼 {normalized_code} 已存在")
        center.code = normalized_code
        center.name = require_text(name, "工作中心名稱")
        center.description = optional_text(description)
        center.is_active = is_active
        self.session.flush()
        return center

    def delete_work_center(self, center_id: str) -> None:
        center = self.session.get(WorkCenter, center_id)
        if not center:
            raise DomainError("找不到工作中心")
        line_count = self.session.scalar(
            select(func.count())
            .select_from(ProductionLine)
            .where(ProductionLine.work_center_id == center_id)
        )
        if line_count:
            raise DomainError("此工作中心已有產線，無法刪除，請先刪除或移轉產線，或改用停用")
        self.session.delete(center)
        self.session.flush()

    def create_production_line(
        self,
        work_center_id: str,
        code: str,
        name: str,
        daily_capacity: str | Decimal | None = None,
    ) -> ProductionLine:
        center = self.session.get(WorkCenter, work_center_id)
        if not center:
            raise DomainError("請選擇有效的工作中心")
        normalized_code = normalize_code(code, "產線代碼")
        if self.session.scalar(select(ProductionLine).where(ProductionLine.code == normalized_code)):
            raise DomainError(f"產線代碼 {normalized_code} 已存在")
        capacity = positive_decimal(daily_capacity, "每日產能") if daily_capacity not in (None, "") else None
        line = ProductionLine(
            code=normalized_code,
            name=require_text(name, "產線名稱"),
            work_center_id=work_center_id,
            daily_capacity=capacity,
            is_active=True,
        )
        self.session.add(line)
        self.session.flush()
        return line

    def update_production_line(
        self,
        line_id: str,
        work_center_id: str,
        code: str,
        name: str,
        daily_capacity: str | Decimal | None,
        is_active: bool,
    ) -> ProductionLine:
        line = self.session.get(ProductionLine, line_id)
        if not line:
            raise DomainError("找不到產線")
        center = self.session.get(WorkCenter, work_center_id)
        if not center:
            raise DomainError("請選擇有效的工作中心")
        normalized_code = normalize_code(code, "產線代碼")
        duplicate = self.session.scalar(
            select(ProductionLine).where(
                ProductionLine.code == normalized_code, ProductionLine.id != line_id
            )
        )
        if duplicate:
            raise DomainError(f"產線代碼 {normalized_code} 已存在")
        line.code = normalized_code
        line.name = require_text(name, "產線名稱")
        line.work_center_id = work_center_id
        line.daily_capacity = (
            positive_decimal(daily_capacity, "每日產能") if daily_capacity not in (None, "") else None
        )
        line.is_active = is_active
        self.session.flush()
        return line

    def delete_production_line(self, line_id: str) -> None:
        line = self.session.get(ProductionLine, line_id)
        if not line:
            raise DomainError("找不到產線")
        work_order_count = self.session.scalar(
            select(func.count()).select_from(WorkOrder).where(WorkOrder.production_line_id == line_id)
        )
        if work_order_count:
            raise DomainError("此產線已有工單，無法刪除，請改用停用以保留歷史關聯")
        self.session.delete(line)
        self.session.flush()
