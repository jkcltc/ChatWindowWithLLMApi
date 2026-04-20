from PyQt6.QtCore import pyqtSignal,Qt
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QLabel,QHBoxLayout,QCheckBox,QGridLayout,QSlider,QSpinBox,QPushButton,QComboBox,QTextEdit,QFrame,QApplication,QSizePolicy,QFileDialog,QLineEdit,QScrollArea,QAbstractScrollArea,QTabWidget
from PyQt6.QtGui import QPixmap,QPainter,QPalette
from ui.custom_widget import QuickSeparator,AspectLabel
from config import APP_SETTINGS

class SectionWidget(QWidget):
    """分组组件模板，提供标题和分组框样式"""
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.layout:QVBoxLayout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(6)
        
        if title:
            title_label = QLabel(title)
            title_label.setStyleSheet("font-weight: bold;")
            self.layout.addWidget(title_label)

#背景生成设置UI
class BackgroundSettingsWidget(QWidget):
    """背景设置组件 - 直接读写 APP_SETTINGS"""

    updateModelRequested = pyqtSignal()
    updateImageModelRequested = pyqtSignal()
    previewImageChanged = pyqtSignal(str)  # 预览图变了，主类刷新UI
    updateSettingChanged = pyqtSignal(bool) # 主类有个进度条要刷新

    def __init__(self, parent=None):
        super().__init__(parent)
        self._initializing = False
        self._image_model_map = {}
        self.setup_ui()
        self.setup_connections()
        self.load_from_settings()
        self.update()
    @property
    def cfg(self):
        return APP_SETTINGS.background
    
    @property
    def model_map(self) -> dict:
        return APP_SETTINGS.api.model_map

    def set_image_model_map(self, model_map: dict):
        """外部设置图像模型映射后调用"""
        self._image_model_map = model_map
        self.load_from_settings()

    def setup_ui(self):
        # 主窗口设置
        self.setWindowTitle("背景设置")

        self._preview_pixmap = None
        self._background_pixmap = None

        # 主布局 - 左侧设置区域和右侧编辑区域
        main_layout = QHBoxLayout(self)
        
        # 左侧设置面板（滚动）
        settings_container = QWidget()
        settings_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        settings_layout = QVBoxLayout(settings_container)

        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        settings_scroll.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        settings_scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        settings_scroll.setWidget(settings_container)
 
        # 顶部标题（放到预览图上方）
        title_label = QLabel("背景设置")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        settings_layout.addWidget(title_label)
 
        preview_strip = QWidget()
        preview_strip_layout = QHBoxLayout(preview_strip)
        preview_strip_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_area = AspectLabel(text="背景预览")
        self.preview_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_area.setFrameShape(QFrame.Shape.Box)
        self.preview_area.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.preview_area.setMinimumHeight(self.fontMetrics().height() * 8)
        preview_strip_layout.addWidget(self.preview_area)

        settings_layout.addWidget(preview_strip)

        # 配置选项分组
        config_section = SectionWidget("更新配置")
        
        # 复选框设置
        self.enable_update_check = QCheckBox("跟随对话更新")
        self.specify_background_check = QCheckBox("指定背景")
        config_section.layout.addWidget(self.enable_update_check)
        config_section.layout.addWidget(self.specify_background_check)
        
        # 间隔设置
        interval_group = QWidget()
        interval_layout = QGridLayout(interval_group)
        interval_layout.setContentsMargins(0, 0, 0, 0)
        
        interval_label = QLabel("更新间隔")
        self.update_slider = QSlider(Qt.Orientation.Horizontal)
        self.update_slider.setEnabled(False)
        self.update_slider.setRange(1, 100)
        self.update_slider.setValue(15)
        self.update_spin = QSpinBox()
        self.update_spin.setEnabled(False)
        self.update_spin.setRange(1, 100)
        self.update_spin.setValue(15)
        self.update_spin.setSuffix('次对话')
        self.update_spin.setSingleStep(1)
        
        interval_layout.addWidget(interval_label, 0, 0)
        interval_layout.addWidget(self.update_slider, 1, 0)
        interval_layout.addWidget(self.update_spin, 1, 1, Qt.AlignmentFlag.AlignRight)
        
        config_section.layout.addWidget(interval_group)
        
        # 对话长度设置
        history_group = QWidget()
        history_layout = QGridLayout(history_group)
        history_layout.setContentsMargins(0, 0, 0, 0)
        
        history_label = QLabel("参考对话长度")
        self.history_slider = QSlider(Qt.Orientation.Horizontal)
        self.history_slider.setEnabled(False)
        self.history_slider.setRange(200, 128000)
        self.history_slider.setValue(500)
        self.history_slider.setSingleStep(100)
        self.history_spin = QSpinBox()
        self.history_spin.setEnabled(False)
        self.history_spin.setRange(200, 128000)
        self.history_spin.setValue(500)
        self.history_spin.setSingleStep(100)
        
        history_layout.addWidget(history_label, 0, 0)
        history_layout.addWidget(self.history_slider, 1, 0)
        history_layout.addWidget(self.history_spin, 1, 1, Qt.AlignmentFlag.AlignRight)
        
        config_section.layout.addWidget(history_group)
        
        settings_layout.addWidget(config_section)


        # 分隔线
        settings_layout.addWidget(QuickSeparator("h"))
        
        # 提示词模型分组
        model_section = SectionWidget("提示词生成模型")
        
        model_row = QHBoxLayout()
        model_row.setContentsMargins(0, 0, 0, 0)
        model_label = QLabel("模型选择")
        model_label.setSizePolicy(model_label.sizePolicy().horizontalPolicy(), 
                                 model_label.sizePolicy().verticalPolicy())
        self.update_model_button = QPushButton('更新模型')
        model_row.addWidget(model_label)
        model_row.addStretch()
        model_row.addWidget(self.update_model_button)
        model_section.layout.addLayout(model_row)
        
        provider_row = QVBoxLayout()
        provider_row.setContentsMargins(0, 0, 0, 0)
        provider_label = QLabel("提供商")
        self.provider_combo = QComboBox()
        provider_row.addWidget(provider_label)
        provider_row.addWidget(self.provider_combo)
        model_section.layout.addLayout(provider_row)
        
        model_name_row = QVBoxLayout()
        model_name_row.setContentsMargins(0, 0, 0, 0)
        model_name_label = QLabel("模型名称")
        self.model_combo = QComboBox()
        model_name_row.addWidget(model_name_label)
        model_name_row.addWidget(self.model_combo)
        model_section.layout.addLayout(model_name_row)
        
        settings_layout.addWidget(model_section)
        
        # 分隔线
        settings_layout.addWidget(QuickSeparator("h"))
        
        # 绘图模型分组
        image_model_section = SectionWidget("绘图模型")
        
        image_row = QHBoxLayout()
        image_row.setContentsMargins(0, 0, 0, 0)
        image_label = QLabel("模型选择")
        self.update_image_model_button = QPushButton('更新模型')
        image_row.addWidget(image_label)
        image_row.addStretch()
        image_row.addWidget(self.update_image_model_button)
        image_model_section.layout.addLayout(image_row)
        
        image_provider_row = QVBoxLayout()
        image_provider_row.setContentsMargins(0, 0, 0, 0)
        image_provider_label = QLabel("提供商")
        self.image_provider_combo = QComboBox()
        image_provider_row.addWidget(image_provider_label)
        image_provider_row.addWidget(self.image_provider_combo)
        image_model_section.layout.addLayout(image_provider_row)
        
        image_model_name_row = QVBoxLayout()
        image_model_name_row.setContentsMargins(0, 0, 0, 0)
        image_model_name_label = QLabel("模型名称")
        self.image_model_combo = QComboBox()
        image_model_name_row.addWidget(image_model_name_label)
        image_model_name_row.addWidget(self.image_model_combo)
        image_model_section.layout.addLayout(image_model_name_row)
        
        settings_layout.addWidget(image_model_section)  

        # 分隔线
        settings_layout.addWidget(QuickSeparator("h"))
        
        # 生成风格编辑区（与 stylehint 并排放到右侧预设区）
        self.style_text_edit = QLineEdit()
        self.style_text_edit.setPlaceholderText("在此输入生成风格描述...")

        # 设置面板添加到主布局左侧
        main_layout.addWidget(settings_scroll, 0)

        # 垂直分隔线
        separator = QuickSeparator("v")
        separator.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        main_layout.addWidget(separator, 0)

        preset_tabs = QTabWidget()
        preset_tabs.setObjectName("backgroundPresetTabs")
        preset_tabs.setStyleSheet(
            "#backgroundPresetTabs { background: transparent; }"
            "#backgroundPresetTabs::pane { background: transparent; border: none; }"
            "#backgroundPresetTabs QTabBar { background: transparent; }"
        )

        self.style_hint_edit = QLineEdit()
        self.scene_hint_edit = QLineEdit()
        self.system_prompt_hint_edit = QTextEdit()
        self.summary_prompt_edit = QTextEdit()
        self.user_summary_edit = QTextEdit()

        rule_tab = QWidget()
        rule_tab_layout = QVBoxLayout(rule_tab)
        rule_tab_layout.setSpacing(12)
        rule_tab_layout.setContentsMargins(0, 0, 0, 0)
        rule_tab_layout.addWidget(self.summary_prompt_edit)

        rule_scroll = QScrollArea()
        rule_scroll.setWidgetResizable(True)
        rule_scroll.setFrameShape(QFrame.Shape.NoFrame)
        rule_scroll.setWidget(rule_tab)

        prompt_tab = QWidget()
        prompt_tab_layout = QVBoxLayout(prompt_tab)
        prompt_tab_layout.setSpacing(12)
        prompt_tab_layout.setContentsMargins(0, 0, 0, 0)
        prompt_tab_layout.addWidget(QLabel("全局记忆标注"))
        prompt_tab_layout.addWidget(self.system_prompt_hint_edit)
        prompt_tab_layout.addWidget(QLabel("场景标注"))
        prompt_tab_layout.addWidget(self.scene_hint_edit)
        prompt_tab_layout.addWidget(QLabel("生成指令"))
        prompt_tab_layout.addWidget(self.user_summary_edit)

        style_row_layout = QHBoxLayout()
        style_row_layout.setContentsMargins(0, 0, 0, 0)
        style_row_layout.setSpacing(12)

        style_hint_group = QWidget()
        style_hint_layout = QVBoxLayout(style_hint_group)
        style_hint_layout.setContentsMargins(0, 0, 0, 0)
        style_hint_layout.addWidget(QLabel("风格提示"))
        style_hint_layout.addWidget(self.style_hint_edit)

        style_text_group = QWidget()
        style_text_layout = QVBoxLayout(style_text_group)
        style_text_layout.setContentsMargins(0, 0, 0, 0)
        style_text_layout.addWidget(QLabel("生成风格"))
        style_text_layout.addWidget(self.style_text_edit)

        style_row_layout.addWidget(style_hint_group, 1)
        style_row_layout.addWidget(style_text_group, 1)

        prompt_tab_layout.addLayout(style_row_layout)

        prompt_scroll = QScrollArea()
        prompt_scroll.setWidgetResizable(True)
        prompt_scroll.setFrameShape(QFrame.Shape.NoFrame)
        prompt_scroll.setWidget(prompt_tab)

        preset_tabs.addTab(rule_scroll, "场景提取规则")
        preset_tabs.addTab(prompt_scroll, "标注与指令")

        # 右侧面板透明：避免全局 QWidget 背景覆盖
        transparent_palette = QPalette()
        transparent_palette.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.transparent)
        transparent_palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.transparent)

        for tab in (rule_tab, prompt_tab):
            tab.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            tab.setAutoFillBackground(False)
            tab.setPalette(transparent_palette)
            tab.setStyleSheet("background: transparent;")

        for scroll in (rule_scroll, prompt_scroll):
            scroll.setAutoFillBackground(False)
            viewport = scroll.viewport()
            viewport.setAutoFillBackground(False)
            viewport.setPalette(transparent_palette)

        for edit in (
            self.summary_prompt_edit,
            self.system_prompt_hint_edit,
            self.user_summary_edit,
        ):
            edit.setAutoFillBackground(False)
            edit.viewport().setAutoFillBackground(False)
            edit.viewport().setPalette(transparent_palette)

        # 右侧面板透明：限制在 backgroundPresetTabs 内部
        preset_tabs.setStyleSheet(
            "#backgroundPresetTabs { background: transparent; }"
            "#backgroundPresetTabs::pane { background: transparent; border: none; }"
            "#backgroundPresetTabs QTabBar { background: transparent; }"
            "#backgroundPresetTabs QScrollArea { background: transparent; border: none; }"
            "#backgroundPresetTabs QScrollArea::viewport { background: transparent; }"
            "#backgroundPresetTabs QTextEdit, #backgroundPresetTabs QLineEdit { background: transparent; }"
            "#backgroundPresetTabs QWidget { background: transparent; }"
        )

        # 添加到主布局右侧
        main_layout.addWidget(preset_tabs, 1)

        self._main_layout = main_layout
        self._settings_panel = settings_scroll
        self._preset_panel = preset_tabs
        self._separator = separator

        main_layout.setStretch(0, 3)
        main_layout.setStretch(1, 0)
        main_layout.setStretch(2, 8)

    def load_from_settings(self):
        """从 APP_SETTINGS 加载到控件"""
        self._initializing = True
        # 怎么光flag没有用的
        # self.blockSignals(True)
        try:
            preset = self.cfg.preset
            # --- 模型下拉框 ---
            self.provider_combo.clear()
            self.provider_combo.addItems(list(self.model_map.keys()))

            self.image_provider_combo.clear()
            self.image_provider_combo.addItems(list(self._image_model_map.keys()))

            # 设置当前选中的 provider 和 model
            if self.cfg.summary_provider in self.model_map:
                self.provider_combo.setCurrentText(self.cfg.summary_provider)
                self.model_combo.clear()
                self.model_combo.addItems(self.model_map[self.cfg.summary_provider])
                if self.cfg.summary_model in self.model_map[self.cfg.summary_provider]:
                    self.model_combo.setCurrentText(self.cfg.summary_model)

            if self.cfg.image_provider in self._image_model_map:
                self.image_provider_combo.setCurrentText(self.cfg.image_provider)
                self.image_model_combo.clear()
                self.image_model_combo.addItems(self._image_model_map[self.cfg.image_provider])
                if self.cfg.image_model in self._image_model_map[self.cfg.image_provider]:
                    self.image_model_combo.setCurrentText(self.cfg.image_model)

            # --- 开关和数值 ---
            self.enable_update_check.setChecked(self.cfg.enabled)
            self.specify_background_check.setChecked(self.cfg.lock)

            self.update_slider.setValue(self.cfg.max_rounds)
            self.update_spin.setValue(self.cfg.max_rounds)

            self.history_slider.setValue(self.cfg.max_length)
            self.history_spin.setValue(self.cfg.max_length)

            self.style_text_edit.setText(self.cfg.style)

            self.style_hint_edit.setText(preset.style_hint)
            self.scene_hint_edit.setText(preset.scene_hint)
            self.system_prompt_hint_edit.setText(preset.system_prompt_hint)
            self.summary_prompt_edit.setText(preset.summary_prompt)
            self.user_summary_edit.setText(preset.user_summary)

            # --- 控件启用状态 ---
            self._update_controls_enabled(self.cfg.enabled)

            # --- 背景预览 ---
            if self.cfg.lock and self.cfg.image_path:
                self._update_preview_image(self.cfg.image_path)
            else:
                self.preview_area.clear()
                self.preview_area.setText("背景预览")

        finally:
            self._initializing = False
            #self.blockSignals(False)
    
    # ==================== UI变更 → 写入配置 ====================

    def _on_provider_changed(self, provider: str):
        if not provider or self._initializing:
            return
        self.cfg.summary_provider = provider
        # 更新模型下拉框
        self.model_combo.clear()
        if provider in self.model_map:
            self.model_combo.addItems(self.model_map.get(provider, []))

    def _on_model_changed(self, model: str):
        if not model or self._initializing:
            return
        self.cfg.summary_model = model

    def _on_image_provider_changed(self, provider: str):
        if not provider or self._initializing:
            return
        self.cfg.image_provider = provider
        self.image_model_combo.clear()
        if provider in self._image_model_map:
            self.image_model_combo.addItems(self._image_model_map[provider])

    def _on_image_model_changed(self, model: str):
        if not model or self._initializing:
            return
        self.cfg.image_model = model

    def _on_enabled_changed(self, enabled: bool):
        if self._initializing:
            return
        self.cfg.enabled = enabled
        self._update_controls_enabled(enabled)
        if enabled:
            self.specify_background_check.setChecked(False)
        self.updateSettingChanged.emit(enabled)

    def _on_max_rounds_changed(self, value: int):
        if self._initializing:
            return
        self.cfg.max_rounds = value
        # 同步 slider 和 spin
        if self.sender() == self.update_slider:
            self.update_spin.blockSignals(True)
            self.update_spin.setValue(value)
            self.update_spin.blockSignals(False)
        else:
            self.update_slider.blockSignals(True)
            self.update_slider.setValue(value)
            self.update_slider.blockSignals(False)

    def _on_max_length_changed(self, value: int):
        if self._initializing:
            return
        self.cfg.max_length = value

        if self.sender() == self.history_slider:
            self.history_spin.blockSignals(True)
            self.history_spin.setValue(value)
            self.history_spin.blockSignals(False)
        else:
            self.history_slider.blockSignals(True)
            self.history_slider.setValue(value)
            self.history_slider.blockSignals(False)

    def _on_style_changed(self):
        if self._initializing:
            return
        self.cfg.style = self.style_text_edit.text()

    def _on_preset_style_hint_changed(self, text: str):
        if self._initializing:
            return
        self.cfg.preset.style_hint = text

    def _on_preset_scene_hint_changed(self, text: str):
        if self._initializing:
            return
        self.cfg.preset.scene_hint = text

    def _on_preset_system_prompt_hint_changed(self):
        if self._initializing:
            return
        self.cfg.preset.system_prompt_hint = self.system_prompt_hint_edit.toPlainText()

    def _on_preset_summary_prompt_changed(self):
        if self._initializing:
            return
        self.cfg.preset.summary_prompt = self.summary_prompt_edit.toPlainText()

    def _on_preset_user_summary_changed(self):
        if self._initializing:
            return
        self.cfg.preset.user_summary = self.user_summary_edit.toPlainText()

    def _on_preset_irag_use_chinese_changed(self, text: str):
        if self._initializing:
            return
        self.cfg.preset.IRAG_USE_CHINESE = text
    
    # ==================== 连接信号 ====================
    def setup_connections(self):
        # 模型选择
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        self.image_provider_combo.currentTextChanged.connect(self._on_image_provider_changed)
        self.image_model_combo.currentTextChanged.connect(self._on_image_model_changed)

        # 开关
        self.enable_update_check.toggled.connect(self._on_enabled_changed)
        self.specify_background_check.toggled.connect(self._on_lock_changed)

        # 数值
        self.update_slider.valueChanged.connect(self._on_max_rounds_changed)
        self.update_spin.valueChanged.connect(self._on_max_rounds_changed)
        self.history_slider.valueChanged.connect(self._on_max_length_changed)
        self.history_spin.valueChanged.connect(self._on_max_length_changed)

        # 文本
        self.style_text_edit.textChanged.connect(self._on_style_changed)
        self.style_hint_edit.textChanged.connect(self._on_preset_style_hint_changed)
        self.scene_hint_edit.textChanged.connect(self._on_preset_scene_hint_changed)
        self.system_prompt_hint_edit.textChanged.connect(self._on_preset_system_prompt_hint_changed)
        self.summary_prompt_edit.textChanged.connect(self._on_preset_summary_prompt_changed)
        self.user_summary_edit.textChanged.connect(self._on_preset_user_summary_changed)

        # 刷新按钮（这个还是要信号，让外部去拉新的模型列表）
        self.update_model_button.clicked.connect(self.updateModelRequested.emit)
        self.update_image_model_button.clicked.connect(self.updateImageModelRequested.emit)



    def _on_lock_changed(self, checked: bool):
        """处理指定背景复选框状态变化"""
        if self._initializing:
            return

        if checked:
            self._initializing = True
            self.enable_update_check.setChecked(False)
            self._initializing = False

            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择背景图片",
                "",
                "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
            )

            if file_path:
                self.cfg.image_path = file_path
                self.cfg.lock = True
                self._update_preview_image(file_path)
                self.previewImageChanged.emit(file_path)
            else:
                self._initializing = True
                self.specify_background_check.setChecked(False)
                self._initializing = False
                self.cfg.lock = False
        else:
            self.cfg.lock = False
            self.cfg.image_path = ''
            # 改这里：用 clear() 会同时清掉 master_pixmap
            self.preview_area.clear()
            self.preview_area.setText("背景预览")
            self._background_pixmap = None
            self.update()
            self.previewImageChanged.emit("")

    def _update_preview_image(self, file_path: str):
        """更新预览区域的图片"""
        if not file_path:
            self.preview_area.clear()
            self.preview_area.setText("背景预览")
            self._background_pixmap = None
            self.update()
            return

        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            self.preview_area.clear()
            self.preview_area.setText("图片加载失败")
            self._background_pixmap = None
            self.update()
            return

        self._background_pixmap = pixmap
        self.preview_area.setText('')  # 清掉文字
        self.preview_area.update_icon(pixmap)
        self.update()

    def _update_controls_enabled(self, enabled: bool):
        """启用/禁用相关控件"""
        self.update_slider.setEnabled(enabled)
        self.update_spin.setEnabled(enabled)
        self.history_slider.setEnabled(enabled)
        self.history_spin.setEnabled(enabled)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._background_pixmap or self._background_pixmap.isNull():
            return

        painter = QPainter(self)
        painter.setOpacity(0.18)
        scaled = self._background_pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)

    def show(self):
        super().show()
        self.resize(int(1.5 * self.height()), self.height())

        screen = QApplication.primaryScreen()
        if self.parent():
            screen = self.parent().screen()

        screen_geometry = screen.availableGeometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2

        self.move(screen_geometry.left() + x, screen_geometry.top() + y)
