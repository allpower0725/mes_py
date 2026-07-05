from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from mes_py.infrastructure.database import create_engine_from_url, init_database, make_session_factory, session_scope
from mes_py.services.production_resource_service import ProductionResourceService
from mes_py.ui.main_window import ACTION_BUTTON_HEIGHT, ResourcesPage, WorkOrdersPage


def memory_factory():
    engine = create_engine_from_url("sqlite:///:memory:")
    init_database(engine)
    return make_session_factory(engine)


def test_resource_and_work_order_code_inputs_uppercase_user_typing() -> None:
    app = QApplication.instance() or QApplication([])
    factory = memory_factory()
    resource_page = ResourcesPage(factory)
    work_order_page = WorkOrdersPage(factory)

    resource_page.center_code.setFocus()
    QTest.keyClicks(resource_page.center_code, "wc-a")
    resource_page.line_code.setFocus()
    QTest.keyClicks(resource_page.line_code, "line-01")
    work_order_page.order_no.setFocus()
    QTest.keyClicks(work_order_page.order_no, "wo-001")
    app.processEvents()

    assert resource_page.center_code.text() == "WC-A"
    assert resource_page.line_code.text() == "LINE-01"
    assert work_order_page.order_no.text() == "WO-001"


def test_resource_page_creates_and_updates_centers_and_lines(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    factory = memory_factory()
    page = ResourcesPage(factory)
    page.refresh()

    assert page.center_save_button.height() == ACTION_BUTTON_HEIGHT
    assert page.line_save_button.height() == ACTION_BUTTON_HEIGHT
    assert page.center_table.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    assert page.line_table.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded

    monkeypatch.setattr(page, "confirm", lambda *args: True)
    monkeypatch.setattr(page, "message", lambda *args: None)
    monkeypatch.setattr(page, "error", lambda exc: (_ for _ in ()).throw(exc))
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: (_ for _ in ()).throw(AssertionError(args[2])),
    )

    page.center_code.setText("WC-A")
    page.center_name.setText("組裝中心")
    page.save_center()

    assert page.center_table.rowCount() == 1
    assert page.center_save_button.objectName() == "AddButton"

    with session_scope(factory) as session:
        center = ProductionResourceService(session).list_work_centers()[0]
        center_id = center.id
        assert center.code == "WC-A"
        assert center.is_active is True

    page.line_code.setText("LINE-A")
    page.line_name.setText("組裝一線")
    page.line_capacity.setText("120")
    page.save_line()

    assert page.line_table.rowCount() == 1
    assert page.line_save_button.objectName() == "AddButton"

    page.center_table.selectRow(0)
    app.processEvents()
    assert page.selected_center_id == center_id
    assert page.center_save_button.objectName() == "EditButton"
    assert page.center_delete_button.isEnabled()

    page.center_name.setText("組裝二部")
    page.center_active.setChecked(False)
    page.save_center()

    page.line_table.selectRow(0)
    app.processEvents()
    assert page.line_save_button.objectName() == "EditButton"
    assert page.line_delete_button.isEnabled()

    page.line_code.setText("LINE-B")
    page.line_capacity.setText("250")
    page.line_active.setChecked(False)
    page.save_line()

    with session_scope(factory) as session:
        service = ProductionResourceService(session)
        updated_center = service.list_work_centers()[0]
        updated_line = service.list_production_lines()[0]
        assert updated_center.name == "組裝二部"
        assert updated_center.is_active is False
        assert updated_line.code == "LINE-B"
        assert updated_line.work_center_id == center_id
        assert updated_line.daily_capacity == 250
        assert updated_line.is_active is False

    page.line_table.selectRow(0)
    app.processEvents()
    page.delete_line()
    assert page.line_table.rowCount() == 0
    assert page.line_save_button.objectName() == "AddButton"
    assert not page.line_delete_button.isEnabled()

    page.center_table.selectRow(0)
    app.processEvents()
    page.delete_center()
    assert page.center_table.rowCount() == 0
    assert page.center_save_button.objectName() == "AddButton"
    assert not page.center_delete_button.isEnabled()

    with session_scope(factory) as session:
        service = ProductionResourceService(session)
        assert service.list_production_lines() == []
        assert service.list_work_centers() == []
