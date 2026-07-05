from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from mes_py.domain.enums import WorkOrderStatus
from mes_py.infrastructure.database import (
    create_engine_from_url,
    init_database,
    make_session_factory,
    session_scope,
)
from mes_py.services import (
    ProductService,
    ProductionReportService,
    ProductionResourceService,
    WorkOrderService,
)
from mes_py.services.progress_service import ProgressService


def memory_session_factory() -> sessionmaker:
    engine = create_engine_from_url("sqlite:///:memory:")
    init_database(engine)
    return make_session_factory(engine)


def test_report_moves_work_order_to_in_progress() -> None:
    factory = memory_session_factory()
    with session_scope(factory) as session:
        product = ProductService(session).create_product("fg-001", "成品 A", None, "PCS")
        center = ProductionResourceService(session).create_work_center("wc-1", "組裝")
        line = ProductionResourceService(session).create_production_line(center.id, "line-1", "A 線")
        work_order = WorkOrderService(session).create_work_order(
            "wo-001",
            product.id,
            line.id,
            "100",
        )
        report = ProductionReportService(session).create_report(work_order.id, "20", "2")
        report_id = report.id
        work_order_id = work_order.id

    with session_scope(factory) as session:
        rows = ProgressService(session).list_progress()
        assert rows[0].status == WorkOrderStatus.IN_PROGRESS
        assert rows[0].good_qty == 20
        assert rows[0].defect_qty == 2

        ProductionReportService(session).delete_report(report_id)

    with session_scope(factory) as session:
        work_order = WorkOrderService(session).list_work_orders()[0]
        assert work_order.id == work_order_id
        assert work_order.status == WorkOrderStatus.PLANNED.value
        assert work_order.started_at is None

