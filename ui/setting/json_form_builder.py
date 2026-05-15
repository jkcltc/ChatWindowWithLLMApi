from __future__ import annotations

import json
from typing import Any

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class _EditableListWidget(QWidget):
    list_changed = pyqtSignal(list)

    _EMPTY_HINT = "（空列表）"

    def __init__(self, items: list, parent: QWidget | None = None):
        super().__init__(parent)
        self._items: list = list(items)
        self._item_type: type | None = None
        if self._items:
            first = self._items[0]
            if isinstance(first, bool):
                self._item_type = bool
            elif isinstance(first, int):
                self._item_type = int
            elif isinstance(first, float):
                self._item_type = float
            elif isinstance(first, dict):
                self._item_type = dict
            else:
                self._item_type = str

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._list_widget = QListWidget()
        self._list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list_widget.setMinimumHeight(150)
        self._list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._populate_list()
        self._list_widget.setCurrentRow(0 if self._items else -1)
        self._list_widget.currentRowChanged.connect(self._update_button_states)
        layout.addWidget(self._list_widget, 1)

        self._empty_label = QLabel(self._EMPTY_HINT)
        self._empty_label.setStyleSheet("color: #888;")
        self._empty_label.setVisible(not self._items)
        layout.addWidget(self._empty_label)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        self._add_btn = QPushButton("[+] 添加")
        self._del_btn = QPushButton("[-] 删除")
        self._up_btn = QPushButton("[↑] 上移")
        self._down_btn = QPushButton("[↓] 下移")

        self._add_btn.clicked.connect(self._on_add)
        self._del_btn.clicked.connect(self._on_delete)
        self._up_btn.clicked.connect(self._on_move_up)
        self._down_btn.clicked.connect(self._on_move_down)

        btn_layout.addWidget(self._add_btn)
        btn_layout.addWidget(self._del_btn)
        btn_layout.addWidget(self._up_btn)
        btn_layout.addWidget(self._down_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._update_button_states()

    def populate(self, items: list) -> None:
        self._items = list(items)
        self._item_type = None
        if self._items:
            first = self._items[0]
            if isinstance(first, bool):
                self._item_type = bool
            elif isinstance(first, int):
                self._item_type = int
            elif isinstance(first, float):
                self._item_type = float
            elif isinstance(first, dict):
                self._item_type = dict
            else:
                self._item_type = str
        self._populate_list()
        self._update_button_states()
        self._empty_label.setVisible(not self._items)

    def get_items(self) -> list:
        return list(self._items)

    def _populate_list(self, select_row: int = -1) -> None:
        old_row = self._list_widget.currentRow()
        self._list_widget.clear()
        for idx, value in enumerate(self._items):
            row_widget = self._create_row_widget(idx, value)
            item = QListWidgetItem()
            item.setSizeHint(row_widget.sizeHint())
            self._list_widget.addItem(item)
            self._list_widget.setItemWidget(item, row_widget)
        target = select_row
        if target < 0:
            target = old_row
        if target < 0 and self._items:
            target = 0
        if 0 <= target < len(self._items):
            self._list_widget.setCurrentRow(target)

    def _create_row_widget(self, idx: int, value: Any) -> QWidget:
        widget_type = self._item_type
        container = QWidget()
        hlayout = QHBoxLayout(container)
        hlayout.setContentsMargins(4, 2, 4, 2)
        hlayout.setSpacing(6)

        if widget_type is dict:
            label = QLabel(self._dict_summary(value))
            label.setStyleSheet("color: #555;")
            label.setMinimumWidth(120)
            hlayout.addWidget(label, 1)
            edit_btn = QPushButton("编辑...")
            edit_btn.clicked.connect(lambda checked, i=idx: self._on_edit_dict_item(i))
            hlayout.addWidget(edit_btn)
            return container

        if widget_type is bool:
            widget = QCheckBox()
            widget.setChecked(bool(value))
            widget.toggled.connect(lambda checked, i=idx: self._on_item_changed(i, checked))
        elif widget_type is int:
            widget = QSpinBox()
            widget.setRange(-999999, 999999)
            widget.setValue(int(value) if value is not None else 0)
            widget.valueChanged.connect(lambda v, i=idx: self._on_item_changed(i, v))
        elif widget_type is float:
            widget = QDoubleSpinBox()
            widget.setRange(-999999.99, 999999.99)
            widget.setDecimals(2)
            widget.setSingleStep(0.01)
            widget.setValue(float(value) if value is not None else 0.0)
            widget.valueChanged.connect(lambda v, i=idx: self._on_item_changed(i, v))
        else:
            widget = QPlainTextEdit()
            widget.setPlainText(str(value) if value is not None else "")
            widget.setMaximumHeight(60)
            widget.textChanged.connect(lambda i=idx: self._on_item_text_changed(i))

        hlayout.addWidget(widget, 1)
        return container

    def _on_item_changed(self, idx: int, value: Any) -> None:
        if 0 <= idx < len(self._items):
            self._items[idx] = value
            self.list_changed.emit(list(self._items))

    def _on_item_text_changed(self, idx: int) -> None:
        widget = self._find_row_widget_by_idx(idx)
        if widget is not None:
            if isinstance(widget, QPlainTextEdit):
                new_val = widget.toPlainText()
                if 0 <= idx < len(self._items):
                    self._items[idx] = new_val
                    self.list_changed.emit(list(self._items))

    def _find_row_widget_by_idx(self, idx: int) -> QWidget | None:
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            w = self._list_widget.itemWidget(item)
            if w is not None:
                hlayout = w.layout()
                if hlayout and hlayout.count() >= 1:
                    last_item = hlayout.itemAt(hlayout.count() - 1)
                    if last_item and last_item.widget():
                        return last_item.widget()
        return None

    def _on_edit_dict_item(self, idx: int) -> None:
        if 0 <= idx < len(self._items):
            dlg = JsonFormEditorDialog("列表项", self._items[idx], self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._items[idx] = dlg.get_data()
                self._populate_list()
                self.list_changed.emit(list(self._items))

    def _on_add(self) -> None:
        default = self._default_value()
        self._items.append(default)
        self._populate_list()
        self._update_button_states()
        self._empty_label.setVisible(not self._items)
        self.list_changed.emit(list(self._items))

    def _on_delete(self) -> None:
        row = self._list_widget.currentRow()
        if 0 <= row < len(self._items):
            del self._items[row]
            self._populate_list()
            self._update_button_states()
            self._empty_label.setVisible(not self._items)
            self.list_changed.emit(list(self._items))

    def _on_move_up(self) -> None:
        row = self._list_widget.currentRow()
        if 1 <= row < len(self._items):
            self._items[row], self._items[row - 1] = self._items[row - 1], self._items[row]
            self._populate_list()
            self._list_widget.setCurrentRow(row - 1)
            self.list_changed.emit(list(self._items))

    def _on_move_down(self) -> None:
        row = self._list_widget.currentRow()
        if 0 <= row < len(self._items) - 1:
            self._items[row], self._items[row + 1] = self._items[row + 1], self._items[row]
            self._populate_list()
            self._list_widget.setCurrentRow(row + 1)
            self.list_changed.emit(list(self._items))

    def _update_button_states(self) -> None:
        has_items = len(self._items) > 0
        row = self._list_widget.currentRow()
        self._del_btn.setEnabled(has_items and row >= 0)
        self._up_btn.setEnabled(has_items and row > 0)
        self._down_btn.setEnabled(has_items and row >= 0 and row < len(self._items) - 1)

    def _default_value(self) -> Any:
        if self._item_type is bool:
            return False
        elif self._item_type is int:
            return 0
        elif self._item_type is float:
            return 0.0
        elif self._item_type is dict:
            return {}
        return ""

    @staticmethod
    def _dict_summary(data: dict) -> str:
        if not data:
            return "{}"
        parts = []
        for k, v in data.items():
            if len(parts) >= 3:
                parts.append("...")
                break
            parts.append(f"{k}: {_EditableListWidget._truncate_val(v)}")
        return "{" + ", ".join(parts) + "}"

    @staticmethod
    def _truncate_val(v: Any) -> str:
        s = json.dumps(v, ensure_ascii=False)
        if len(s) > 30:
            return s[:27] + "..."
        return s


class JsonFormEditorDialog(QDialog):
    def __init__(self, title: str, data: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"编辑 - {title}")
        self.resize(500, 400)

        layout = QVBoxLayout(self)
        self._builder = JsonFormBuilder(self)
        scroll = self._builder.build(self, data)
        layout.addWidget(scroll, 1)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_data(self) -> dict:
        return self._builder.collect()


class JsonFormBuilder(QObject):
    data_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._data: dict = {}
        self._root_widget: QWidget | None = None
        self._widgets: dict[str, QWidget] = {}
        self._key_labels: dict[str, QLabel] = {}

    def build(self, parent: QWidget, data: dict) -> QWidget:
        self._clear()
        self._data = json.loads(json.dumps(data))

        scroll = QScrollArea(parent)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        if not self._data:
            empty_label = QLabel("（无配置项）")
            empty_label.setStyleSheet("color: #888;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty_label)
        else:
            for key, value in self._data.items():
                widget_row = self._create_widget_for(container, key, value, path=key)
                layout.addWidget(widget_row)

        layout.addStretch()
        scroll.setWidget(container)
        self._root_widget = scroll
        return scroll

    def collect(self) -> dict:
        return self._collect_from_widgets()

    def rebuild(self, parent: QWidget, data: dict) -> QWidget:
        self._clear()
        return self.build(parent, data)

    def _clear(self) -> None:
        if self._root_widget is not None:
            self._root_widget.deleteLater()
            self._root_widget = None
        self._widgets.clear()
        self._key_labels.clear()
        self._data = {}

    def _create_widget_for(self, parent: QWidget, key: str, value: Any, path: str) -> QWidget:
        if isinstance(value, dict):
            group = QGroupBox(self._format_key_label(key))
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(8, 12, 8, 8)
            group_layout.setSpacing(2)
            for sub_key, sub_value in value.items():
                sub_path = f"{path}.{sub_key}"
                sub_row = self._create_widget_for(group, sub_key, sub_value, sub_path)
                group_layout.addWidget(sub_row)
            return group

        if isinstance(value, list):
            row = QWidget(parent)
            layout = QVBoxLayout(row)
            layout.setContentsMargins(0, 2, 0, 2)
            layout.setSpacing(4)

            label = QLabel(self._format_key_label(key))
            label.setStyleSheet("font-weight: bold;")
            layout.addWidget(label)

            list_widget = _EditableListWidget(value)
            list_widget.setMinimumHeight(100)
            list_widget.list_changed.connect(lambda items, p=path: self._on_field_changed(p, items))
            layout.addWidget(list_widget, 1)

            self._widgets[path] = list_widget
            return row

        row = QWidget(parent)
        hlayout = QHBoxLayout(row)
        hlayout.setContentsMargins(4, 1, 4, 1)
        hlayout.setSpacing(6)

        label = QLabel(self._format_key_label(key))
        label.setMinimumWidth(120)
        label.setMaximumWidth(300)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        hlayout.addWidget(label)

        widget = self._create_leaf_widget(value)
        hlayout.addWidget(widget, 1)
        self._connect_signal(widget, path)

        self._widgets[path] = widget
        self._key_labels[path] = label
        return row

    def _create_leaf_widget(self, value: Any) -> QWidget:
        if isinstance(value, bool):
            widget = QCheckBox()
            widget.setChecked(value)
            return widget

        if isinstance(value, int):
            widget = QSpinBox()
            widget.setRange(-999999, 999999)
            widget.setValue(value)
            return widget

        if isinstance(value, float):
            widget = QDoubleSpinBox()
            widget.setRange(-999999.99, 999999.99)
            widget.setDecimals(2)
            widget.setSingleStep(0.01)
            widget.setValue(value)
            return widget

        if isinstance(value, str):
            widget = QPlainTextEdit()
            widget.setPlainText(value)
            widget.setMaximumHeight(72)
            return widget

        widget = QLineEdit()
        widget.setText(str(value))
        widget.setReadOnly(True)
        return widget

    def _connect_signal(self, widget: QWidget, path: str) -> None:
        if isinstance(widget, QCheckBox):
            widget.toggled.connect(lambda checked, p=path: self._on_field_changed(p, checked))
        elif isinstance(widget, QSpinBox):
            widget.valueChanged.connect(lambda v, p=path: self._on_field_changed(p, v))
        elif isinstance(widget, QDoubleSpinBox):
            widget.valueChanged.connect(lambda v, p=path: self._on_field_changed(p, v))
        elif isinstance(widget, QLineEdit):
            widget.textChanged.connect(lambda text, p=path: self._on_field_changed(p, text))
        elif isinstance(widget, QPlainTextEdit):
            widget.textChanged.connect(lambda p=path: self._on_field_changed(p, widget.toPlainText()))
        elif isinstance(widget, _EditableListWidget):
            widget.list_changed.connect(lambda items, p=path: self._on_field_changed(p, items))

    def _on_field_changed(self, path: str, value: Any) -> None:
        keys = path.split(".")
        target = self._data
        for k in keys[:-1]:
            target = target[k]
        target[keys[-1]] = value
        self.data_changed.emit()

    def _collect_from_widgets(self) -> dict:
        result: dict = {}
        for path, widget in self._widgets.items():
            val = self._read_widget_value(widget)
            keys = path.split(".")
            target = result
            for k in keys[:-1]:
                if k not in target or not isinstance(target[k], dict):
                    target[k] = {}
                target = target[k]
            target[keys[-1]] = val
        return result

    @staticmethod
    def _read_widget_value(widget: QWidget) -> Any:
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        elif isinstance(widget, QSpinBox):
            return widget.value()
        elif isinstance(widget, QDoubleSpinBox):
            return widget.value()
        elif isinstance(widget, QLineEdit):
            return widget.text()
        elif isinstance(widget, QPlainTextEdit):
            return widget.toPlainText()
        elif isinstance(widget, _EditableListWidget):
            return widget.get_items()
        return None

    @staticmethod
    def _format_key_label(key: str) -> str:
        display = key.replace("_", " ").strip()
        if display and not display[0].isupper():
            display = display[0].upper() + display[1:]
        return display
