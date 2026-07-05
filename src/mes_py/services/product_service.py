from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mes_py.domain.errors import DomainError
from mes_py.domain.models import Product, WorkOrder
from mes_py.services.utils import normalize_code, optional_text, require_text


class ProductService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_products(self) -> list[Product]:
        return list(
            self.session.scalars(
                select(Product).order_by(Product.is_active.desc(), Product.code.asc())
            )
        )

    def create_product(
        self,
        code: str,
        name: str,
        spec: str | None,
        unit: str,
        is_active: bool = True,
    ) -> Product:
        normalized_code = normalize_code(code, "產品料號")
        if self.session.scalar(select(Product).where(Product.code == normalized_code)):
            raise DomainError(f"產品料號 {normalized_code} 已存在")

        product = Product(
            code=normalized_code,
            name=require_text(name, "產品名稱"),
            spec=optional_text(spec),
            unit=require_text(unit, "單位").upper(),
            is_active=is_active,
        )
        self.session.add(product)
        self.session.flush()
        return product

    def update_product(
        self,
        product_id: str,
        code: str,
        name: str,
        spec: str | None,
        unit: str,
        is_active: bool,
    ) -> Product:
        product = self.session.get(Product, product_id)
        if not product:
            raise DomainError("找不到產品")

        normalized_code = normalize_code(code, "產品料號")
        duplicate = self.session.scalar(
            select(Product).where(Product.code == normalized_code, Product.id != product_id)
        )
        if duplicate:
            raise DomainError(f"產品料號 {normalized_code} 已存在")

        product.code = normalized_code
        product.name = require_text(name, "產品名稱")
        product.spec = optional_text(spec)
        product.unit = require_text(unit, "單位").upper()
        product.is_active = is_active
        self.session.flush()
        return product

    def delete_product(self, product_id: str) -> None:
        product = self.session.get(Product, product_id)
        if not product:
            raise DomainError("找不到產品")

        work_order_count = self.session.scalar(
            select(func.count()).select_from(WorkOrder).where(WorkOrder.product_id == product_id)
        )
        if work_order_count:
            raise DomainError("此產品已有工單，無法刪除，請改用停用")

        self.session.delete(product)
        self.session.flush()

