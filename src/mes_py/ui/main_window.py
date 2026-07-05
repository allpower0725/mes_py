from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from importlib.resources import files
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from mes_py.domain.enums import STATUS_LABELS, WorkOrderStatus
from mes_py.domain.errors import DomainError
from mes_py.domain.models import Product, ProductionReport, WorkOrder
from mes_py.infrastructure.database import session_scope
from mes_py.services import (
    AuthService,
    ProductService,
    ProductionReportService,
    ProductionResourceService,
    ProgressService,
    WorkOrderService,
)
from mes_py.services.bootstrap import bootstrap_application
from mes_py.services.schedule_service import ScheduleService
from mes_py.settings import Settings


ACTION_BUTTON_WIDTH = 178
ACTION_BUTTON_HEIGHT = 30
TABLE_HEADER_HEIGHT = 38
TABLE_ROW_HEIGHT = 30


def run_app(settings: Settings) -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("FlowMES Python")
    style_path = files("mes_py.ui").joinpath("styles.qss")
    app.setStyleSheet(style_path.read_text(encoding="utf-8"))

    session_factory = bootstrap_application(settings)
    login = LoginDialog(session_factory)
    if login.exec() != QDialog.Accepted or login.user is None:
        return 0

    window = MainWindow(session_factory=session_factory, user=login.user)
    window.resize(1440, 1080)
    window.show()
    return app.exec()


class LoginDialog(QDialog):
    def __init__(self, session_factory: sessionmaker, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session_factory = session_factory
        self.user = None
        self.setWindowTitle("FlowMES 登入")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        title = QLabel("FlowMES")
        title.setObjectName("BrandTitle")
        subtitle = QLabel("Production OS")
        subtitle.setObjectName("Muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.email_input = QLineEdit("admin@local")
        self.email_input.setPlaceholderText("Email")
        self.password_input = QLineEdit("admin123")
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.email_input)
        layout.addWidget(self.password_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("登入")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._authenticate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _authenticate(self) -> None:
        try:
            with session_scope(self.session_factory) as session:
                self.user = AuthService(session).authenticate(
                    self.email_input.text(),
                    self.password_input.text(),
                )
        except DomainError as exc:
            QMessageBox.warning(self, "登入失敗", str(exc))
            return
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, session_factory: sessionmaker, user: Any) -> None:
        super().__init__()
        self.session_factory = session_factory
        self.user = user
        self.setWindowTitle("FlowMES Python")

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = self._build_sidebar()
        root_layout.addWidget(self.sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        root_layout.addWidget(content, 1)

        self.title_label = QLabel("生產儀表板")
        self.title_label.setObjectName("PageTitle")
        self.page_description_label = QLabel()
        self.page_description_label.setObjectName("Muted")
        self.page_description_label.setWordWrap(True)
        topbar = self._build_topbar()
        content_layout.addWidget(topbar)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 1)

        self.pages: list[tuple[str, str, QWidget]] = [
            ("儀表板", "▦ 儀表板", DashboardPage(session_factory)),
            ("產品管理", "◇ 產品管理", ProductsPage(session_factory)),
            ("生產資源", "⌘ 生產資源", ResourcesPage(session_factory)),
            ("工單管理", "▤ 工單管理", WorkOrdersPage(session_factory)),
            ("生產報工", "▥ 生產報工", ReportsPage(session_factory)),
            ("進度查詢", "⌕ 進度查詢", ProgressPage(session_factory)),
            ("生產排程", "◷ 生產排程", SchedulePage(session_factory)),
        ]
        self.nav_buttons: list[QPushButton] = []
        for index, (title, label, page) in enumerate(self.pages):
            button = QPushButton(label)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self.show_page(i))
            self.nav_layout.addWidget(button)
            self.nav_buttons.append(button)
            self.stack.addWidget(page)

        self.nav_layout.addStretch(1)
        self.show_page(0)
        self.statusBar().showMessage("系統連線正常")

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(250)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        brand = QLabel("FlowMES")
        brand.setObjectName("BrandTitle")
        sub = QLabel("Production OS")
        sub.setObjectName("BrandSub")
        layout.addWidget(brand)
        layout.addWidget(sub)

        label = QLabel("工作台")
        label.setObjectName("Eyebrow")
        layout.addWidget(label)
        self.nav_layout = QVBoxLayout()
        self.nav_layout.setSpacing(6)
        layout.addLayout(self.nav_layout)

        footer = QLabel("● 系統連線正常")
        footer.setObjectName("Muted")
        layout.addWidget(footer)
        return sidebar

    def _build_topbar(self) -> QFrame:
        topbar = QFrame()
        topbar.setObjectName("Topbar")
        topbar.setFixedHeight(82)
        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(28, 12, 28, 12)

        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        eyebrow = QLabel("MANUFACTURING EXECUTION SYSTEM")
        eyebrow.setObjectName("Eyebrow")
        title_block.addWidget(eyebrow)
        title_block.addWidget(self.title_label)
        title_block.addWidget(self.page_description_label)
        layout.addLayout(title_block)
        layout.addStretch(1)

        user_label = QLabel(f"{self.user.name}  |  {self.user.email}")
        user_label.setObjectName("Muted")
        layout.addWidget(user_label)
        return topbar

    def show_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.title_label.setText(self.pages[index][0])
        description = getattr(self.stack.widget(index), "topbar_description", "")
        self.page_description_label.setText(description)
        self.page_description_label.setVisible(bool(description))
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)
        page = self.stack.widget(index)
        if hasattr(page, "refresh"):
            page.refresh()


class Page(QWidget):
    def __init__(self, session_factory: sessionmaker) -> None:
        super().__init__()
        self.session_factory = session_factory

    def require_fields(self, fields: list[tuple[str, QWidget]]) -> bool:
        missing = missing_required_fields(fields)
        if not missing:
            return True
        QMessageBox.warning(
            self,
            "資料不完整",
            "請先補齊必填欄位：\n" + "\n".join(f"- {label}" for label in missing),
        )
        return False

    def confirm(self, title: str, text: str) -> bool:
        return (
            QMessageBox.question(
                self,
                title,
                text,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            == QMessageBox.Yes
        )

    def message(self, title: str, text: str) -> None:
        QMessageBox.information(self, title, text)

    def error(self, exc: Exception) -> None:
        QMessageBox.warning(self, "操作失敗", str(exc))


class DashboardPage(Page):
    def __init__(self, session_factory: sessionmaker) -> None:
        super().__init__(session_factory)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        self.metrics = QGridLayout()
        layout.addLayout(self.metrics)
        self.alert_table = make_table(["工單", "產品", "產線", "狀態", "警示"])
        layout.addWidget(self.alert_table, 1)

    def refresh(self) -> None:
        clear_layout(self.metrics)
        with session_scope(self.session_factory) as session:
            product_count = session.scalar(select(func.count()).select_from(Product).where(Product.is_active.is_(True))) or 0
            work_order_count = session.scalar(select(func.count()).select_from(WorkOrder)) or 0
            report_count = session.scalar(select(func.count()).select_from(ProductionReport)) or 0
            in_progress = session.scalar(
                select(func.count()).select_from(WorkOrder).where(WorkOrder.status == WorkOrderStatus.IN_PROGRESS.value)
            ) or 0
            metrics = [
                ("啟用產品", product_count, "項"),
                ("全部工單", work_order_count, "張"),
                ("生產中", in_progress, "張"),
                ("報工筆數", report_count, "筆"),
            ]
            for index, (label, value, unit) in enumerate(metrics):
                self.metrics.addWidget(metric_panel(label, str(value), unit), 0, index)

            rows = ScheduleService(session).list_schedule()
            alert_rows = [row for row in rows if row.alerts]
            fill_table(
                self.alert_table,
                [
                    [
                        row.order_no,
                        row.product,
                        row.line,
                        STATUS_LABELS[row.status],
                        "、".join(alert.short_label for alert in row.alerts),
                    ]
                    for row in alert_rows
                ],
            )


class ProductsPage(Page):
    topbar_description = "維護可投入工單的產品主檔。產品料號會自動轉成大寫，停用產品仍會保留歷史資料關聯。"

    def __init__(self, session_factory: sessionmaker) -> None:
        super().__init__(session_factory)
        self.selected_id: str | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        form = panel()
        form_layout = QGridLayout(form)
        form_layout.setContentsMargins(18, 18, 18, 18)
        form_layout.setHorizontalSpacing(16)
        form_layout.setVerticalSpacing(10)
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("例如：FG-001")
        enable_uppercase_input(self.code_input)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("例如：測試成品")
        self.spec_input = QLineEdit()
        self.spec_input.setPlaceholderText("選填")
        self.unit_input = QLineEdit("PCS")
        self.unit_input.setPlaceholderText("PCS")
        self.active_input = QCheckBox("啟用")
        self.active_input.setChecked(True)
        add_inline_field(form_layout, 0, "產品料號", self.code_input, required=True)
        add_inline_field(form_layout, 1, "產品名稱", self.name_input, required=True)
        add_inline_field(form_layout, 2, "規格", self.spec_input)
        add_inline_field(form_layout, 3, "單位", self.unit_input, required=True)
        add_inline_field(form_layout, 4, "狀態", self.active_input)
        form_layout.setColumnStretch(0, 1)
        form_layout.setColumnStretch(1, 2)
        form_layout.setColumnStretch(2, 2)
        form_layout.setColumnStretch(3, 1)
        form_layout.setColumnStretch(4, 1)

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 10, 0, 0)
        action_layout.setSpacing(10)
        self.save_button = add_button("新增產品")
        self.clear_button = clear_button("清除表單")
        self.delete_button = danger_button("刪除產品")
        self.delete_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_product)
        self.clear_button.clicked.connect(self.clear_form)
        self.delete_button.clicked.connect(self.delete_product)
        action_layout.addWidget(self.save_button)
        action_layout.addWidget(self.clear_button)
        action_layout.addWidget(self.delete_button)
        action_layout.addStretch(1)
        form_layout.addLayout(action_layout, 2, 0, 1, 5)
        layout.addWidget(form)

        self.table = make_table(["狀態", "料號", "名稱", "規格", "單位"])
        self.table.itemSelectionChanged.connect(self.load_selected)
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        with session_scope(self.session_factory) as session:
            products = ProductService(session).list_products()
            self.table.blockSignals(True)
            try:
                fill_table(
                    self.table,
                    [
                        [
                            "啟用" if item.is_active else "停用",
                            item.code,
                            item.name,
                            item.spec or "",
                            item.unit,
                        ]
                        for item in products
                    ],
                    [item.id for item in products],
                )
                if self.selected_id is None:
                    self.table.clearSelection()
            finally:
                self.table.blockSignals(False)

    def load_selected(self) -> None:
        if not self.table.selectedItems():
            return
        row = self.table.currentRow()
        if row < 0:
            return
        self.selected_id = self.table.item(row, 0).data(Qt.UserRole)
        self.active_input.setChecked(self.table.item(row, 0).text() == "啟用")
        self.code_input.setText(self.table.item(row, 1).text())
        self.name_input.setText(self.table.item(row, 2).text())
        self.spec_input.setText(self.table.item(row, 3).text())
        self.unit_input.setText(self.table.item(row, 4).text())
        set_action_button(self.save_button, "edit", "修改產品")
        self.delete_button.setEnabled(True)

    def save_product(self) -> None:
        if not self.require_fields(
            [
                ("產品料號", self.code_input),
                ("產品名稱", self.name_input),
                ("單位", self.unit_input),
            ]
        ):
            return
        is_update = self.selected_id is not None
        action_label = "修改" if is_update else "新增"
        product_code = self.code_input.text().strip().upper()
        if not self.confirm(
            f"確認{action_label}產品",
            f"產品料號：{self.code_input.text().strip() or '未輸入'}\n"
            f"產品名稱：{self.name_input.text().strip() or '未輸入'}\n"
            f"狀態：{'啟用' if self.active_input.isChecked() else '停用'}\n\n"
            f"是否要{action_label}這筆產品資料？",
        ):
            return

        try:
            with session_scope(self.session_factory) as session:
                service = ProductService(session)
                if is_update and self.selected_id:
                    service.update_product(
                        self.selected_id,
                        self.code_input.text(),
                        self.name_input.text(),
                        self.spec_input.text(),
                        self.unit_input.text(),
                        self.active_input.isChecked(),
                    )
                else:
                    service.create_product(
                        self.code_input.text(),
                        self.name_input.text(),
                        self.spec_input.text(),
                        self.unit_input.text(),
                        self.active_input.isChecked(),
                    )
            self._reset_form()
            self.refresh()
            self.message("操作完成", f"產品 {product_code} 已{action_label}")
        except DomainError as exc:
            self.error(exc)

    def delete_product(self) -> None:
        if not self.selected_id:
            self.message("請先選擇資料", "請先在下方表格點選要刪除的產品。")
            return
        if not self.confirm(
            "確認刪除產品",
            f"產品料號：{self.code_input.text().strip()}\n"
            f"產品名稱：{self.name_input.text().strip()}\n\n"
            "此操作無法刪除已被工單使用的產品；若已有關聯資料，請改用停用。\n"
            "是否確定刪除？",
        ):
            return
        try:
            code = self.code_input.text().strip().upper()
            with session_scope(self.session_factory) as session:
                ProductService(session).delete_product(self.selected_id)
            self._reset_form()
            self.refresh()
            self.message("刪除完成", f"產品 {code} 已刪除")
        except DomainError as exc:
            self.error(exc)

    def clear_form(self) -> None:
        self._reset_form()

    def _reset_form(self) -> None:
        self.selected_id = None
        for widget in [self.code_input, self.name_input, self.spec_input]:
            widget.clear()
        self.unit_input.setText("PCS")
        self.active_input.setChecked(True)
        self.table.blockSignals(True)
        try:
            self.table.clearSelection()
        finally:
            self.table.blockSignals(False)
        set_action_button(self.save_button, "add", "新增產品")
        self.delete_button.setEnabled(False)


class ResourcesPage(Page):
    topbar_description = "維護生產資源，供工單排程與衝突檢查使用。"

    def __init__(self, session_factory: sessionmaker) -> None:
        super().__init__(session_factory)
        self.selected_center_id: str | None = None
        self.selected_line_id: str | None = None
        self._center_by_id: dict[str, dict[str, Any]] = {}
        self._line_by_id: dict[str, dict[str, Any]] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        self.metrics = QGridLayout()
        self.metrics.setHorizontalSpacing(12)
        layout.addLayout(self.metrics)

        center_group = QGroupBox("工作中心")
        center_layout = QGridLayout(center_group)
        center_layout.setContentsMargins(18, 22, 18, 18)
        center_layout.setHorizontalSpacing(16)
        center_layout.setVerticalSpacing(10)
        self.center_code = QLineEdit()
        self.center_code.setPlaceholderText("例如：WC-001")
        enable_uppercase_input(self.center_code)
        self.center_name = QLineEdit()
        self.center_name.setPlaceholderText("例如：組裝中心")
        self.center_desc = QLineEdit()
        self.center_desc.setPlaceholderText("選填，例如：一樓組裝區")
        self.center_active = QCheckBox("啟用")
        self.center_active.setChecked(True)
        add_inline_field(center_layout, 0, "工作中心代碼", self.center_code, required=True)
        add_inline_field(center_layout, 1, "工作中心名稱", self.center_name, required=True)
        add_inline_field(center_layout, 2, "說明", self.center_desc)
        add_inline_field(center_layout, 3, "狀態", self.center_active)
        center_layout.setColumnStretch(0, 1)
        center_layout.setColumnStretch(1, 2)
        center_layout.setColumnStretch(2, 3)
        center_layout.setColumnStretch(3, 1)

        center_actions = QHBoxLayout()
        center_actions.setContentsMargins(0, 14, 0, 0)
        center_actions.setSpacing(10)
        self.center_save_button = add_button("新增工作中心")
        self.center_clear_button = clear_button("清除資料")
        self.center_delete_button = danger_button("刪除工作中心")
        self.center_delete_button.setEnabled(False)
        self.center_save_button.clicked.connect(self.save_center)
        self.center_clear_button.clicked.connect(self.clear_center_form)
        self.center_delete_button.clicked.connect(self.delete_center)
        center_actions.addWidget(self.center_save_button)
        center_actions.addWidget(self.center_clear_button)
        center_actions.addWidget(self.center_delete_button)
        center_actions.addStretch(1)
        center_layout.addLayout(center_actions, 2, 0, 1, 4)

        center_table_label = QLabel("現有工作中心")
        center_table_label.setObjectName("FieldLabel")
        self.center_table = make_table(["狀態", "代碼", "名稱", "說明", "產線數"])
        constrain_table_rows(self.center_table)
        self.center_table.itemSelectionChanged.connect(self.load_selected_center)
        center_layout.addWidget(center_table_label, 3, 0, 1, 4)
        center_layout.addWidget(self.center_table, 4, 0, 1, 4)
        layout.addWidget(center_group)

        line_group = QGroupBox("產線")
        line_layout = QGridLayout(line_group)
        line_layout.setContentsMargins(18, 22, 18, 18)
        line_layout.setHorizontalSpacing(16)
        line_layout.setVerticalSpacing(10)
        self.line_center = QComboBox()
        self.line_center.setPlaceholderText("請選擇工作中心")
        self.line_code = QLineEdit()
        self.line_code.setPlaceholderText("例如：LINE-01")
        enable_uppercase_input(self.line_code)
        self.line_name = QLineEdit()
        self.line_name.setPlaceholderText("例如：A 線")
        self.line_capacity = QLineEdit()
        self.line_capacity.setPlaceholderText("選填，例如：1000")
        self.line_active = QCheckBox("啟用")
        self.line_active.setChecked(True)
        add_inline_field(line_layout, 0, "工作中心", self.line_center, required=True)
        add_inline_field(line_layout, 1, "產線代碼", self.line_code, required=True)
        add_inline_field(line_layout, 2, "產線名稱", self.line_name, required=True)
        add_inline_field(line_layout, 3, "每日產能", self.line_capacity)
        add_inline_field(line_layout, 4, "狀態", self.line_active)
        line_layout.setColumnStretch(0, 2)
        line_layout.setColumnStretch(1, 1)
        line_layout.setColumnStretch(2, 2)
        line_layout.setColumnStretch(3, 1)
        line_layout.setColumnStretch(4, 1)

        line_actions = QHBoxLayout()
        line_actions.setContentsMargins(0, 14, 0, 0)
        line_actions.setSpacing(10)
        self.line_save_button = add_button("新增產線")
        self.line_clear_button = clear_button("清除資料")
        self.line_delete_button = danger_button("刪除產線")
        self.line_delete_button.setEnabled(False)
        self.line_save_button.clicked.connect(self.save_line)
        self.line_clear_button.clicked.connect(self.clear_line_form)
        self.line_delete_button.clicked.connect(self.delete_line)
        line_actions.addWidget(self.line_save_button)
        line_actions.addWidget(self.line_clear_button)
        line_actions.addWidget(self.line_delete_button)
        line_actions.addStretch(1)
        line_layout.addLayout(line_actions, 2, 0, 1, 5)

        line_table_label = QLabel("現有產線")
        line_table_label.setObjectName("FieldLabel")
        self.line_table = make_table(["狀態", "工作中心", "產線代碼", "產線名稱", "每日產能", "工單數"])
        constrain_table_rows(self.line_table)
        self.line_table.itemSelectionChanged.connect(self.load_selected_line)
        line_layout.addWidget(line_table_label, 3, 0, 1, 5)
        line_layout.addWidget(self.line_table, 4, 0, 1, 5)
        layout.addWidget(line_group, 1)

    def refresh(self) -> None:
        with session_scope(self.session_factory) as session:
            service = ProductionResourceService(session)
            centers = service.list_work_centers()
            lines = service.list_production_lines()
            order_counts = dict(
                session.execute(
                    select(WorkOrder.production_line_id, func.count())
                    .where(WorkOrder.production_line_id.is_not(None))
                    .group_by(WorkOrder.production_line_id)
                ).all()
            )

            active_centers = [center for center in centers if center.is_active]
            active_lines = [
                line for line in lines if line.is_active and line.work_center.is_active
            ]
            assigned_orders = sum(order_counts.get(line.id, 0) for line in lines)

            clear_layout(self.metrics)
            for index, (label, value, unit) in enumerate(
                [
                    ("啟用工作中心", f"{len(active_centers)}/{len(centers)}", "個"),
                    ("啟用產線", f"{len(active_lines)}/{len(lines)}", "條"),
                    ("已指派工單", str(assigned_orders), "張"),
                ]
            ):
                self.metrics.addWidget(metric_panel(label, value, unit), 0, index)

            self._center_by_id = {
                center.id: {
                    "code": center.code,
                    "name": center.name,
                    "description": center.description or "",
                    "is_active": center.is_active,
                    "line_count": len(center.production_lines),
                }
                for center in centers
            }
            self._line_by_id = {
                line.id: {
                    "code": line.code,
                    "name": line.name,
                    "work_center_id": line.work_center_id,
                    "work_center": f"{line.work_center.code} - {line.work_center.name}",
                    "daily_capacity": format_decimal(line.daily_capacity),
                    "is_active": line.is_active,
                    "effective_status": (
                        "啟用"
                        if line.is_active and line.work_center.is_active
                        else "中心停用"
                        if line.is_active
                        else "停用"
                    ),
                    "order_count": order_counts.get(line.id, 0),
                }
                for line in lines
            }

            current_line_center_id = self.line_center.currentData()
            self.line_center.clear()
            for center in centers:
                self.line_center.addItem(f"{center.code} - {center.name}", center.id)
            if self.selected_line_id and self.selected_line_id in self._line_by_id:
                set_combo_current_data(
                    self.line_center,
                    self._line_by_id[self.selected_line_id]["work_center_id"],
                )
            elif current_line_center_id:
                set_combo_current_data(self.line_center, current_line_center_id)
            elif self.line_center.count() and self.line_center.currentIndex() < 0:
                self.line_center.setCurrentIndex(0)

            self.center_table.blockSignals(True)
            self.line_table.blockSignals(True)
            try:
                fill_table(
                    self.center_table,
                    [
                        [
                            "啟用" if center.is_active else "停用",
                            center.code,
                            center.name,
                            center.description or "尚未設定",
                            len(center.production_lines),
                        ]
                        for center in centers
                    ],
                    [center.id for center in centers],
                )
                fill_table(
                    self.line_table,
                    [
                        [
                            self._line_by_id[line.id]["effective_status"],
                            f"{line.work_center.code} {line.work_center.name}",
                            line.code,
                            line.name,
                            format_decimal(line.daily_capacity),
                            order_counts.get(line.id, 0),
                        ]
                        for line in lines
                    ],
                    [line.id for line in lines],
                )
                if self.selected_center_id is None:
                    self.center_table.clearSelection()
                elif self.selected_center_id not in self._center_by_id:
                    self.clear_center_form()
                if self.selected_line_id is None:
                    self.line_table.clearSelection()
                elif self.selected_line_id not in self._line_by_id:
                    self.clear_line_form()
            finally:
                self.center_table.blockSignals(False)
                self.line_table.blockSignals(False)

    def load_selected_center(self) -> None:
        if not self.center_table.selectedItems():
            return
        row = self.center_table.currentRow()
        if row < 0:
            return
        center_id = self.center_table.item(row, 0).data(Qt.UserRole)
        record = self._center_by_id.get(center_id)
        if not record:
            return
        self.selected_center_id = center_id
        self.center_code.setText(record["code"])
        self.center_name.setText(record["name"])
        self.center_desc.setText(record["description"])
        self.center_active.setChecked(record["is_active"])
        set_action_button(self.center_save_button, "edit", "修改工作中心")
        self.center_delete_button.setEnabled(True)

    def load_selected_line(self) -> None:
        if not self.line_table.selectedItems():
            return
        row = self.line_table.currentRow()
        if row < 0:
            return
        line_id = self.line_table.item(row, 0).data(Qt.UserRole)
        record = self._line_by_id.get(line_id)
        if not record:
            return
        self.selected_line_id = line_id
        set_combo_current_data(self.line_center, record["work_center_id"])
        self.line_code.setText(record["code"])
        self.line_name.setText(record["name"])
        self.line_capacity.setText(record["daily_capacity"])
        self.line_active.setChecked(record["is_active"])
        set_action_button(self.line_save_button, "edit", "修改產線")
        self.line_delete_button.setEnabled(True)

    def save_center(self) -> None:
        if not self.require_fields(
            [
                ("工作中心代碼", self.center_code),
                ("工作中心名稱", self.center_name),
            ]
        ):
            return
        is_update = self.selected_center_id is not None
        action_label = "修改" if is_update else "新增"
        center_code = self.center_code.text().strip().upper()
        if not self.confirm(
            f"確認{action_label}工作中心",
            f"代碼：{self.center_code.text().strip()}\n"
            f"名稱：{self.center_name.text().strip()}\n"
            f"狀態：{'啟用' if self.center_active.isChecked() else '停用'}\n\n"
            f"是否要{action_label}這筆工作中心資料？",
        ):
            return
        try:
            with session_scope(self.session_factory) as session:
                service = ProductionResourceService(session)
                if is_update and self.selected_center_id:
                    service.update_work_center(
                        self.selected_center_id,
                        self.center_code.text(),
                        self.center_name.text(),
                        self.center_desc.text(),
                        self.center_active.isChecked(),
                    )
                else:
                    center = service.create_work_center(
                        self.center_code.text(),
                        self.center_name.text(),
                        self.center_desc.text(),
                    )
                    center.is_active = self.center_active.isChecked()
            self.clear_center_form()
            self.refresh()
            self.message("操作完成", f"工作中心 {center_code} 已{action_label}")
        except DomainError as exc:
            self.error(exc)

    def save_line(self) -> None:
        if not self.require_fields(
            [
                ("工作中心", self.line_center),
                ("產線代碼", self.line_code),
                ("產線名稱", self.line_name),
            ]
        ):
            return
        is_update = self.selected_line_id is not None
        action_label = "修改" if is_update else "新增"
        line_code = self.line_code.text().strip().upper()
        if not self.confirm(
            f"確認{action_label}產線",
            f"工作中心：{self.line_center.currentText()}\n"
            f"產線代碼：{self.line_code.text().strip()}\n"
            f"產線名稱：{self.line_name.text().strip()}\n"
            f"每日產能：{self.line_capacity.text().strip() or '未設定'}\n"
            f"狀態：{'啟用' if self.line_active.isChecked() else '停用'}\n\n"
            f"是否要{action_label}這筆產線資料？",
        ):
            return
        try:
            with session_scope(self.session_factory) as session:
                service = ProductionResourceService(session)
                if is_update and self.selected_line_id:
                    service.update_production_line(
                        self.selected_line_id,
                        self.line_center.currentData(),
                        self.line_code.text(),
                        self.line_name.text(),
                        self.line_capacity.text(),
                        self.line_active.isChecked(),
                    )
                else:
                    line = service.create_production_line(
                        self.line_center.currentData(),
                        self.line_code.text(),
                        self.line_name.text(),
                        self.line_capacity.text(),
                    )
                    line.is_active = self.line_active.isChecked()
            self.clear_line_form()
            self.refresh()
            self.message("操作完成", f"產線 {line_code} 已{action_label}")
        except DomainError as exc:
            self.error(exc)

    def delete_center(self) -> None:
        if not self.selected_center_id:
            self.message("請先選擇資料", "請先在工作中心清單點選要刪除的工作中心。")
            return
        center_code = self.center_code.text().strip().upper()
        if not self.confirm(
            "確認刪除工作中心",
            f"代碼：{self.center_code.text().strip()}\n"
            f"名稱：{self.center_name.text().strip()}\n\n"
            "此操作無法刪除已有產線的工作中心；若已有關聯資料，請改用停用。\n"
            "是否確定刪除？",
        ):
            return
        try:
            with session_scope(self.session_factory) as session:
                ProductionResourceService(session).delete_work_center(self.selected_center_id)
            self.clear_center_form()
            self.refresh()
            self.message("刪除完成", f"工作中心 {center_code} 已刪除")
        except DomainError as exc:
            self.error(exc)

    def delete_line(self) -> None:
        if not self.selected_line_id:
            self.message("請先選擇資料", "請先在產線清單點選要刪除的產線。")
            return
        line_code = self.line_code.text().strip().upper()
        if not self.confirm(
            "確認刪除產線",
            f"產線代碼：{self.line_code.text().strip()}\n"
            f"產線名稱：{self.line_name.text().strip()}\n\n"
            "此操作無法刪除已有工單使用的產線；若已有關聯資料，請改用停用。\n"
            "是否確定刪除？",
        ):
            return
        try:
            with session_scope(self.session_factory) as session:
                ProductionResourceService(session).delete_production_line(self.selected_line_id)
            self.clear_line_form()
            self.refresh()
            self.message("刪除完成", f"產線 {line_code} 已刪除")
        except DomainError as exc:
            self.error(exc)

    def clear_center_form(self) -> None:
        self.selected_center_id = None
        self.center_code.clear()
        self.center_name.clear()
        self.center_desc.clear()
        self.center_active.setChecked(True)
        if hasattr(self, "center_table"):
            self.center_table.blockSignals(True)
            try:
                self.center_table.clearSelection()
            finally:
                self.center_table.blockSignals(False)
        set_action_button(self.center_save_button, "add", "新增工作中心")
        self.center_delete_button.setEnabled(False)

    def clear_line_form(self) -> None:
        self.selected_line_id = None
        if self.line_center.count():
            self.line_center.setCurrentIndex(0)
        self.line_code.clear()
        self.line_name.clear()
        self.line_capacity.clear()
        self.line_active.setChecked(True)
        if hasattr(self, "line_table"):
            self.line_table.blockSignals(True)
            try:
                self.line_table.clearSelection()
            finally:
                self.line_table.blockSignals(False)
        set_action_button(self.line_save_button, "add", "新增產線")
        self.line_delete_button.setEnabled(False)

    def create_center(self) -> None:
        self.save_center()

    def create_line(self) -> None:
        self.save_line()


class WorkOrdersPage(Page):
    def __init__(self, session_factory: sessionmaker) -> None:
        super().__init__(session_factory)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        form = panel()
        form_layout = QGridLayout(form)
        self.order_no = QLineEdit()
        self.order_no.setPlaceholderText("例如：WO-001")
        enable_uppercase_input(self.order_no)
        self.product_select = QComboBox()
        self.product_select.setPlaceholderText("請選擇產品")
        self.line_select = QComboBox()
        self.line_select.setPlaceholderText("暫不指派")
        self.qty = QLineEdit()
        self.qty.setPlaceholderText("例如：100")
        self.start_at = QLineEdit()
        self.end_at = QLineEdit()
        self.remark = QLineEdit()
        self.start_at.setPlaceholderText("YYYY-MM-DD HH:MM")
        self.end_at.setPlaceholderText("YYYY-MM-DD HH:MM")
        self.remark.setPlaceholderText("選填")
        add_labeled(form_layout, 0, "工單號碼", self.order_no, required=True)
        add_labeled(form_layout, 1, "產品", self.product_select, required=True)
        add_labeled(form_layout, 2, "產線", self.line_select)
        add_labeled(form_layout, 3, "預計數量", self.qty, required=True)
        add_labeled(form_layout, 4, "預計開工", self.start_at)
        add_labeled(form_layout, 5, "預計完工", self.end_at)
        add_labeled(form_layout, 6, "備註", self.remark)
        create_button = primary_button("新增工單")
        create_button.clicked.connect(self.create_work_order)
        form_layout.addWidget(create_button, 3, 0)
        layout.addWidget(form)

        self.table = make_table(["狀態", "工單", "產品", "產線", "預計數量", "良品", "預計期間"])
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        with session_scope(self.session_factory) as session:
            products = ProductService(session).list_products()
            lines = ProductionResourceService(session).list_production_lines(only_active=True)
            orders = WorkOrderService(session).list_work_orders()

            self.product_select.clear()
            for product in products:
                if product.is_active:
                    self.product_select.addItem(f"{product.code} - {product.name}", product.id)
            self.line_select.clear()
            self.line_select.addItem("暫不指派", None)
            for line in lines:
                self.line_select.addItem(
                    f"{line.work_center.code} / {line.code} - {line.name}",
                    line.id,
                )
            fill_table(
                self.table,
                [
                    [
                        STATUS_LABELS[WorkOrderStatus(order.status)],
                        order.order_no,
                        f"{order.product.code} {order.product.name}",
                        (
                            f"{order.production_line.work_center.code} / {order.production_line.code}"
                            if order.production_line
                            else "未指派"
                        ),
                        format_decimal(order.planned_qty),
                        format_decimal(sum(report.good_qty for report in order.reports)),
                        f"{format_dt(order.planned_start_at)} ～ {format_dt(order.planned_end_at)}",
                    ]
                    for order in orders
                ],
                [order.id for order in orders],
            )

    def create_work_order(self) -> None:
        if not self.require_fields(
            [
                ("工單號碼", self.order_no),
                ("產品", self.product_select),
                ("預計數量", self.qty),
            ]
        ):
            return
        try:
            planned_start_at = parse_datetime(self.start_at.text())
            planned_end_at = parse_datetime(self.end_at.text())
        except ValueError as exc:
            self.error(exc)
            return
        order_no = self.order_no.text().strip().upper()
        if not self.confirm(
            "確認新增工單",
            f"工單號碼：{self.order_no.text().strip()}\n"
            f"產品：{self.product_select.currentText()}\n"
            f"產線：{self.line_select.currentText() or '暫不指派'}\n"
            f"預計數量：{self.qty.text().strip()}\n"
            f"預計開工：{format_dt(planned_start_at)}\n"
            f"預計完工：{format_dt(planned_end_at)}\n\n"
            "是否要新增這張工單？",
        ):
            return
        try:
            with session_scope(self.session_factory) as session:
                WorkOrderService(session).create_work_order(
                    self.order_no.text(),
                    self.product_select.currentData(),
                    self.line_select.currentData(),
                    self.qty.text(),
                    planned_start_at,
                    planned_end_at,
                    self.remark.text(),
                )
            for widget in [self.order_no, self.qty, self.start_at, self.end_at, self.remark]:
                widget.clear()
            self.refresh()
            self.message("操作完成", f"工單 {order_no} 已新增")
        except DomainError as exc:
            self.error(exc)


class ReportsPage(Page):
    def __init__(self, session_factory: sessionmaker) -> None:
        super().__init__(session_factory)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        form = panel()
        form_layout = QGridLayout(form)
        self.work_order_select = QComboBox()
        self.work_order_select.setPlaceholderText("請選擇可報工工單")
        self.good_qty = QLineEdit()
        self.good_qty.setPlaceholderText("例如：100")
        self.defect_qty = QLineEdit("0")
        self.defect_qty.setPlaceholderText("例如：0")
        self.reporter = QLineEdit()
        self.reporter.setPlaceholderText("例如：王小明")
        self.note = QLineEdit()
        self.note.setPlaceholderText("選填")
        add_labeled(form_layout, 0, "工單", self.work_order_select, required=True)
        add_labeled(form_layout, 1, "良品數", self.good_qty, required=True)
        add_labeled(form_layout, 2, "不良數", self.defect_qty, required=True)
        add_labeled(form_layout, 3, "報工人員", self.reporter)
        add_labeled(form_layout, 4, "備註", self.note)
        create_button = primary_button("新增報工")
        create_button.clicked.connect(self.create_report)
        form_layout.addWidget(create_button, 2, 0)
        layout.addWidget(form)

        self.table = make_table(["時間", "工單", "良品", "不良", "報工人員", "備註"])
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        with session_scope(self.session_factory) as session:
            orders = WorkOrderService(session).list_work_orders()
            reports = ProductionReportService(session).list_reports()
            self.work_order_select.clear()
            for order in orders:
                if order.status in [WorkOrderStatus.PLANNED.value, WorkOrderStatus.IN_PROGRESS.value]:
                    self.work_order_select.addItem(f"{order.order_no} - {order.product.code}", order.id)
            fill_table(
                self.table,
                [
                    [
                        format_dt(report.reported_at),
                        report.work_order.order_no,
                        format_decimal(report.good_qty),
                        format_decimal(report.defect_qty),
                        report.reporter_name or "",
                        report.note or "",
                    ]
                    for report in reports
                ],
                [report.id for report in reports],
            )

    def create_report(self) -> None:
        if not self.require_fields(
            [
                ("工單", self.work_order_select),
                ("良品數", self.good_qty),
                ("不良數", self.defect_qty),
            ]
        ):
            return
        order_text = self.work_order_select.currentText()
        if not self.confirm(
            "確認新增報工",
            f"工單：{order_text}\n"
            f"良品數：{self.good_qty.text().strip()}\n"
            f"不良數：{self.defect_qty.text().strip()}\n"
            f"報工人員：{self.reporter.text().strip() or '未填寫'}\n\n"
            "是否要新增這筆報工資料？",
        ):
            return
        try:
            with session_scope(self.session_factory) as session:
                ProductionReportService(session).create_report(
                    self.work_order_select.currentData(),
                    self.good_qty.text(),
                    self.defect_qty.text(),
                    reporter_name=self.reporter.text(),
                    note=self.note.text(),
                )
            self.good_qty.clear()
            self.defect_qty.setText("0")
            self.reporter.clear()
            self.note.clear()
            self.refresh()
            self.message("操作完成", f"{order_text} 已新增報工")
        except DomainError as exc:
            self.error(exc)


class ProgressPage(Page):
    def __init__(self, session_factory: sessionmaker) -> None:
        super().__init__(session_factory)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        self.table = make_table(["狀態", "工單", "產品", "預計", "良品", "不良", "剩餘", "達成率", "良率"])
        layout.addWidget(self.table)

    def refresh(self) -> None:
        with session_scope(self.session_factory) as session:
            rows = ProgressService(session).list_progress()
            fill_table(
                self.table,
                [
                    [
                        STATUS_LABELS[row.status],
                        row.order_no,
                        f"{row.product_code} {row.product_name}",
                        f"{format_decimal(row.planned_qty)} {row.unit}",
                        format_decimal(row.good_qty),
                        format_decimal(row.defect_qty),
                        format_decimal(row.remaining_qty),
                        f"{row.completion_rate:.1f}%",
                        f"{row.yield_rate:.1f}%",
                    ]
                    for row in rows
                ],
                [row.id for row in rows],
            )


class SchedulePage(Page):
    def __init__(self, session_factory: sessionmaker) -> None:
        super().__init__(session_factory)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        self.table = make_table(["工單", "產品", "產線", "狀態", "良品 / 預計", "警示"])
        layout.addWidget(self.table)

    def refresh(self) -> None:
        with session_scope(self.session_factory) as session:
            rows = ScheduleService(session).list_schedule()
            fill_table(
                self.table,
                [
                    [
                        row.order_no,
                        row.product,
                        row.line,
                        STATUS_LABELS[row.status],
                        f"{format_decimal(row.good_qty)} / {format_decimal(row.planned_qty)}",
                        "、".join(alert.reason for alert in row.alerts) if row.alerts else "無",
                    ]
                    for row in rows
                ],
                [row.id for row in rows],
            )


def panel() -> QFrame:
    frame = QFrame()
    frame.setObjectName("Panel")
    return frame


def set_action_button(button: QPushButton, role: str, text: str) -> None:
    icons = {
        "add": "＋",
        "edit": "✎",
        "delete": "✕",
        "clear": "",
    }
    object_names = {
        "add": "AddButton",
        "edit": "EditButton",
        "delete": "DeleteButton",
        "clear": "ClearButton",
    }
    icon = icons[role]
    button.setText(f"{icon} {text}" if icon else text)
    button.setObjectName(object_names[role])
    button.setFixedWidth(ACTION_BUTTON_WIDTH)
    button.setFixedHeight(ACTION_BUTTON_HEIGHT)
    button.style().unpolish(button)
    button.style().polish(button)


def add_button(text: str) -> QPushButton:
    button = QPushButton()
    set_action_button(button, "add", text)
    return button


def edit_button(text: str) -> QPushButton:
    button = QPushButton()
    set_action_button(button, "edit", text)
    return button


def clear_button(text: str) -> QPushButton:
    button = QPushButton()
    set_action_button(button, "clear", text)
    return button


def primary_button(text: str) -> QPushButton:
    return add_button(text)


def secondary_button(text: str) -> QPushButton:
    return clear_button(text)


def danger_button(text: str) -> QPushButton:
    button = QPushButton()
    set_action_button(button, "delete", text)
    return button


def page_heading(eyebrow_text: str, title_text: str, description: str) -> QFrame:
    frame = panel()
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(8)

    eyebrow = QLabel(eyebrow_text)
    eyebrow.setObjectName("Eyebrow")
    title = QLabel(title_text)
    title.setObjectName("SectionTitle")
    copy = QLabel(description)
    copy.setObjectName("Muted")
    copy.setWordWrap(True)

    layout.addWidget(eyebrow)
    layout.addWidget(title)
    layout.addWidget(copy)
    return frame


def add_inline_field(
    layout: QGridLayout,
    column: int,
    label: str,
    widget: QWidget,
    *,
    required: bool = False,
) -> None:
    label_widget = QLabel(field_label_text(label, required))
    label_widget.setObjectName("FieldLabel")
    label_widget.setTextFormat(Qt.RichText)
    layout.addWidget(label_widget, 0, column)
    layout.addWidget(widget, 1, column)


def add_labeled(
    layout: QGridLayout,
    row: int,
    label: str,
    widget: QWidget,
    *,
    required: bool = False,
) -> None:
    label_widget = QLabel(field_label_text(label, required))
    label_widget.setObjectName("Muted")
    label_widget.setTextFormat(Qt.RichText)
    layout.addWidget(label_widget, row // 3 * 2, row % 3)
    layout.addWidget(widget, row // 3 * 2 + 1, row % 3)


def field_label_text(label: str, required: bool = False) -> str:
    if not required:
        return label
    return f"{label} <span style='color:#ff5c6c; font-weight:900;'>*</span>"


def missing_required_fields(fields: list[tuple[str, QWidget]]) -> list[str]:
    missing: list[str] = []
    for label, widget in fields:
        if isinstance(widget, QLineEdit):
            has_value = bool(widget.text().strip())
        elif isinstance(widget, QComboBox):
            has_value = widget.currentIndex() >= 0 and widget.currentData() is not None
        elif isinstance(widget, QCheckBox):
            has_value = widget.isChecked()
        else:
            has_value = True
        if not has_value:
            missing.append(label)
    return missing


def enable_uppercase_input(line_edit: QLineEdit) -> None:
    line_edit.textEdited.connect(lambda text: uppercase_line_edit_text(line_edit, text))


def uppercase_line_edit_text(line_edit: QLineEdit, text: str) -> None:
    upper_text = text.upper()
    if text == upper_text:
        return
    cursor_position = line_edit.cursorPosition()
    line_edit.blockSignals(True)
    try:
        line_edit.setText(upper_text)
        line_edit.setCursorPosition(cursor_position)
    finally:
        line_edit.blockSignals(False)


def set_combo_current_data(combo: QComboBox, value: Any) -> bool:
    for index in range(combo.count()):
        if combo.itemData(index) == value:
            combo.setCurrentIndex(index)
            return True
    return False


def make_table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(TABLE_ROW_HEIGHT)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    return table


def constrain_table_rows(table: QTableWidget, minimum_rows: int = 2, maximum_rows: int = 5) -> None:
    min_height = TABLE_HEADER_HEIGHT + TABLE_ROW_HEIGHT * minimum_rows + 12
    max_height = TABLE_HEADER_HEIGHT + TABLE_ROW_HEIGHT * maximum_rows + 12
    table.setMinimumHeight(min_height)
    table.setMaximumHeight(max_height)


def fill_table(table: QTableWidget, rows: list[list[Any]], row_ids: list[str] | None = None) -> None:
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            item = QTableWidgetItem(str(value))
            if row_ids and column_index == 0:
                item.setData(Qt.UserRole, row_ids[row_index])
            table.setItem(row_index, column_index, item)


def metric_panel(label: str, value: str, unit: str) -> QFrame:
    frame = panel()
    layout = QVBoxLayout(frame)
    title = QLabel(label)
    title.setObjectName("Muted")
    number = QLabel(f"{value} {unit}")
    number.setObjectName("PageTitle")
    layout.addWidget(title)
    layout.addWidget(number)
    return frame


def clear_layout(layout: QGridLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def parse_datetime(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    normalized = text.replace("/", "-").replace(" ", "T")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        raise ValueError("日期時間格式請使用 YYYY-MM-DD HH:MM") from None


def format_decimal(value: Decimal | int | float | None) -> str:
    if value is None:
        return ""
    return f"{Decimal(value):,.3f}".rstrip("0").rstrip(".")


def format_dt(value: datetime | None) -> str:
    if value is None:
        return "未設定"
    return value.strftime("%Y-%m-%d %H:%M")
