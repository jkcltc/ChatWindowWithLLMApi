from typing import Optional, Dict, List, Tuple
from service.chat_completion import GlobalPatcher
from PyQt6.QtWidgets import (
    QWidget, QLineEdit, QListWidget, QApplication,
    QVBoxLayout, QHBoxLayout, QLabel,
    QTabWidget, QGroupBox, QPushButton,
    QComboBox, QInputDialog, QFormLayout,
    QMessageBox, QGraphicsOpacityEffect,
    QListWidgetItem
)
from PyQt6.QtCore import (
    pyqtSignal, Qt, QTimer, QRect,
    QSequentialAnimationGroup, QAbstractAnimation,
    QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import QFont

from config.model_map_manager import APIConfigDialogUpdateModelThread
from config import APP_SETTINGS, ConfigManager


class APIConfigWidget(QWidget):
    configUpdated = pyqtSignal()
    initializationCompleted = pyqtSignal(dict)
    notificationRequested = pyqtSignal(str, str)  # message, level

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.preset_apis = ["deepseek"]
        self.custom_apis = []

        # api_name -> (url_entry, key_entry, model_list_widget, search_edit, type_combo)
        self.api_widgets: Dict[str, Tuple[QLineEdit, QLineEdit, QListWidget, QLineEdit, QComboBox]] = {}
        self.available_models: Dict[str, List[str]] = {}
        self.api_timers: Dict[str, QTimer] = {}

        self.update_btn_overlay = None
        self.animation_group = None
        self.save_btn_overlay = None
        self.save_animation_group = None
        self.save_in_progress = False
        self.initializing = True

        self._initialize_ui()
        self._setup_update_button_animation()
        self._setup_save_button_animation()
        self.load_config()
        self.adjustSize()

        screen_geometry = QApplication.primaryScreen().availableGeometry()
        width = int(screen_geometry.width() * 0.3)
        height = int(screen_geometry.height() * 0.8)
        left = (screen_geometry.width() - width) // 2
        top = (screen_geometry.height() - height) // 2
        self.setGeometry(left, top, width, height)
        self.setWindowTitle("API 配置管理")

        self.initializationCompleted.emit(self.available_models)
        self.initializing = False

    def _initialize_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        title_label = QLabel("API 配置管理")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.West)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setElideMode(Qt.TextElideMode.ElideNone)
        main_layout.addWidget(self.tab_widget, 1)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        button_layout.addStretch(1)

        self.add_custom_btn = QPushButton("+ 添加自定义API供应商")
        self.add_custom_btn.setFixedHeight(40)
        self.add_custom_btn.clicked.connect(self.add_custom_api)
        button_layout.addWidget(self.add_custom_btn)

        self.update_btn = QPushButton("更新模型库")
        self.update_btn.setFixedHeight(40)
        self.update_btn.clicked.connect(self.on_update_models)
        button_layout.addWidget(self.update_btn)

        self.save_btn = QPushButton("保存并关闭")
        self.save_btn.setFixedHeight(40)
        self.save_btn.clicked.connect(self.on_save_and_close)
        button_layout.addWidget(self.save_btn)

        main_layout.addLayout(button_layout)

        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        main_layout.addWidget(self.status_label)

        self._setup_preset_apis()

    def _setup_preset_apis(self) -> None:
        for api_name in self.preset_apis:
            self._create_api_tab(api_name, is_custom=False)

    def _create_api_tab(self, api_name: str, is_custom: bool = True) -> None:
        tab_content = QWidget()
        tab_content.setObjectName(api_name)
        main_tab_layout = QVBoxLayout(tab_content)
        main_tab_layout.setContentsMargins(15, 15, 15, 15)
        main_tab_layout.setSpacing(15)

        # API 配置
        config_group = QGroupBox("API 配置")
        config_layout = QFormLayout()
        config_layout.setSpacing(12)
        config_layout.setContentsMargins(15, 15, 15, 15)

        url_entry = QLineEdit()
        url_entry.setPlaceholderText("请输入API端点URL...")
        url_entry.setClearButtonEnabled(True)

        key_entry = QLineEdit()
        key_entry.setPlaceholderText("请输入认证密钥...")
        key_entry.setEchoMode(QLineEdit.EchoMode.Password)
        key_entry.setClearButtonEnabled(True)

        type_combo = QComboBox()
        type_combo.setEditable(True)
        patch_list = GlobalPatcher().patch_list
        type_combo.addItems(patch_list)
        type_combo.setPlaceholderText("选择或输入适配类型")

        url_entry.textChanged.connect(lambda _text, api=api_name: self._on_config_edited(api))
        key_entry.textChanged.connect(lambda _text, api=api_name: self._on_config_edited(api))
        type_combo.currentTextChanged.connect(lambda _text, api=api_name: self._on_config_edited(api))

        config_layout.addRow("API URL:", url_entry)
        config_layout.addRow("API 密钥:", key_entry)
        config_layout.addRow("供应商类型:", type_combo)

        if is_custom:
            del_btn = QPushButton("删除此供应商")
            del_btn.setStyleSheet("QPushButton { color: #ff4444; }")
            del_btn.clicked.connect(lambda: self.remove_custom_api(api_name))
            config_layout.addRow(del_btn)

        config_group.setLayout(config_layout)
        main_tab_layout.addWidget(config_group)

        # 模型选择
        model_group = QGroupBox("模型选择")
        model_layout = QVBoxLayout(model_group)
        model_layout.setContentsMargins(15, 15, 15, 15)

        search_layout = QHBoxLayout()
        search_label = QLabel("搜索:")
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("输入模型名称...")
        search_edit.textChanged.connect(lambda text, api=api_name: self.filter_models(api, text))
        search_layout.addWidget(search_label)
        search_layout.addWidget(search_edit)
        model_layout.addLayout(search_layout)

        model_desc = QLabel("可用模型列表 (点击-添加/取消选用):")
        model_layout.addWidget(model_desc)

        model_list_widget = QListWidget()
        model_list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        model_list_widget.setAlternatingRowColors(True)
        model_layout.addWidget(model_list_widget)

        add_model_btn = QPushButton("手动添加")
        add_model_btn.clicked.connect(lambda: self.add_manual_model(api_name))
        model_layout.addWidget(add_model_btn)

        model_list_widget.itemSelectionChanged.connect(
            lambda api=api_name: self._on_config_edited(api)
        )

        main_tab_layout.addWidget(model_group, 5)
        self.tab_widget.addTab(tab_content, api_name)
        self.api_widgets[api_name] = (url_entry, key_entry, model_list_widget, search_edit, type_combo)

        if is_custom and api_name not in self.custom_apis:
            self.custom_apis.append(api_name)

    def add_manual_model(self, api_name: str):
        model_name, ok = QInputDialog.getText(
            self, "添加模型", f"请输入要添加到{api_name}的模型名称:"
        )
        if ok and model_name:
            model_name = model_name.strip()
            if not model_name:
                QMessageBox.warning(self, "输入错误", "模型名称不能为空")
                return
            if api_name not in self.api_widgets:
                return

            _, _, list_widget, _, _ = self.api_widgets[api_name]

            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item and item.text() == model_name:
                    QMessageBox.information(self, "已存在", f"模型 '{model_name}' 已在列表中")
                    return

            list_widget.addItem(model_name)
            if api_name not in self.available_models:
                self.available_models[api_name] = []
            self.available_models[api_name].append(model_name)
            self.available_models[api_name] = sorted(list(set(self.available_models[api_name])))

            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item and item.text() == model_name:
                    item.setSelected(True)
                    list_widget.scrollToItem(item)
                    break

            self.status_label.setText(f"已添加模型: {model_name}")
            QTimer.singleShot(2000, lambda: self.status_label.setText(""))
            self._on_config_edited(api_name)

    def _on_config_edited(self, api_name: str) -> None:
        if self.initializing:
            return

        if api_name not in self.api_timers:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(1000)
            # 自动编辑仅做“草稿校验/收集”，不改全局、不通知外部、不落盘
            timer.timeout.connect(lambda: self._validate_and_save(
                show_message=False,
                apply_global=False,
                emit_signal=False,
                persist=False
            ))
            self.api_timers[api_name] = timer
        else:
            timer = self.api_timers[api_name]

        if timer.isActive():
            timer.stop()
        timer.start()

    def _setup_update_button_animation(self):
        self.update_btn_overlay = QWidget(self.update_btn)
        self.update_btn_overlay.setStyleSheet("background-color: rgba(173, 216, 230, 80);")
        self.update_btn_overlay.hide()
        self.update_btn_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.opacity_effect = QGraphicsOpacityEffect(self.update_btn_overlay)
        self.opacity_effect.setOpacity(1.0)
        self.update_btn_overlay.setGraphicsEffect(self.opacity_effect)

        self.animation_group = QSequentialAnimationGroup(self)
        self.animation_group.setLoopCount(-1)

        self.width_animation = QPropertyAnimation(self.update_btn_overlay, b"geometry")
        self.width_animation.setDuration(1500)
        self.width_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(600)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.OutQuad)

        self.reset_animation = QSequentialAnimationGroup()
        self.reset_opacity_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.reset_opacity_anim.setDuration(0)
        self.reset_opacity_anim.setStartValue(0.0)
        self.reset_opacity_anim.setEndValue(1.0)

        self.reset_geometry_anim = QPropertyAnimation(self.update_btn_overlay, b"geometry")
        self.reset_geometry_anim.setDuration(0)

        self.reset_animation.addAnimation(self.reset_opacity_anim)
        self.reset_animation.addAnimation(self.reset_geometry_anim)

        self.animation_group.addAnimation(self.width_animation)
        self.animation_group.addAnimation(self.fade_animation)
        self.animation_group.addAnimation(self.reset_animation)

    def _setup_save_button_animation(self):
        self.save_btn_overlay = QWidget(self.save_btn)
        self.save_btn_overlay.setStyleSheet("background-color: rgba(143, 188, 143, 80);")
        self.save_btn_overlay.hide()
        self.save_btn_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.save_opacity_effect = QGraphicsOpacityEffect(self.save_btn_overlay)
        self.save_opacity_effect.setOpacity(1.0)
        self.save_btn_overlay.setGraphicsEffect(self.save_opacity_effect)

        self.save_animation_group = QSequentialAnimationGroup(self)
        self.save_animation_group.setLoopCount(1)

        self.save_width_animation = QPropertyAnimation(self.save_btn_overlay, b"geometry")
        self.save_width_animation.setDuration(1500)
        self.save_width_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.save_fade_animation = QPropertyAnimation(self.save_opacity_effect, b"opacity")
        self.save_fade_animation.setDuration(600)
        self.save_fade_animation.setStartValue(1.0)
        self.save_fade_animation.setEndValue(0.0)
        self.save_fade_animation.setEasingCurve(QEasingCurve.Type.OutQuad)

        self.save_animation_group.finished.connect(self._on_save_animation_finished)
        self.save_animation_group.addAnimation(self.save_width_animation)
        self.save_animation_group.addAnimation(self.save_fade_animation)

    def start_update_animation(self):
        self.update_btn.setEnabled(False)
        self.update_btn_overlay.setGeometry(0, 0, 0, self.update_btn.height())
        self.update_btn_overlay.show()
        self.update_btn_overlay.raise_()

        end_width = self.update_btn.width()
        self.width_animation.setStartValue(QRect(0, 0, 0, self.update_btn.height()))
        self.width_animation.setEndValue(QRect(0, 0, end_width, self.update_btn.height()))
        self.reset_geometry_anim.setEndValue(QRect(0, 0, 0, self.update_btn.height()))
        self.animation_group.start()

    def stop_update_animation(self):
        self.update_btn.setEnabled(True)
        if self.animation_group and self.animation_group.state() == QAbstractAnimation.State.Running:
            self.animation_group.stop()
        if self.update_btn_overlay:
            self.update_btn_overlay.hide()

    def start_save_animation(self):
        self.save_in_progress = True
        self.save_btn.setFixedSize(self.save_btn.size())
        self.save_btn.setText("取消")
        self.save_btn.setEnabled(True)
        self.save_btn_overlay.setGeometry(0, 0, 0, self.save_btn.height())
        self.save_btn_overlay.show()
        self.save_btn_overlay.raise_()

        end_width = self.save_btn.width()
        self.save_width_animation.setStartValue(QRect(0, 0, 0, self.save_btn.height()))
        self.save_width_animation.setEndValue(QRect(0, 0, end_width, self.save_btn.height()))
        self.save_animation_group.start()

    def stop_save_animation(self):
        self.save_in_progress = False
        self.save_btn.setText("保存并关闭")
        if self.save_animation_group and self.save_animation_group.state() == QAbstractAnimation.State.Running:
            self.save_animation_group.stop()
        if self.save_btn_overlay:
            self.save_btn_overlay.hide()

    def on_update_models(self) -> None:
        self.status_label.setText("正在更新模型库...")
        self.update_thread = APIConfigDialogUpdateModelThread()
        self.update_thread.started_signal.connect(
            lambda: self.status_label.setText("正在更新模型库...")
        )
        self.update_thread.finished_signal.connect(self._on_models_updated)
        self.update_thread.error_signal.connect(
            lambda msg: [self.status_label.setText(f"更新出错: {msg}"), self.stop_update_animation()]
        )

        self.update_thread.start()
        self.start_update_animation()

    def _on_models_updated(self, available_models: Dict[str, List[str]]) -> None:
        self.stop_update_animation()

        # 先记录当前选中
        previously_selected = self._get_currently_selected_models()

        # 合并手动添加模型
        for api_name, models in self.available_models.items():
            if api_name in available_models:
                merged = set(available_models[api_name])
                merged.update(models)
                available_models[api_name] = sorted(list(merged))
            else:
                available_models[api_name] = models

        # 仅更新本地/UI，不触发全局外部配置更新
        self.available_models = available_models
        self._populate_model_ui(available_models, previously_selected)

        total = sum(len(m) for m in available_models.values())
        selected_count = sum(len(m) for m in previously_selected.values())
        self.status_label.setText(
            f"模型库更新完成！共 {total} 个模型，已选中 {selected_count} 个（点击“保存并关闭”生效）"
        )

    def _get_currently_selected_models(self) -> Dict[str, List[str]]:
        selected = {}
        for api_name, widgets in self.api_widgets.items():
            _, _, list_widget, _, _ = widgets
            selected_items = [item.text() for item in list_widget.selectedItems()]
            if selected_items:
                selected[api_name] = selected_items
        return selected

    def on_save_and_close(self):
        if self.save_in_progress:
            self.stop_save_animation()
            self.status_label.setText("保存已取消")
            QTimer.singleShot(2000, lambda: self.status_label.setText(""))
            return

        self.status_label.setText("正在保存配置...")
        self.start_save_animation()

    def _on_save_animation_finished(self):
        config = self._validate_and_save(
            show_message=True,
            apply_global=True,
            emit_signal=True,
            persist=True
        )
        self.save_btn_overlay.hide()
        self.save_in_progress = False
        self.save_btn.setText("保存并关闭")

        total_models = sum(len(provider.get("models", [])) for provider in config.values())
        self.notificationRequested.emit(
            f"模型列表更新完成。数量:{total_models}",
            "success"
        )
        self.close()

    def add_custom_api(self) -> None:
        name, ok = QInputDialog.getText(
            self, "添加自定义API供应商", "请输入供应商名称:", text="custom_api"
        )

        if ok and name:
            name = name.strip()
            if not name:
                QMessageBox.warning(self, "输入错误", "供应商名称不能为空")
                return

            if name in self.api_widgets:
                QMessageBox.warning(self, "名称冲突", "该供应商名称已存在")
                return

            self._create_api_tab(name, is_custom=True)
            self._validate_and_save(show_message=True)
            self.status_label.setText(f"已添加自定义供应商: {name}")
            QTimer.singleShot(2000, lambda: self.status_label.setText(""))

    def remove_custom_api(self, api_name: str) -> None:
        if api_name not in self.custom_apis:
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除'{api_name}'的配置吗?\n此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                widget = self.tab_widget.findChild(QWidget, api_name)
                if widget:
                    index = self.tab_widget.indexOf(widget)
                    if index != -1:
                        self.tab_widget.removeTab(index)
                        widget.deleteLater()

                if api_name in self.custom_apis:
                    self.custom_apis.remove(api_name)
                if api_name in self.api_widgets:
                    del self.api_widgets[api_name]
                if api_name in self.api_timers:
                    self.api_timers[api_name].stop()
                    del self.api_timers[api_name]
                if api_name in self.available_models:
                    del self.available_models[api_name]

                if api_name in APP_SETTINGS.api.providers:
                    del APP_SETTINGS.api.providers[api_name]

                self._validate_and_save()
                self.status_label.setText(f"已删除供应商: {api_name}")
                QTimer.singleShot(2000, lambda: self.status_label.setText(""))

            except Exception as e:
                QMessageBox.critical(self, "删除错误", f"删除时发生错误: {str(e)}")

    def load_config(self) -> None:
        providers = APP_SETTINGS.api.providers

        for api_name, config in providers.items():
            if api_name not in self.preset_apis and api_name not in self.api_widgets:
                self._create_api_tab(api_name, is_custom=True)

            if api_name in self.api_widgets:
                url_entry, key_entry, _, search_edit, type_combo = self.api_widgets[api_name]

                url_entry.blockSignals(True)
                key_entry.blockSignals(True)
                search_edit.blockSignals(True)
                type_combo.blockSignals(True)

                url_entry.setText(getattr(config, "url", ""))
                key_entry.setText(getattr(config, "key", ""))

                current_type = getattr(config, "provider_type", "openai_compatible")
                type_combo.setCurrentText(current_type)

                url_entry.blockSignals(False)
                key_entry.blockSignals(False)
                search_edit.blockSignals(False)
                type_combo.blockSignals(False)

            self.available_models[api_name] = list(getattr(config, "models", []))

        self._populate_model_ui(self.available_models, self.available_models)

    def _populate_model_ui(
        self,
        available_models: Dict[str, List[str]],
        selected_models_map: Dict[str, List[str]] = None
    ):
        selected_models_map = selected_models_map or {}
        for api_name, models in available_models.items():
            if api_name not in self.api_widgets:
                continue

            _, _, list_widget, search_edit, _ = self.api_widgets[api_name]

            # 更新UI时静默，避免触发 itemSelectionChanged
            list_widget.blockSignals(True)
            search_edit.blockSignals(True)
            try:
                list_widget.clear()
                for model in models:
                    list_widget.addItem(model)

                if api_name in selected_models_map:
                    self._select_models(api_name, selected_models_map[api_name])
            finally:
                list_widget.blockSignals(False)
                search_edit.blockSignals(False)

    def _select_models(self, api_name: str, model_names: List[str]) -> None:
        if api_name not in self.api_widgets:
            return

        _, _, list_widget, _, _ = self.api_widgets[api_name]
        target = set(model_names)
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item and item.text() in target:
                item.setSelected(True)

    def _collect_config_from_ui(self) -> dict:
        providers = {}
        for api_name, widgets in self.api_widgets.items():
            url_entry, key_entry, list_widget, _, type_combo = widgets
            url = url_entry.text().strip()
            key = key_entry.text().strip()
            models = [item.text() for item in list_widget.selectedItems()]
            p_type = type_combo.currentText().strip() or "openai_compatible"

            providers[api_name] = {
                "url": url,
                "key": key,
                "models": models,
                "provider_type": p_type
            }
        return providers

    def _validate_and_save(
        self,
        show_message: bool = True,
        apply_global: bool = True,
        emit_signal: bool = True,
        persist: bool = True
    ) -> dict:
        config_data = self._collect_config_from_ui()

        try:
            if apply_global:
                APP_SETTINGS.api.providers = config_data
                if persist:
                    ConfigManager.save_settings(APP_SETTINGS)

            if not self.initializing and show_message:
                self.status_label.setText("配置已保存")
                QTimer.singleShot(3000, lambda: self.status_label.setText(""))

            if apply_global and emit_signal:
                self.configUpdated.emit()

            return config_data

        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存时出错:\n{str(e)}")
            return {}

    def filter_models(self, api_name: str, search_text: str) -> None:
        if api_name not in self.api_widgets:
            return

        _, _, list_widget, _, _ = self.api_widgets[api_name]

        selected_items = [item.text() for item in list_widget.selectedItems()]

        items = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            text = item.text()
            score = self._calculate_match_score(text, search_text.lower())
            items.append((score, text))

        items.sort(key=lambda x: x[0], reverse=True)

        list_widget.blockSignals(True)
        try:
            list_widget.clear()
            for _score, text in items:
                item = QListWidgetItem(text)
                list_widget.addItem(item)
                if text in selected_items:
                    item.setSelected(True)
        finally:
            list_widget.blockSignals(False)

        if list_widget.count() > 0:
            list_widget.scrollToTop()

    def _calculate_match_score(self, text: str, search_text: str) -> int:
        if not search_text:
            return 0

        text_lower = text.lower()

        if text_lower == search_text:
            return 100
        if text_lower.startswith(search_text):
            return 90
        if search_text in text_lower:
            return 80 - text_lower.find(search_text)

        for word in text_lower.split():
            if word.startswith(search_text):
                return 50

        return 0
