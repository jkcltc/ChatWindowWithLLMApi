from __future__ import annotations

import sys
from typing import Optional, List, TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from config.settings import ModConfig
from .json_form_builder import JsonFormBuilder

if TYPE_CHECKING:
    from core.context.mod_manager import ModManager
    from .mod_main_window_manager import ModMainWindowManager


_PHASE_OPTIONS = [
    ("PRE_PROCESS", "前处理·数据准备"),
    ("TRANSFORM", "前处理·消息变换"),
    ("INJECT", "前处理·内容注入"),
    ("DECORATE", "前处理·字符串装饰"),
    ("FINALIZE", "前处理·兜底"),
    ("VALIDATE", "后处理·响应校验"),
    ("REWRITE", "后处理·响应改写"),
    ("TRANSFORM_COMMIT", "持久化·写入变换"),
    ("STREAM_REWRITE", "流式·内容改写"),
]


class AddModDialog(QDialog):
    def __init__(self, available_mods: List[dict], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("添加 Mod")
        self.resize(520, 400)

        layout = QVBoxLayout(self)

        self._list = QListWidget()
        self._list.setFrameShape(QFrame.Shape.NoFrame)
        self._list.setSpacing(4)
        for mod_info in available_mods:
            item = QListWidgetItem()
            label = f"{mod_info['name']}"
            if mod_info.get("description"):
                label += f" — {mod_info['description']}"
            item.setText(label)
            item.setData(Qt.ItemDataRole.UserRole, mod_info)
            self._list.addItem(item)

        layout.addWidget(QLabel("从 mods/ 目录发现的 Mod："))
        layout.addWidget(self._list, 1)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._validate_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _validate_and_accept(self):
        current = self._list.currentItem()
        if not current:
            QMessageBox.warning(self, "提示", "请选择一个 Mod")
            return
        self.accept()

    def get_selected_mod(self) -> Optional[dict]:
        item = self._list.currentItem()
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None


class ModConfigWidget(QWidget):
    manager_changed = pyqtSignal()

    def __init__(self, mod_manager: ModManager, window_manager: ModMainWindowManager = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._manager = mod_manager
        self._window_manager = window_manager
        self._configs: List[ModConfig] = []
        self._current_index: int = -1
        self._form_builder: Optional[JsonFormBuilder] = None
        self._config_scroll: Optional[QScrollArea] = None
        self._custom_config_widget: Optional[QWidget] = None
        self._loading_form = False

        self._build_ui()
        self._load_configs()
        self._connect_signals()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title = QLabel("Mod 管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        root.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        left_header = QHBoxLayout()
        left_header.addWidget(QLabel("已配置 Mod"))
        left_header.addStretch()
        left_layout.addLayout(left_header)

        self._mod_list = QListWidget()
        self._mod_list.setFrameShape(QFrame.Shape.NoFrame)
        self._mod_list.setSpacing(4)
        left_layout.addWidget(self._mod_list, 1)

        left_btn_row = QHBoxLayout()
        left_btn_row.setSpacing(6)
        self._btn_add = QPushButton("+ 添加")
        self._btn_remove = QPushButton("− 移除")
        self._btn_refresh = QPushButton("刷新发现")
        left_btn_row.addWidget(self._btn_add)
        left_btn_row.addWidget(self._btn_remove)
        left_btn_row.addWidget(self._btn_refresh)
        left_btn_row.addStretch()
        left_layout.addLayout(left_btn_row)

        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 0, 0, 0)
        right_layout.setSpacing(12)

        self._right_scroll = QScrollArea()
        self._right_scroll.setWidgetResizable(True)
        self._right_scroll.setFrameShape(QFrame.Shape.NoFrame)

        detail_container = QWidget()
        self._detail_layout = QVBoxLayout(detail_container)
        self._detail_layout.setContentsMargins(0, 0, 0, 0)
        self._detail_layout.setSpacing(16)

        meta_group = QGroupBox("Mod 元信息")
        meta_form = QFormLayout(meta_group)
        meta_form.setSpacing(8)

        self._edit_name = QLineEdit()
        self._edit_class_path = QLineEdit()
        self._edit_class_path.setReadOnly(True)
        self._edit_phase = QComboBox()
        for value, label in _PHASE_OPTIONS:
            self._edit_phase.addItem(label, value)
        self._edit_depth = QSpinBox()
        self._edit_depth.setRange(0, 9999)
        self._edit_desc = QLineEdit()

        meta_form.addRow("名称", self._edit_name)
        meta_form.addRow("类路径", self._edit_class_path)
        meta_form.addRow("Phase", self._edit_phase)
        meta_form.addRow("Depth", self._edit_depth)
        meta_form.addRow("描述", self._edit_desc)

        self._detail_layout.addWidget(meta_group)

        config_group = QGroupBox("运行时参数 (config)")
        config_layout = QVBoxLayout(config_group)
        config_layout.setContentsMargins(4, 8, 4, 4)

        self._config_container = QVBoxLayout()
        self._config_container.setContentsMargins(0, 0, 0, 0)
        config_layout.addLayout(self._config_container)

        self._edit_config_json_btn = QPushButton("编辑原始 JSON")
        config_layout.addWidget(self._edit_config_json_btn)

        self._detail_layout.addWidget(config_group)

        self._detail_layout.addStretch()

        self._right_scroll.setWidget(detail_container)
        right_layout.addWidget(self._right_scroll, 1)

        right_btn_row = QHBoxLayout()
        right_btn_row.setSpacing(8)
        self._btn_open_panel = QPushButton("打开面板")
        self._btn_open_panel.setEnabled(False)
        self._btn_toggle = QPushButton("启用/禁用")
        self._btn_save = QPushButton("保存")
        right_btn_row.addWidget(self._btn_open_panel)
        right_btn_row.addWidget(self._btn_toggle)
        right_btn_row.addWidget(self._btn_save)
        right_btn_row.addStretch()
        right_layout.addLayout(right_btn_row)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 600])
        root.addWidget(splitter, 1)

    def _connect_signals(self):
        self._mod_list.currentRowChanged.connect(self._on_selection_changed)
        self._btn_add.clicked.connect(self._on_add_mod)
        self._btn_remove.clicked.connect(self._on_remove_mod)
        self._btn_refresh.clicked.connect(self._on_refresh)
        self._btn_open_panel.clicked.connect(self._on_open_panel)
        self._btn_toggle.clicked.connect(self._on_toggle_mod)
        self._btn_save.clicked.connect(self._on_save)
        self._edit_config_json_btn.clicked.connect(self._on_edit_raw_config)
        self._edit_name.textChanged.connect(self._on_form_changed)
        self._edit_phase.currentIndexChanged.connect(self._on_form_changed)
        self._edit_depth.valueChanged.connect(self._on_form_changed)
        self._edit_desc.textChanged.connect(self._on_form_changed)

    def _load_configs(self):
        self._configs = self._manager.get_mod_configs()
        self._refresh_list()

    def _refresh_list(self):
        self._mod_list.blockSignals(True)
        self._mod_list.clear()
        for i, config in enumerate(self._configs):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, i)
            enabled_mark = "☑" if config.enabled else "☐"
            item.setText(f"{enabled_mark}  {config.name}")
            self._mod_list.addItem(item)
        self._mod_list.blockSignals(False)
        if self._configs:
            target = self._current_index
            if target < 0 or target >= len(self._configs):
                target = 0
            self._mod_list.setCurrentRow(target)
        else:
            self._current_index = -1
            self._clear_form()

    def _on_selection_changed(self, row: int):
        if row < 0:
            self._current_index = -1
            self._clear_form()
            return
        item = self._mod_list.item(row)
        if not item:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is None or idx < 0 or idx >= len(self._configs):
            return
        self._current_index = idx
        self._populate_form(self._configs[idx])

    def _populate_form(self, config: ModConfig):
        self._loading_form = True

        self._edit_name.setText(config.name)
        self._edit_class_path.setText(config.class_path)

        idx = self._edit_phase.findData(config.phase)
        if idx >= 0:
            self._edit_phase.setCurrentIndex(idx)
        else:
            self._edit_phase.setCurrentIndex(0)

        self._edit_depth.setValue(config.depth)
        self._edit_desc.setText(config.description)

        self._btn_open_panel.setEnabled(config.enabled and bool(config.has_main_widget))

        if config.enabled and config.has_config_widget and self._try_load_custom_config_widget(config):
            pass
        else:
            self._rebuild_config_form(config.config)

        self._loading_form = False

    def _try_load_custom_config_widget(self, config: ModConfig) -> bool:
        self._destroy_custom_config_widget()
        mod = self._manager.get_mod_instance(config.name)
        if mod is None:
            return False
        module = sys.modules.get(mod.__class__.__module__)
        if module is None or not hasattr(module, "mod_config_widget"):
            return False
        try:
            widget = module.mod_config_widget(mod, parent=self)
        except Exception:
            return False
        if widget is None:
            return False

        self._custom_config_widget = widget
        self._config_container.addWidget(widget)
        return True

    def _destroy_custom_config_widget(self):
        if self._custom_config_widget is not None:
            while self._config_container.count():
                item = self._config_container.takeAt(0)
                if item.widget() is self._custom_config_widget:
                    self._custom_config_widget.setParent(None)
                    self._custom_config_widget.deleteLater()
                    self._custom_config_widget = None
                    return
                if item.widget():
                    pass
            self._custom_config_widget.setParent(None)
            self._custom_config_widget.deleteLater()
            self._custom_config_widget = None

    def _rebuild_config_form(self, config_dict: dict):
        if self._form_builder is not None:
            self._form_builder.data_changed.disconnect()
            self._form_builder.deleteLater()
            self._form_builder = None
        if self._config_scroll is not None:
            self._config_scroll.deleteLater()
            self._config_scroll = None

        while self._config_container.count():
            item = self._config_container.takeAt(0)
            if item.widget():
                pass

        self._form_builder = JsonFormBuilder(self)
        self._form_builder.data_changed.connect(self._on_config_changed)
        self._config_scroll = self._form_builder.build(self, config_dict)
        self._config_container.addWidget(self._config_scroll)

    def _clear_form(self):
        self._loading_form = True
        self._edit_name.clear()
        self._edit_class_path.clear()
        self._edit_phase.setCurrentIndex(0)
        self._edit_depth.setValue(50)
        self._edit_desc.clear()
        self._btn_open_panel.setEnabled(False)

        self._destroy_custom_config_widget()

        if self._form_builder is not None:
            self._form_builder.data_changed.disconnect()
            self._form_builder.deleteLater()
            self._form_builder = None
        if self._config_scroll is not None:
            self._config_scroll.deleteLater()
            self._config_scroll = None
        while self._config_container.count():
            item = self._config_container.takeAt(0)
            if item.widget():
                pass

        self._loading_form = False

    def _on_form_changed(self, *_args):
        if self._loading_form:
            return
        idx = self._current_index
        if idx < 0 or idx >= len(self._configs):
            return
        config = self._configs[idx]
        config.name = self._edit_name.text().strip()
        phase_data = self._edit_phase.currentData()
        if phase_data:
            config.phase = str(phase_data)
        config.depth = self._edit_depth.value()
        config.description = self._edit_desc.text().strip()

        enabled_mark = "☑" if config.enabled else "☐"
        item = self._mod_list.item(self._mod_list.currentRow())
        if item:
            item.setText(f"{enabled_mark}  {config.name}")

    def _on_config_changed(self):
        if self._loading_form:
            return
        idx = self._current_index
        if idx < 0 or idx >= len(self._configs):
            return
        if self._form_builder:
            self._configs[idx].config = self._form_builder.collect()

    def _on_add_mod(self):
        from core.context.mod_manager import ModManager

        available = ModManager.discover_available_mods()
        if not available:
            QMessageBox.information(self, "提示", "mods/ 目录中未发现 Mod 类")
            return

        dlg = AddModDialog(available, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        mod_info = dlg.get_selected_mod()
        if not mod_info:
            return

        new_config = ModConfig(
            name=mod_info["name"],
            enabled=False,
            mod_type="class",
            class_path=mod_info["class_path"],
            description=mod_info.get("description", ""),
            version=mod_info.get("version", "1.0"),
            author=mod_info.get("author", ""),
            phase="INJECT",
            depth=50,
            config={},
            has_config_widget=mod_info.get("has_config_widget", False),
            has_main_widget=mod_info.get("has_main_widget", False),
            main_widget_title=mod_info.get("main_widget_title", ""),
        )
        self._manager.add_mod(new_config)
        self._load_configs()
        self.manager_changed.emit()

    def _on_remove_mod(self):
        idx = self._current_index
        if idx < 0 or idx >= len(self._configs):
            return
        name = self._configs[idx].name
        reply = QMessageBox.question(
            self, "确认移除", f"确定要移除 Mod \"{name}\" 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._manager.remove_mod(name)
        self._load_configs()
        self.manager_changed.emit()

    def _on_toggle_mod(self):
        idx = self._current_index
        if idx < 0 or idx >= len(self._configs):
            return
        config = self._configs[idx]
        if config.enabled:
            self._manager.disable_mod(config.name)
        else:
            self._manager.enable_mod(config.name)
        self._load_configs()
        self.manager_changed.emit()

    def _on_open_panel(self):
        idx = self._current_index
        if idx < 0 or idx >= len(self._configs):
            return
        config = self._configs[idx]
        if not config.has_main_widget:
            return
        if not config.enabled:
            return

        mod = self._manager.get_mod_instance(config.name)
        if mod is None:
            return

        module = sys.modules.get(mod.__class__.__module__)
        if module is None or not hasattr(module, "mod_main_widget"):
            return

        try:
            widget = module.mod_main_widget(mod)
        except Exception:
            return
        if widget is None:
            return

        title = config.main_widget_title or config.name

        if self._window_manager is not None:
            self._window_manager.open_mod_window(config.name, widget, title)
        else:
            from PyQt6.QtWidgets import QDialog
            dlg = QDialog(self)
            dlg.setWindowTitle(title)
            dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            layout = QVBoxLayout(dlg)
            layout.addWidget(widget)
            dlg.show()

    def _on_save(self):
        self._manager.save()

    def _on_refresh(self):
        self._load_configs()

    def _on_edit_raw_config(self):
        idx = self._current_index
        if idx < 0 or idx >= len(self._configs):
            return

        import json
        from .mcp_config_widget import JsonEditorDialog

        current_json = json.dumps(
            self._configs[idx].config, ensure_ascii=False, indent=2
        )
        dlg = JsonEditorDialog("编辑 Mod 配置 JSON", current_json, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            new_config = json.loads(dlg.text().strip() or "{}")
            if not isinstance(new_config, dict):
                raise ValueError("config 必须是 JSON 对象")
            self._configs[idx].config = new_config
            self._rebuild_config_form(new_config)
        except Exception as e:
            QMessageBox.warning(self, "JSON 解析失败", str(e))
