from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate, QDateTime, QTime
from PySide6.QtWidgets import QApplication, QMessageBox

from mes_py.domain.enums import WorkOrderStatus
from mes_py.infrastructure.database import create_engine_from_url, init_database, make_session_factory, session_scope
from mes_py.services.product_service import ProductService
from mes_py.services.production_resource_service import ProductionResourceService
from mes_py.services.work_order_service import WorkOrderService
from mes_py.ui.main_window import WorkOrdersPage, set_combo_current_data


def memory_factory():
    engine = create_engine_from_url("sqlite:///:memory:")
    init_database(engine)
    return make_session_factory(engine)


def test_work_order_page_creates_updates_and_deletes_orders(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    factory = memory_factory()

    with session_scope(factory) as session:
        product = ProductService(session).create_product("fg-001", "測試產品", None, "PCS")
        center = ProductionResourceService(session).create_work_center("wc-001", "組裝中心")
        line = ProductionResourceService(session).create_production_line(center.id, "line-01", "A 線")
        product_id = product.id
        line_id = line.id

    page = WorkOrdersPage(factory)
    page.refresh()

    monkeypatch.setattr(page, "confirm", lambda *args: True)
    monkeypatch.setattr(page, "message", lambda *args: None)
    monkeypatch.setattr(page, "error", lambda exc: (_ for _ in ()).throw(exc))
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: (_ for _ in ()).throw(AssertionError(args[2])),
    )

    assert page.product_select.currentData() == product_id
    assert set_combo_current_data(page.line_select, line_id)

    page.order_no.setText("WO-001")
    page.qty.setText("100")
    page.start_at.setDateTime(QDateTime(QDate(2026, 7, 1), QTime(8, 0)))
    page.end_at.setDateTime(QDateTime(QDate(2026, 7, 1), QTime(17, 0)))
    page.save_work_order()

    assert page.table.rowCount() == 1
    assert page.save_button.objectName() == "AddButton"

    page.table.selectRow(0)
    app.processEvents()

    assert page.selected_id is not None
    assert page.save_button.objectName() == "EditButton"
    assert page.delete_button.isEnabled()
    assert page.start_at.calendarPopup()
    assert page.end_at.calendarPopup()

    page.order_no.setText("WO-002")
    page.qty.setText("150")
    page.save_work_order()

    with session_scope(factory) as session:
        order = WorkOrderService(session).list_work_orders()[0]
        order_id = order.id
        assert order.order_no == "WO-002"
        assert order.product_id == product_id
        assert order.production_line_id == line_id
        assert order.planned_qty == 150
        assert order.status == WorkOrderStatus.PLANNED.value
        assert order.started_at is None
        assert order.completed_at is None

    page.table.selectRow(0)
    app.processEvents()
    assert page.selected_id == order_id

    page.delete_work_order()

    assert page.table.rowCount() == 0
    assert page.save_button.objectName() == "AddButton"
    assert not page.delete_button.isEnabled()

    with session_scope(factory) as session:
        assert WorkOrderService(session).list_work_orders() == []
