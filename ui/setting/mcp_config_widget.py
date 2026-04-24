from __future__ import annotations

import json
import os
from concurrent.futures import Future
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import APP_RUNTIME, APP_SETTINGS, ConfigManager
from core.tool_call.mcp.async_runner import McpAsyncRunner
from core.tool_call.tool_core import get_tools_event_bus


class JsonEditorDialog(QDialog):
    def __init__(self, title: str, initial_text: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 520)

        layout = QVBoxLayout(self)
        self.editor = QPlainTextEdit(self)
        self.editor.setPlainText(initial_text)
        layout.addWidget(self.editor, 1)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    def text(self) -> str:
        return self.editor.toPlainText()


class MCPConfigWidget(QWidget):
    configUpdated = pyqtSignal()
    notificationRequested = pyqtSignal(str, str)
    _taskFinished = pyqtSignal(str, object)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._servers: List[Dict[str, Any]] = []
        self._current_index: int = -1
        self._runner = McpAsyncRunner(max_workers=4)
        self._task_seq = 0
        self._inflight: Dict[str, str] = {}
        self._modified = False
        self._tools_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._loading_form = False

        self._build_ui()
        self._load_from_settings()
        self._taskFinished.connect(self._on_task_finished)

    def _build_ui(self):
        self.setWindowTitle("MCP 配置管理")
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        width = int(screen_geometry.width() * 0.78)
        height = int(screen_geometry.height() * 0.86)
        left = screen_geometry.left() + (screen_geometry.width() - width) // 2
        top = screen_geometry.top() + (screen_geometry.height() - height) // 2
        self.setGeometry(left, top, width, height)

        root = QVBoxLayout(self)

        self.disabled_container = QWidget()
        disabled_layout = QVBoxLayout(self.disabled_container)
        disabled_layout.setContentsMargins(32, 32, 32, 32)
        disabled_layout.setSpacing(16)
        disabled_layout.addStretch(1)
        self.disabled_hint = QLabel("MCP 当前未启用")
        self.disabled_hint.setObjectName("mcpDisabledHint")
        self.disabled_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.disabled_enable_checkbox = QCheckBox("启用 MCP")
        self.disabled_enable_checkbox.setObjectName("mcpDisabledEnableCheckbox")
        disabled_layout.addWidget(self.disabled_hint, 0, Qt.AlignmentFlag.AlignHCenter)
        disabled_layout.addWidget(
            self.disabled_enable_checkbox, 0, Qt.AlignmentFlag.AlignHCenter
        )
        disabled_layout.addStretch(1)
        root.addWidget(self.disabled_container)

        self.main_container = QWidget()
        main_root = QVBoxLayout(self.main_container)
        main_root.setContentsMargins(0, 0, 0, 0)

        top_bar_widget = QWidget()
        top_bar_widget.setObjectName("mcpTopBar")
        top_bar = QHBoxLayout(top_bar_widget)
        top_bar.setContentsMargins(18, 12, 18, 12)
        top_bar.setSpacing(12)

        brand_widget = QWidget()
        brand_layout = QHBoxLayout(brand_widget)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(10)
        self.logo_label = QLabel("M")
        self.logo_label.setObjectName("mcpLogoLabel")
        self.title_label = QLabel("MCP Manager")
        self.title_label.setObjectName("mcpTitleLabel")
        brand_layout.addWidget(self.logo_label)
        brand_layout.addWidget(self.title_label)

        breadcrumb_widget = QWidget()
        breadcrumb_layout = QHBoxLayout(breadcrumb_widget)
        breadcrumb_layout.setContentsMargins(0, 0, 0, 0)
        breadcrumb_layout.setSpacing(6)
        self.breadcrumb_label = QLabel("配置")
        self.breadcrumb_sep_label = QLabel("/")
        self.breadcrumb_current_label = QLabel("全局设置")
        self.breadcrumb_label.setObjectName("mcpBreadcrumbLabel")
        self.breadcrumb_sep_label.setObjectName("mcpBreadcrumbSepLabel")
        self.breadcrumb_current_label.setObjectName("mcpBreadcrumbCurrentLabel")
        breadcrumb_layout.addWidget(self.breadcrumb_label)
        breadcrumb_layout.addWidget(self.breadcrumb_sep_label)
        breadcrumb_layout.addWidget(self.breadcrumb_current_label)

        self.global_enabled = QCheckBox("启用 MCP")
        self.refresh_on_startup = QCheckBox("启动时刷新")
        self.status_label = QLabel("所有更改已保存")
        self.status_label.setObjectName("mcpStatusLabel")
        self.btn_edit_json = QPushButton("编辑原 JSON")
        self.btn_save = QPushButton("保存并应用")
        self.btn_close = QPushButton("关闭窗口")

        top_bar.addWidget(brand_widget)
        top_bar.addWidget(breadcrumb_widget)
        top_bar.addSpacing(12)
        top_bar.addWidget(self.global_enabled)
        top_bar.addWidget(self.refresh_on_startup)
        top_bar.addStretch(1)
        top_bar.addWidget(self.btn_edit_json)
        main_root.addWidget(top_bar_widget)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setObjectName("mcpMainSplitter")

        left_panel = QWidget()
        left_panel.setObjectName("mcpLeftPanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_header_widget = QWidget()
        left_header_widget.setObjectName("mcpLeftHeader")
        left_header = QVBoxLayout(left_header_widget)
        left_header.setContentsMargins(16, 16, 16, 12)
        left_header.setSpacing(12)

        left_title_row = QHBoxLayout()
        left_title_row.setSpacing(8)
        self.server_title_label = QLabel("MCP Servers")
        self.server_title_label.setObjectName("mcpServerTitleLabel")
        self.server_count_label = QLabel("0")
        self.server_count_label.setObjectName("mcpServerCountLabel")
        self.btn_refresh_all = QPushButton("刷新所有")
        self.btn_add = QPushButton("添加")
        self.btn_remove = QPushButton("删除")
        left_title_row.addWidget(self.server_title_label)
        left_title_row.addWidget(self.server_count_label)
        left_title_row.addStretch(1)
        left_title_row.addWidget(self.btn_refresh_all)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索服务器...")
        self.search_edit.setObjectName("mcpSearchEdit")

        left_header.addLayout(left_title_row)
        left_header.addWidget(self.search_edit)
        left_layout.addWidget(left_header_widget)

        self.server_list = QListWidget()
        self.server_list.setObjectName("mcpServerList")
        self.server_list.setFrameShape(QFrame.Shape.NoFrame)
        self.server_list.setSpacing(8)
        self.server_list.setAlternatingRowColors(False)
        self.server_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        left_layout.addWidget(self.server_list, 1)

        left_bottom_widget = QWidget()
        left_bottom = QHBoxLayout(left_bottom_widget)
        left_bottom.setContentsMargins(0, 0, 0, 0)
        left_bottom.addWidget(self.btn_add, 1)
        left_bottom.addWidget(self.btn_remove, 1)
        left_layout.addWidget(left_bottom_widget)

        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_panel.setObjectName("mcpRightPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.right_scroll = QScrollArea()
        self.right_scroll.setObjectName("mcpRightScroll")
        self.right_scroll.setWidgetResizable(True)
        self.right_scroll.setFrameShape(QFrame.Shape.NoFrame)

        detail_container = QWidget()
        detail_container.setObjectName("mcpDetailContainer")
        self.detail_layout = QVBoxLayout(detail_container)
        self.detail_layout.setContentsMargins(28, 28, 28, 24)
        self.detail_layout.setSpacing(22)

        hero = QGroupBox()
        hero.setObjectName("mcpHeroCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(0, 0, 0, 0)
        hero_layout.setSpacing(18)

        self.hero_icon = QLabel("M")
        self.hero_icon.setObjectName("mcpHeroIcon")
        self.hero_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hero_icon.setFixedSize(56, 56)

        hero_left = QVBoxLayout()
        hero_left.setSpacing(8)
        self.hero_name = QLabel("-")
        self.hero_name.setObjectName("mcpHeroName")
        self.hero_desc = QLabel("选择一个 MCP server 查看详情")
        self.hero_desc.setObjectName("mcpHeroDesc")
        self.hero_desc.setWordWrap(True)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        badge_row.setContentsMargins(0, 0, 0, 0)
        self.hero_enabled_badge = QLabel("未启用")
        self.hero_enabled_badge.setObjectName("mcpHeroEnabledBadge")
        self.hero_transport_badge = QLabel("-")
        self.hero_transport_badge.setObjectName("mcpHeroTransportBadge")
        self.hero_tools_badge = QLabel("工具 0")
        self.hero_tools_badge.setObjectName("mcpHeroToolsBadge")
        badge_row.addWidget(self.hero_enabled_badge)
        badge_row.addWidget(self.hero_transport_badge)
        badge_row.addWidget(self.hero_tools_badge)
        badge_row.addStretch(1)

        hero_left.addWidget(self.hero_name)
        hero_left.addWidget(self.hero_desc)
        hero_left.addLayout(badge_row)

        hero_right = QVBoxLayout()
        hero_right.setSpacing(8)
        self.server_enabled = QCheckBox("启用此 server")
        self.btn_preview_current = QPushButton("刷新工具列表")
        hero_right.addWidget(self.server_enabled, 0, Qt.AlignmentFlag.AlignRight)
        hero_right.addWidget(self.btn_preview_current)
        hero_right.addStretch(1)

        hero_layout.addWidget(self.hero_icon, 0, Qt.AlignmentFlag.AlignTop)
        hero_layout.addLayout(hero_left, 1)
        hero_layout.addLayout(hero_right)
        self.detail_layout.addWidget(hero)

        advanced_group = QGroupBox()
        advanced_group.setObjectName("mcpGlobalSection")
        advanced_outer = QVBoxLayout(advanced_group)
        advanced_outer.setContentsMargins(0, 0, 0, 0)
        advanced_outer.setSpacing(12)

        advanced_header = QHBoxLayout()
        advanced_header.setContentsMargins(0, 0, 0, 0)
        self.global_title_label = QLabel("全局设置")
        self.global_title_label.setObjectName("mcpSectionTitle")
        self.global_desc_label = QLabel("MCP 管理器通用行为")
        self.global_desc_label.setObjectName("mcpSectionDesc")
        advanced_header.addWidget(self.global_title_label)
        advanced_header.addStretch(1)
        advanced_header.addWidget(self.global_desc_label)

        self.conflict_combo = QComboBox()
        self.conflict_combo.addItems(["prefix", "skip", "error"])

        advanced_form = QFormLayout()
        advanced_form.setContentsMargins(0, 0, 0, 0)
        advanced_form.setSpacing(10)
        advanced_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        advanced_form.addRow("冲突策略", self.conflict_combo)

        advanced_outer.addLayout(advanced_header)
        advanced_outer.addLayout(advanced_form)
        self.detail_layout.addWidget(advanced_group)

        conn_group = QGroupBox()
        conn_group.setObjectName("mcpConnSection")
        conn_outer = QVBoxLayout(conn_group)
        conn_outer.setContentsMargins(0, 0, 0, 0)
        conn_outer.setSpacing(12)

        conn_header = QHBoxLayout()
        conn_header.setContentsMargins(0, 0, 0, 0)
        self.conn_title_label = QLabel("连接配置")
        self.conn_title_label.setObjectName("mcpSectionTitle")
        self.conn_desc_label = QLabel("传输方式与端点设置")
        self.conn_desc_label.setObjectName("mcpSectionDesc")
        conn_header.addWidget(self.conn_title_label)
        conn_header.addStretch(1)
        conn_header.addWidget(self.conn_desc_label)

        conn_grid = QGridLayout()
        conn_grid.setContentsMargins(0, 0, 0, 0)
        conn_grid.setHorizontalSpacing(14)
        conn_grid.setVerticalSpacing(10)
        conn_grid.setColumnStretch(1, 1)
        conn_grid.setColumnStretch(3, 1)

        self.edit_name = QLineEdit()
        self.edit_url = QLineEdit()
        self.edit_url.setPlaceholderText("https://example.com/mcp")
        self.edit_command = QLineEdit()
        self.edit_args = QLineEdit()
        self.edit_args.setPlaceholderText(
            '["-y", "@modelcontextprotocol/server-filesystem", "."]'
        )
        self.edit_env = QPlainTextEdit()
        self.edit_env.setObjectName("mcpEnvEdit")
        self.edit_env.setMinimumHeight(96)
        self.edit_cwd = QLineEdit()
        self.edit_transport = QComboBox()
        self.edit_transport.addItems(["stdio", "streamable_http", "sse"])
        self.edit_timeout = QDoubleSpinBox()
        self.edit_timeout.setRange(1.0, 600.0)
        self.edit_timeout.setDecimals(1)
        self.edit_timeout.setValue(30.0)

        self.lbl_name = QLabel("名称")
        self.lbl_timeout = QLabel("超时时间 秒")
        self.lbl_transport = QLabel("传输协议")
        self.lbl_cwd = QLabel("工作目录")
        self.lbl_url = QLabel("远程端点 URL")
        self.lbl_command = QLabel("命令")
        self.lbl_args = QLabel("参数（列表）")
        self.lbl_env = QLabel("环境变量 JSON 对象")

        conn_grid.addWidget(self.lbl_name, 0, 0)
        conn_grid.addWidget(self.edit_name, 0, 1)
        conn_grid.addWidget(self.lbl_timeout, 0, 2)
        conn_grid.addWidget(self.edit_timeout, 0, 3)
        conn_grid.addWidget(self.lbl_transport, 1, 0)
        conn_grid.addWidget(self.edit_transport, 1, 1)
        conn_grid.addWidget(self.lbl_cwd, 1, 2)
        conn_grid.addWidget(self.edit_cwd, 1, 3)
        conn_grid.addWidget(self.lbl_url, 2, 0)
        conn_grid.addWidget(self.edit_url, 2, 1, 1, 3)
        conn_grid.addWidget(self.lbl_command, 3, 0)
        conn_grid.addWidget(self.edit_command, 3, 1, 1, 3)
        conn_grid.addWidget(self.lbl_args, 4, 0)
        conn_grid.addWidget(self.edit_args, 4, 1, 1, 3)
        conn_grid.addWidget(self.lbl_env, 5, 0)
        conn_grid.addWidget(self.edit_env, 5, 1, 1, 3)

        conn_outer.addLayout(conn_header)
        conn_outer.addLayout(conn_grid)
        self.detail_layout.addWidget(conn_group)

        tool_group = QGroupBox()
        tool_group.setObjectName("mcpToolSection")
        tool_outer = QVBoxLayout(tool_group)
        tool_outer.setContentsMargins(0, 0, 0, 0)
        tool_outer.setSpacing(12)

        tool_header = QHBoxLayout()
        tool_header.setContentsMargins(0, 0, 0, 0)
        self.tool_title_label = QLabel("工具预览")
        self.tool_title_label.setObjectName("mcpSectionTitle")
        self.tool_desc_label = QLabel("当前服务提供的工具")
        self.tool_desc_label.setObjectName("mcpSectionDesc")
        tool_header.addWidget(self.tool_title_label)
        tool_header.addStretch(1)
        tool_header.addWidget(self.tool_desc_label)

        self.preview_table = QTableWidget(0, 4)
        self.preview_table.setObjectName("mcpPreviewTable")
        self.preview_table.setHorizontalHeaderLabels(
            ["Server", "Tool", "Description", "Schema"]
        )
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.preview_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.preview_table.setShowGrid(False)
        self.preview_table.setWordWrap(True)
        self.preview_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.preview_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.preview_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.preview_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )

        tool_outer.addLayout(tool_header)
        tool_outer.addWidget(self.preview_table, 1)
        self.detail_layout.addWidget(tool_group, 1)

        self.right_scroll.setWidget(detail_container)
        right_layout.addWidget(self.right_scroll, 1)

        bottom_bar_widget = QWidget()
        bottom_bar_widget.setObjectName("mcpBottomBar")
        bottom_bar = QHBoxLayout(bottom_bar_widget)
        bottom_bar.setContentsMargins(18, 14, 18, 14)
        bottom_bar.setSpacing(10)
        self.status_dot = QFrame()
        self.status_dot.setObjectName("mcpStatusDot")
        self.status_dot.setFixedSize(8, 8)
        bottom_bar.addWidget(self.status_dot)
        bottom_bar.addWidget(self.status_label)
        bottom_bar.addStretch(1)
        bottom_bar.addWidget(self.btn_save)
        bottom_bar.addWidget(self.btn_close)
        right_layout.addWidget(bottom_bar_widget)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, max(700, width - 300)])
        main_root.addWidget(splitter, 1)
        root.addWidget(self.main_container, 1)

        self.btn_close.clicked.connect(self.close)
        self.btn_edit_json.clicked.connect(self._edit_raw_json)
        self.btn_save.clicked.connect(self._save_and_apply)
        self.btn_add.clicked.connect(self._add_server)
        self.btn_remove.clicked.connect(self._remove_server)
        self.btn_refresh_all.clicked.connect(self._refresh_all_servers)
        self.server_list.currentRowChanged.connect(self._on_server_selected)
        self.server_list.itemChanged.connect(self._on_server_item_changed)
        self.search_edit.textChanged.connect(self._refresh_server_list)
        self.edit_transport.currentTextChanged.connect(self._on_transport_changed)
        self.edit_name.textChanged.connect(self._on_form_field_changed)
        self.edit_url.textChanged.connect(self._on_form_field_changed)
        self.edit_command.textChanged.connect(self._on_form_field_changed)
        self.edit_args.textChanged.connect(self._on_form_field_changed)
        self.edit_env.textChanged.connect(self._on_form_field_changed)
        self.edit_cwd.textChanged.connect(self._on_form_field_changed)
        self.edit_timeout.valueChanged.connect(self._on_form_field_changed)
        self.btn_preview_current.clicked.connect(self._preview_current_server)
        self.server_enabled.stateChanged.connect(self._on_server_enabled_changed)
        self.global_enabled.stateChanged.connect(self._on_global_enabled_changed)
        self.disabled_enable_checkbox.stateChanged.connect(
            self._on_disabled_enable_changed
        )
        self.refresh_on_startup.stateChanged.connect(lambda _: self._mark_modified())
        self.conflict_combo.currentTextChanged.connect(lambda _: self._mark_modified())
        self._mark_saved()

    def _update_server_list_item_widget(
        self, item: QListWidgetItem, srv: Dict[str, Any]
    ):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        name_label = QLabel(str(srv.get("name") or "<unnamed>"))
        name_label.setObjectName("mcpServerItemName")
        status = QLabel("●")
        status.setObjectName("mcpServerItemStatus")
        status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top_row.addWidget(name_label, 1)
        top_row.addWidget(status)

        type_label = QLabel(str(srv.get("transport", "stdio") or "stdio").upper())
        type_label.setObjectName("mcpServerItemDesc")

        layout.addLayout(top_row)
        layout.addWidget(type_label)
        item.setSizeHint(widget.sizeHint())
        self.server_list.setItemWidget(item, widget)

    def _sync_hero_badges(self, server: Optional[Dict[str, Any]] = None):
        s = server or {}
        enabled = bool(s.get("enabled", False))
        self.hero_enabled_badge.setText("已连接" if enabled else "未启用")
        self.hero_transport_badge.setText(str(s.get("transport", "-") or "-").upper())
        tool_count = s.get("tool_count")
        if tool_count is None:
            self.hero_tools_badge.setText("工具预览")
        else:
            self.hero_tools_badge.setText(f"{tool_count} 个工具")

    def _set_main_visible(self, enabled: bool):
        self.main_container.setVisible(enabled)
        self.disabled_container.setVisible(not enabled)
        self.disabled_enable_checkbox.blockSignals(True)
        self.disabled_enable_checkbox.setChecked(enabled)
        self.disabled_enable_checkbox.blockSignals(False)

    def _on_global_enabled_changed(self, _state: int):
        enabled = bool(self.global_enabled.isChecked())
        self._set_main_visible(enabled)
        self._mark_modified()

    def _on_disabled_enable_changed(self, _state: int):
        enabled = bool(self.disabled_enable_checkbox.isChecked())
        self.global_enabled.blockSignals(True)
        self.global_enabled.setChecked(enabled)
        self.global_enabled.blockSignals(False)
        self._set_main_visible(enabled)
        self._mark_modified()

    def _refresh_all_servers(self):
        if self._current_index >= 0 and not self._apply_current_server_from_form():
            return
        self._set_busy(True)
        self._submit_task(
            "preview_enabled",
            self._runner.submit_preview_servers(self._servers, enabled_only=True),
        )

    def closeEvent(self, event):
        try:
            self._runner.shutdown(wait=False)
        except Exception:
            pass
        super().closeEvent(event)

    def _mark_modified(self):
        self._modified = True
        self.status_label.setText("有未保存的更改")
        if hasattr(self, "status_dot"):
            self.status_dot.setProperty("state", "modified")
            self.status_dot.style().unpolish(self.status_dot)
            self.status_dot.style().polish(self.status_dot)

    def _mark_saved(self):
        self._modified = False
        self.status_label.setText("所有更改已保存")
        if hasattr(self, "status_dot"):
            self.status_dot.setProperty("state", "saved")
            self.status_dot.style().unpolish(self.status_dot)
            self.status_dot.style().polish(self.status_dot)

    def _load_from_settings(self):
        cfg = APP_SETTINGS.mcp
        self.global_enabled.blockSignals(True)
        self.disabled_enable_checkbox.blockSignals(True)
        self.global_enabled.setChecked(bool(cfg.enabled))
        self.disabled_enable_checkbox.setChecked(bool(cfg.enabled))
        self.global_enabled.blockSignals(False)
        self.disabled_enable_checkbox.blockSignals(False)
        self._set_main_visible(bool(cfg.enabled))
        self.refresh_on_startup.setChecked(
            bool(getattr(cfg, "refresh_tools_on_startup", False))
        )
        self.conflict_combo.setCurrentText(str(cfg.name_conflict_policy or "prefix"))
        self._servers = [
            s.model_dump(mode="json", exclude_none=False) for s in cfg.servers
        ]
        self._tools_cache = self._load_tools_cache_data()
        for srv in self._servers:
            name = str(srv.get("name") or "").strip()
            srv["tool_count"] = len(self._tools_cache.get(name, [])) if name else 0
        self._refresh_server_list()
        self._mark_saved()
        if cfg.enabled and self._current_index >= 0:
            self._show_cached_preview_for_current()

    def _cache_file_path(self) -> str:
        return os.path.join(APP_RUNTIME.paths.config_path, "mcp_tools_cache.json")

    def _load_tools_cache_data(self) -> Dict[str, List[Dict[str, Any]]]:
        fp = self._cache_file_path()
        if not os.path.exists(fp):
            return {}
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            out: Dict[str, List[Dict[str, Any]]] = {}
            for k, v in data.items():
                if isinstance(k, str) and isinstance(v, list):
                    out[k] = [item for item in v if isinstance(item, dict)]
            return out
        except Exception:
            return {}

    def _cached_preview_rows_for_server(self, server_name: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for item in self._tools_cache.get(server_name, []) or []:
            rows.append(
                {
                    "server": server_name,
                    "name": item.get("name", ""),
                    "description": item.get("description", ""),
                    "schema": item.get("inputSchema") or item.get("parameters") or {},
                }
            )
        return rows

    def _show_cached_preview_for_current(self):
        srv = self._current_server_payload()
        if not srv:
            self.preview_table.setRowCount(0)
            return
        server_name = str(srv.get("name") or "").strip()
        if not server_name:
            self.preview_table.setRowCount(0)
            return
        self._set_preview_rows(self._cached_preview_rows_for_server(server_name))

    def _set_busy(self, busy: bool):
        self.btn_preview_current.setEnabled(not busy)
        self.btn_refresh_all.setEnabled(not busy)
        self.btn_save.setEnabled(not busy)
        self.btn_edit_json.setEnabled(not busy)
        self.setCursor(
            Qt.CursorShape.WaitCursor if busy else Qt.CursorShape.ArrowCursor
        )

    def _refresh_server_list(self):
        keyword = (self.search_edit.text() or "").strip().lower()
        self.server_list.blockSignals(True)
        self.server_list.clear()
        indices = []
        for i, srv in enumerate(self._servers):
            hay = " ".join(
                [
                    str(srv.get("name", "")),
                    str(srv.get("url", "")),
                    str(srv.get("command", "")),
                    str(srv.get("transport", "")),
                ]
            ).lower()
            if keyword and keyword not in hay:
                continue
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, i)
            item.setText("")
            self.server_list.addItem(item)
            self._update_server_list_item_widget(item, srv)
            indices.append(i)
        self.server_list.blockSignals(False)
        self.server_count_label.setText(str(len(indices)))

        if not indices:
            self._current_index = -1
            self._clear_form()
            return

        if self._current_index not in indices:
            self._current_index = indices[0]
        for row in range(self.server_list.count()):
            item = self.server_list.item(row)
            if int(item.data(Qt.ItemDataRole.UserRole)) == self._current_index:
                self.server_list.setCurrentRow(row)
                break

    def _on_server_item_changed(self, item: QListWidgetItem):
        idx = int(item.data(Qt.ItemDataRole.UserRole))
        if 0 <= idx < len(self._servers):
            self._update_server_list_item_widget(item, self._servers[idx])

    def _on_server_enabled_changed(self, _state: int):
        idx = self._current_index
        if idx < 0 or idx >= len(self._servers):
            return
        self._servers[idx]["enabled"] = bool(self.server_enabled.isChecked())
        self._refresh_server_list()
        self._sync_hero_badges(self._servers[idx])
        self._mark_modified()

    def _on_server_selected(self, row: int):
        if row < 0:
            self._current_index = -1
            self._clear_form()
            return
        item = self.server_list.item(row)
        if not item:
            return
        idx = int(item.data(Qt.ItemDataRole.UserRole))
        self._current_index = idx
        if idx < 0 or idx >= len(self._servers):
            self._clear_form()
            return

        s = self._servers[idx]
        self._loading_form = True
        self.hero_name.setText(str(s.get("name", "-")))
        transport = str(s.get("transport", "stdio") or "stdio")
        endpoint = str(s.get("url") or s.get("command") or "未配置连接信息")
        self.hero_desc.setText(
            f"{transport.upper()} · timeout={s.get('timeout_sec', 30)} · {endpoint}"
        )
        self.server_enabled.blockSignals(True)
        self.server_enabled.setChecked(bool(s.get("enabled", True)))
        self.server_enabled.blockSignals(False)
        self._sync_hero_badges(s)

        self.edit_name.setText(str(s.get("name", "")))
        self.edit_url.setText(str(s.get("url", "")))
        self.edit_command.setText(str(s.get("command", "")))
        self.edit_args.setText(json.dumps(s.get("args", []), ensure_ascii=False))
        self.edit_env.setPlainText(
            json.dumps(s.get("env", {}), ensure_ascii=False, indent=2)
        )
        self.edit_cwd.setText(str(s.get("cwd", "")))
        self.edit_transport.setCurrentText(str(s.get("transport", "stdio") or "stdio"))
        self._on_transport_changed(self.edit_transport.currentText())
        try:
            self.edit_timeout.setValue(float(s.get("timeout_sec", 30.0)))
        except Exception:
            self.edit_timeout.setValue(30.0)
        self._loading_form = False
        self._show_cached_preview_for_current()

    def _clear_form(self):
        self.hero_name.setText("-")
        self.hero_desc.setText("选择一个 MCP server 查看详情")
        self.server_enabled.blockSignals(True)
        self.server_enabled.setChecked(False)
        self.server_enabled.blockSignals(False)
        self._sync_hero_badges(None)

        self.edit_name.clear()
        self.edit_url.clear()
        self.edit_command.clear()
        self.edit_args.setText("[]")
        self.edit_env.setPlainText("{}")
        self.edit_cwd.clear()
        self.edit_transport.setCurrentText("stdio")
        self.edit_timeout.setValue(30.0)
        self.preview_table.setRowCount(0)

    def _on_transport_changed(self, value: str):
        is_stdio = (value or "stdio") == "stdio"
        self.lbl_command.setVisible(is_stdio)
        self.edit_command.setVisible(is_stdio)
        self.lbl_args.setVisible(is_stdio)
        self.edit_args.setVisible(is_stdio)
        self.lbl_env.setVisible(is_stdio)
        self.edit_env.setVisible(is_stdio)
        self.lbl_cwd.setVisible(is_stdio)
        self.edit_cwd.setVisible(is_stdio)

        self.lbl_url.setVisible(not is_stdio)
        self.edit_url.setVisible(not is_stdio)
        self._on_form_field_changed()

    def _on_form_field_changed(self, *_args):
        if self._loading_form:
            return
        self._apply_current_server_from_form(show_errors=False, strict=False)

    def _add_server(self):
        base = {
            "name": f"mcp_{len(self._servers) + 1}",
            "enabled": True,
            "transport": "stdio",
            "url": "",
            "command": "",
            "args": [],
            "env": {},
            "cwd": "",
            "timeout_sec": 30.0,
        }
        self._servers.append(base)
        self._current_index = len(self._servers) - 1
        self._refresh_server_list()
        self._mark_modified()

    def _remove_server(self):
        idx = self._current_index
        if idx < 0 or idx >= len(self._servers):
            return
        self._servers.pop(idx)
        self._current_index = min(idx, len(self._servers) - 1)
        self._refresh_server_list()
        self._mark_modified()

    def _apply_current_server_from_form(
        self, show_errors: bool = True, strict: bool = True
    ) -> bool:
        idx = self._current_index
        if idx < 0 or idx >= len(self._servers):
            if show_errors:
                QMessageBox.information(self, "提示", "请先选择一个 MCP server")
            return False

        current = dict(self._servers[idx])

        try:
            args = json.loads(self.edit_args.text().strip() or "[]")
            env = json.loads(self.edit_env.toPlainText().strip() or "{}")
        except Exception as e:
            if strict:
                if show_errors:
                    QMessageBox.warning(self, "配置错误", f"JSON 解析失败: {e}")
                return False
            args = list(current.get("args", []) or [])
            env = dict(current.get("env", {}) or {})

        if not isinstance(args, list):
            if strict:
                if show_errors:
                    QMessageBox.warning(self, "配置错误", "args 必须是 JSON 数组")
                return False
            args = list(current.get("args", []) or [])
        if not isinstance(env, dict):
            if strict:
                if show_errors:
                    QMessageBox.warning(self, "配置错误", "env 必须是 JSON 对象")
                return False
            env = dict(current.get("env", {}) or {})

        name = self.edit_name.text().strip()
        url = self.edit_url.text().strip()
        command = self.edit_command.text().strip()
        transport = self.edit_transport.currentText().strip() or "stdio"
        if strict:
            if not name:
                if show_errors:
                    QMessageBox.warning(self, "配置错误", "name 不能为空")
                return False
            if transport == "stdio" and not command:
                if show_errors:
                    QMessageBox.warning(
                        self, "配置错误", "stdio 模式下 command 不能为空"
                    )
                return False
            if transport != "stdio" and not url:
                if show_errors:
                    QMessageBox.warning(self, "配置错误", "远程传输模式下 URL 不能为空")
                return False

        if not strict and not name:
            name = str(current.get("name", ""))

        self._servers[idx].update(
            {
                "name": name,
                "enabled": bool(self.server_enabled.isChecked()),
                "transport": transport,
                "url": url,
                "command": command,
                "args": [str(x) for x in args],
                "env": {str(k): str(v) for k, v in env.items()},
                "cwd": self.edit_cwd.text().strip(),
                "timeout_sec": float(self.edit_timeout.value()),
            }
        )
        for row_idx in range(self.server_list.count()):
            item = self.server_list.item(row_idx)
            if not item:
                continue
            item_idx = int(item.data(Qt.ItemDataRole.UserRole))
            if item_idx != idx:
                continue
            item.setText("")
            self._update_server_list_item_widget(item, self._servers[idx])
            break
        self._mark_modified()
        return True

    def _current_server_payload(self) -> Optional[Dict[str, Any]]:
        idx = self._current_index
        if idx < 0 or idx >= len(self._servers):
            return None
        return dict(self._servers[idx])

    def _submit_task(self, kind: str, fut: Future):
        self._task_seq += 1
        task_id = f"{kind}:{self._task_seq}"
        self._inflight[task_id] = kind

        def _done(f: Future):
            try:
                payload = f.result()
            except Exception as e:
                payload = {"ok": False, "message": str(e)}
            self._taskFinished.emit(task_id, payload)

        fut.add_done_callback(_done)

    def _set_preview_rows(self, rows: List[Dict[str, Any]]):
        self.preview_table.setRowCount(0)
        current = self._current_server_payload() or {}
        if current and 0 <= self._current_index < len(self._servers):
            self._servers[self._current_index]["tool_count"] = len(rows)
            current["tool_count"] = len(rows)
            self._sync_hero_badges(current)
            for row_idx in range(self.server_list.count()):
                item = self.server_list.item(row_idx)
                if not item:
                    continue
                idx = int(item.data(Qt.ItemDataRole.UserRole))
                if idx == self._current_index:
                    self._update_server_list_item_widget(item, self._servers[idx])
                    break
        for row in rows:
            r = self.preview_table.rowCount()
            self.preview_table.insertRow(r)
            self.preview_table.setItem(
                r, 0, QTableWidgetItem(str(row.get("server", "")))
            )
            self.preview_table.setItem(r, 1, QTableWidgetItem(str(row.get("name", ""))))
            self.preview_table.setItem(
                r, 2, QTableWidgetItem(str(row.get("description", "")))
            )
            schema_text = json.dumps(row.get("schema", {}), ensure_ascii=False)
            if len(schema_text) > 200:
                schema_text = schema_text[:200] + "..."
            self.preview_table.setItem(r, 3, QTableWidgetItem(schema_text))
        self.preview_table.resizeRowsToContents()

    def _preview_current_server(self, silent: bool = False):
        if self._current_index >= 0 and not silent:
            if not self._apply_current_server_from_form():
                return
        srv = self._current_server_payload()
        if not srv:
            return
        self._set_busy(True)
        self._submit_task(
            "preview_current",
            self._runner.submit_preview_servers([srv], enabled_only=False),
        )

    def _build_external_json(self) -> Dict[str, Any]:
        servers_obj: Dict[str, Any] = {}
        for s in self._servers:
            name = str(s.get("name") or "").strip()
            if not name:
                continue
            servers_obj[name] = {
                "enabled": bool(s.get("enabled", True)),
                "transport": str(s.get("transport", "stdio") or "stdio"),
                "url": str(s.get("url", "") or ""),
                "command": str(s.get("command", "") or ""),
                "args": list(s.get("args", []) or []),
                "env": dict(s.get("env", {}) or {}),
                "cwd": str(s.get("cwd", "") or ""),
                "timeout_sec": float(s.get("timeout_sec", 30.0)),
            }
        return {
            "enabled": bool(self.global_enabled.isChecked()),
            "refresh_tools_on_startup": bool(self.refresh_on_startup.isChecked()),
            "name_conflict_policy": self.conflict_combo.currentText().strip()
            or "prefix",
            "mcpServers": servers_obj,
        }

    def _apply_external_json(self, payload: Dict[str, Any]):
        if not isinstance(payload, dict):
            raise ValueError("JSON 根节点必须是对象")

        if "enabled" in payload:
            self.global_enabled.setChecked(bool(payload.get("enabled")))
        if "refresh_tools_on_startup" in payload:
            self.refresh_on_startup.setChecked(
                bool(payload.get("refresh_tools_on_startup"))
            )
        if "name_conflict_policy" in payload:
            val = str(payload.get("name_conflict_policy") or "prefix")
            if val in {"prefix", "skip", "error"}:
                self.conflict_combo.setCurrentText(val)

        parsed_servers: List[Dict[str, Any]] = []
        if "mcpServers" in payload:
            m = payload.get("mcpServers") or {}
            if not isinstance(m, dict):
                raise ValueError("mcpServers 必须是对象")
            for name, conf in m.items():
                if not isinstance(conf, dict):
                    raise ValueError(f"mcpServers.{name} 必须是对象")
                url = str(conf.get("url", "") or "")
                transport = str(conf.get("transport", "") or "").strip()
                if not transport:
                    transport = (
                        "sse"
                        if "sse" in url.lower()
                        else ("streamable_http" if url else "stdio")
                    )
                parsed_servers.append(
                    {
                        "name": str(name).strip(),
                        "enabled": bool(conf.get("enabled", True)),
                        "transport": transport,
                        "url": url,
                        "command": str(conf.get("command", "") or ""),
                        "args": [str(x) for x in list(conf.get("args", []) or [])],
                        "env": {
                            str(k): str(v)
                            for k, v in dict(conf.get("env", {}) or {}).items()
                        },
                        "cwd": str(conf.get("cwd", "") or ""),
                        "timeout_sec": float(
                            conf.get("timeout_sec", conf.get("timeout", 30.0))
                        ),
                    }
                )
        elif "servers" in payload:
            raw = payload.get("servers") or []
            if not isinstance(raw, list):
                raise ValueError("servers 必须是数组")
            for idx, conf in enumerate(raw):
                if not isinstance(conf, dict):
                    raise ValueError(f"servers[{idx}] 必须是对象")
                name = str(conf.get("name", "")).strip()
                if not name:
                    raise ValueError(f"servers[{idx}] 缺少 name")
                parsed_servers.append(
                    {
                        "name": name,
                        "enabled": bool(conf.get("enabled", True)),
                        "transport": str(conf.get("transport", "stdio") or "stdio"),
                        "url": str(conf.get("url", "") or ""),
                        "command": str(conf.get("command", "") or ""),
                        "args": [str(x) for x in list(conf.get("args", []) or [])],
                        "env": {
                            str(k): str(v)
                            for k, v in dict(conf.get("env", {}) or {}).items()
                        },
                        "cwd": str(conf.get("cwd", "") or ""),
                        "timeout_sec": float(conf.get("timeout_sec", 30.0)),
                    }
                )
        else:
            raise ValueError("缺少 mcpServers 或 servers 字段")

        self._servers = parsed_servers
        self._current_index = 0 if self._servers else -1
        self._refresh_server_list()
        self._mark_modified()

    def _edit_raw_json(self):
        payload = self._build_external_json()
        dlg = JsonEditorDialog(
            "编辑 MCP 原 JSON",
            json.dumps(payload, ensure_ascii=False, indent=2),
            self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            new_payload = json.loads(dlg.text().strip() or "{}")
            self._apply_external_json(new_payload)
        except Exception as e:
            QMessageBox.warning(self, "JSON 应用失败", str(e))

    def _save_and_apply(self):
        if self._current_index >= 0 and not self._apply_current_server_from_form():
            return

        payload = {
            "enabled": bool(self.global_enabled.isChecked()),
            "refresh_tools_on_startup": bool(self.refresh_on_startup.isChecked()),
            "name_conflict_policy": self.conflict_combo.currentText().strip()
            or "prefix",
            "servers": self._servers,
        }
        try:
            APP_SETTINGS.mcp.update(payload)
            ConfigManager.save_settings(APP_SETTINGS)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return

        self._set_busy(True)
        self._submit_task(
            "save_apply",
            self._runner.submit_apply_reload(
                enabled=bool(APP_SETTINGS.mcp.enabled), force_refresh=True
            ),
        )

    def _on_task_finished(self, task_id: str, payload: object):
        kind = self._inflight.pop(task_id, "")
        if not kind:
            return
        self._set_busy(False)

        if not isinstance(payload, dict):
            QMessageBox.warning(self, "任务失败", str(payload))
            return

        if kind in {"preview_current", "preview_enabled"}:
            rows = payload.get("rows", []) or []
            self._set_preview_rows(rows)
            if kind == "preview_current":
                QMessageBox.information(self, "刷新完成", f"发现 {len(rows)} 个工具")
            errors = payload.get("errors", []) or []
            if errors:
                QMessageBox.warning(
                    self, "预览部分失败", "\n".join([str(x) for x in errors[:20]])
                )
            return

        if kind == "save_apply":
            try:
                get_tools_event_bus().toolsChanged.emit()
            except Exception:
                pass

            if payload.get("errors") or payload.get("failed_servers"):
                detail = [
                    f"added: {payload.get('added', [])}",
                    f"cached: {payload.get('cached', [])}",
                    f"failed_servers: {payload.get('failed_servers', [])}",
                    f"errors: {payload.get('errors', [])}",
                ]
                QMessageBox.warning(self, "MCP 应用结果（部分失败）", "\n".join(detail))

            self.configUpdated.emit()
            self.notificationRequested.emit("MCP 配置已保存并应用", "success")
            self._mark_saved()
            self.hide()
