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
    window.resize(1440, 900)
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
        eyebrow = QLabel("MANUFACTURING EXECUTION SYSTEM")
        eyebrow.setObjectName("Eyebrow")
        title_block.addWidget(eyebrow)
        title_block.addWidget(self.title_label)
        layout.addLayout(title_block)
        layout.addStretch(1)

        user_label = QLabel(f"{self.user.name}  |  {self.user.email}")
        user_label.setObjectName("Muted")
        layout.addWidget(user_label)
        return topbar

    def show_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.title_label.setText(self.pages[index][0])
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)
        page = self.stack.widget(index)
        if hasattr(page, "refresh"):
            page.refresh()


class Page(QWidget):
    def __init__(self, session_factory: sessionmaker) -> None:
        super().__init__()
        self.session_factory = session_factory

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
    def __init__(self, session_factory: sessionmaker) -> None:
        super().__init__(session_factory)
        self.selected_id: str | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        heading = page_heading(
            "MES / PRODUCT MASTER",
            "產品管理",
            "維護可投入工單的產品主檔。產品料號會自動轉成大寫，停用產品仍會保留歷史資料關聯。",
        )
        layout.addWidget(heading)

        form = panel()
        form_layout = QGridLayout(form)
        form_layout.setContentsMargins(18, 18, 18, 18)
        form_layout.setHorizontalSpacing(16)
        form_layout.setVerticalSpacing(10)
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("例如：FG-001")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("例如：測試成品")
        self.spec_input = QLineEdit()
        self.spec_input.setPlaceholderText("選填")
        self.unit_input = QLineEdit("PCS")
        self.unit_input.setPlaceholderText("PCS")
        self.active_input = QCheckBox("啟用")
        self.active_input.setChecked(True)
        add_inline_field(form_layout, 0, "產品料號", self.code_input)
        add_inline_field(form_layout, 1, "產品名稱", self.name_input)
        add_inline_field(form_layout, 2, "規格", self.spec_input)
        add_inline_field(form_layout, 3, "單位", self.unit_input)
        add_inline_field(form_layout, 4, "狀態", self.active_input)
        form_layout.setColumnStretch(0, 1)
        form_layout.setColumnStretch(1, 2)
        form_layout.setColumnStretch(2, 2)
        form_layout.setColumnStretch(3, 1)
        form_layout.setColumnStretch(4, 1)

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 10, 0, 0)
        action_layout.setSpacing(10)
        self.save_button = primary_button("儲存產品")
        self.clear_button = secondary_button("清除表單")
        self.delete_button = danger_button("刪除產品")
        self.delete_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_product)
        self.clear_button.clicked.connect(self.clear_form)
        self.delete_button.clicked.connect(self.delete_product)
        action_layout.addWidget(self.save_button, 1)
        action_layout.addWidget(self.clear_button)
        action_layout.addWidget(self.delete_button)
        form_layout.addLayout(action_layout, 2, 0, 1, 5)
        layout.addWidget(form)

        self.table = make_table(["狀態", "料號", "名稱", "規格", "單位"])
        self.table.itemSelectionChanged.connect(self.load_selected)
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        with session_scope(self.session_factory) as session:
            products = ProductService(session).list_products()
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

    def load_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        self.selected_id = self.table.item(row, 0).data(Qt.UserRole)
        self.active_input.setChecked(self.table.item(row, 0).text() == "啟用")
        self.code_input.setText(self.table.item(row, 1).text())
        self.name_input.setText(self.table.item(row, 2).text())
        self.spec_input.setText(self.table.item(row, 3).text())
        self.unit_input.setText(self.table.item(row, 4).text())
        self.save_button.setText("修改產品")
        self.delete_button.setEnabled(True)

    def save_product(self) -> None:
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
        has_content = any(
            widget.text().strip()
            for widget in [self.code_input, self.name_input, self.spec_input, self.unit_input]
        )
        if self.selected_id or has_content:
            if not self.confirm("確認清除表單", "是否清除目前產品表單內容？"):
                return
            show_result = True
        else:
            show_result = False

        self._reset_form()
        if show_result:
            self.message("表單已清除", "產品表單已回到新增模式。")

    def _reset_form(self) -> None:
        self.selected_id = None
        for widget in [self.code_input, self.name_input, self.spec_input]:
            widget.clear()
        self.unit_input.setText("PCS")
        self.active_input.setChecked(True)
        self.table.clearSelection()
        self.save_button.setText("儲存產品")
        self.delete_button.setEnabled(False)


class ResourcesPage(Page):
    def __init__(self, session_factory: sessionmaker) -> None:
        super().__init__(session_factory)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        form_row = QHBoxLayout()
        center_group = QGroupBox("工作中心")
        center_layout = QGridLayout(center_group)
        self.center_code = QLineEdit()
        self.center_code.setPlaceholderText("例如：WC-001")
        self.center_name = QLineEdit()
        self.center_name.setPlaceholderText("例如：組裝中心")
        self.center_desc = QLineEdit()
        self.center_desc.setPlaceholderText("選填，例如：一樓組裝區")
        add_labeled(center_layout, 0, "代碼", self.center_code)
        add_labeled(center_layout, 1, "名稱", self.center_name)
        add_labeled(center_layout, 2, "說明", self.center_desc)
        center_button = primary_button("新增工作中心")
        center_button.clicked.connect(self.create_center)
        center_layout.addWidget(center_button, 3, 0, 1, 2)
        form_row.addWidget(center_group)

        line_group = QGroupBox("產線")
        line_layout = QGridLayout(line_group)
        self.line_center = QComboBox()
        self.line_center.setPlaceholderText("請選擇工作中心")
        self.line_code = QLineEdit()
        self.line_code.setPlaceholderText("例如：LINE-01")
        self.line_name = QLineEdit()
        self.line_name.setPlaceholderText("例如：A 線")
        self.line_capacity = QLineEdit()
        self.line_capacity.setPlaceholderText("例如：1000")
        add_labeled(line_layout, 0, "工作中心", self.line_center)
        add_labeled(line_layout, 1, "產線代碼", self.line_code)
        add_labeled(line_layout, 2, "產線名稱", self.line_name)
        add_labeled(line_layout, 3, "每日產能", self.line_capacity)
        line_button = primary_button("新增產線")
        line_button.clicked.connect(self.create_line)
        line_layout.addWidget(line_button, 4, 0, 1, 2)
        form_row.addWidget(line_group)
        layout.addLayout(form_row)

        self.table = make_table(["工作中心", "產線", "名稱", "每日產能", "狀態"])
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        with session_scope(self.session_factory) as session:
            service = ProductionResourceService(session)
            centers = service.list_work_centers()
            self.line_center.clear()
            for center in centers:
                self.line_center.addItem(f"{center.code} - {center.name}", center.id)
            lines = service.list_production_lines()
            fill_table(
                self.table,
                [
                    [
                        f"{line.work_center.code} {line.work_center.name}",
                        line.code,
                        line.name,
                        format_decimal(line.daily_capacity),
                        "啟用" if line.is_active and line.work_center.is_active else "停用",
                    ]
                    for line in lines
                ],
                [line.id for line in lines],
            )

    def create_center(self) -> None:
        try:
            with session_scope(self.session_factory) as session:
                ProductionResourceService(session).create_work_center(
                    self.center_code.text(), self.center_name.text(), self.center_desc.text()
                )
            self.center_code.clear()
            self.center_name.clear()
            self.center_desc.clear()
            self.refresh()
        except DomainError as exc:
            self.error(exc)

    def create_line(self) -> None:
        try:
            with session_scope(self.session_factory) as session:
                ProductionResourceService(session).create_production_line(
                    self.line_center.currentData(),
                    self.line_code.text(),
                    self.line_name.text(),
                    self.line_capacity.text(),
                )
            self.line_code.clear()
            self.line_name.clear()
            self.line_capacity.clear()
            self.refresh()
        except DomainError as exc:
            self.error(exc)


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
        add_labeled(form_layout, 0, "工單號碼", self.order_no)
        add_labeled(form_layout, 1, "產品", self.product_select)
        add_labeled(form_layout, 2, "產線", self.line_select)
        add_labeled(form_layout, 3, "預計數量", self.qty)
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
        try:
            with session_scope(self.session_factory) as session:
                WorkOrderService(session).create_work_order(
                    self.order_no.text(),
                    self.product_select.currentData(),
                    self.line_select.currentData(),
                    self.qty.text(),
                    parse_datetime(self.start_at.text()),
                    parse_datetime(self.end_at.text()),
                    self.remark.text(),
                )
            for widget in [self.order_no, self.qty, self.start_at, self.end_at, self.remark]:
                widget.clear()
            self.refresh()
        except (DomainError, ValueError) as exc:
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
        add_labeled(form_layout, 0, "工單", self.work_order_select)
        add_labeled(form_layout, 1, "良品數", self.good_qty)
        add_labeled(form_layout, 2, "不良數", self.defect_qty)
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


def primary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("PrimaryButton")
    return button


def secondary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("SecondaryButton")
    return button


def danger_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("DangerButton")
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


def add_inline_field(layout: QGridLayout, column: int, label: str, widget: QWidget) -> None:
    label_widget = QLabel(label)
    label_widget.setObjectName("FieldLabel")
    layout.addWidget(label_widget, 0, column)
    layout.addWidget(widget, 1, column)


def add_labeled(layout: QGridLayout, row: int, label: str, widget: QWidget) -> None:
    label_widget = QLabel(label)
    label_widget.setObjectName("Muted")
    layout.addWidget(label_widget, row // 3 * 2, row % 3)
    layout.addWidget(widget, row // 3 * 2 + 1, row % 3)


def make_table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    return table


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
