from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QMessageBox

from mes_py.infrastructure.database import create_engine_from_url, init_database, make_session_factory, session_scope
from mes_py.services.product_service import ProductService
from mes_py.ui.main_window import ProductsPage, missing_required_fields


def test_product_form_reset_does_not_restore_stale_selection() -> None:
    app = QApplication.instance() or QApplication([])
    engine = create_engine_from_url("sqlite:///:memory:")
    init_database(engine)
    factory = make_session_factory(engine)

    with session_scope(factory) as session:
        ProductService(session).create_product("fg-001", "測試產品", None, "PCS")

    page = ProductsPage(factory)
    page.refresh()
    page.table.selectRow(0)
    app.processEvents()

    assert page.selected_id is not None
    assert page.save_button.objectName() == "EditButton"

    page._reset_form()
    page.load_selected()

    assert page.selected_id is None
    assert page.code_input.text() == ""
    assert page.name_input.text() == ""
    assert page.unit_input.text() == "PCS"
    assert page.save_button.objectName() == "AddButton"
    assert "新增產品" in page.save_button.text()


def test_product_save_validates_required_fields_before_confirmation(monkeypatch) -> None:
    QApplication.instance() or QApplication([])
    engine = create_engine_from_url("sqlite:///:memory:")
    init_database(engine)
    factory = make_session_factory(engine)
    page = ProductsPage(factory)

    warnings: list[str] = []

    def fake_warning(*args) -> None:
        warnings.append(args[2])

    def fail_confirm(*args) -> bool:
        raise AssertionError("confirmation should not run before required fields are complete")

    monkeypatch.setattr(QMessageBox, "warning", fake_warning)
    monkeypatch.setattr(page, "confirm", fail_confirm)

    page.save_product()

    assert warnings == ["請先補齊必填欄位：\n- 產品料號\n- 產品名稱"]


def test_product_code_input_uppercases_user_typing() -> None:
    app = QApplication.instance() or QApplication([])
    engine = create_engine_from_url("sqlite:///:memory:")
    init_database(engine)
    factory = make_session_factory(engine)
    page = ProductsPage(factory)

    page.code_input.setFocus()
    QTest.keyClicks(page.code_input, "fg-abc-001")
    app.processEvents()

    assert page.code_input.text() == "FG-ABC-001"


def test_missing_required_fields_handles_text_and_required_combo() -> None:
    QApplication.instance() or QApplication([])
    text_input = QLineEdit("  ")
    combo = QComboBox()
    combo.addItem("請選擇", None)

    assert missing_required_fields([("文字欄位", text_input), ("下拉選單", combo)]) == [
        "文字欄位",
        "下拉選單",
    ]

    text_input.setText("FG-001")
    combo.addItem("有效選項", "id-1")
    combo.setCurrentIndex(1)

    assert missing_required_fields([("文字欄位", text_input), ("下拉選單", combo)]) == []
