from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from PyQt6.QtGui import QFont
from typing import Optional, Union, Callable,TYPE_CHECKING
if TYPE_CHECKING:
    from config import AppSettings

class LongChatSettingsWidget(QWidget):
    """
    长对话优化设置控件
    交互逻辑：
    1. 默认显示居中的开启按钮。
    2. 开启后进入分栏配置界面。
    3. 右侧面板根据左侧选择的模式动态切换显示的模板编辑框。
    """

    def __init__(self, settings: "AppSettings", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.settings = settings

        # 主布局使用堆叠布局，用于切换 [未启用页] 和 [配置页]
        self.main_stack = QStackedLayout(self)

        self._init_disabled_page()
        self._init_enabled_page()
        self.setup_connections()
        self._init_data() # 初始化数据

    def _init_disabled_page(self) -> None:
        """页面 0: 未启用状态 (居中显示开关)"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.center_cb = QCheckBox("启用长对话优化 | 上下文压缩")
        self.center_cb.setStyleSheet("""
            QCheckBox { font-size: 16px; font-weight: bold; spacing: 8px; }
            QCheckBox::indicator { width: 24px; height: 24px; }
        """)

        layout.addWidget(self.center_cb)
        self.main_stack.addWidget(page)

    def _init_enabled_page(self) -> None:
        """页面 1: 启用状态 (左右分栏)"""
        page = QWidget()
        main_layout = QHBoxLayout(page)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(15)

        # ================= 左侧：配置区 =================
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        #left_scroll.setFixedWidth(360) # 固定左侧宽度，防止过宽

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(15)
        left_layout.setContentsMargins(0, 0, 10, 0) # 右侧留点缝隙

        # 1. 顶部开关
        self.top_cb = QCheckBox("启用长对话优化 | 上下文压缩")
        self.top_cb.setStyleSheet("font-weight: bold; font-size: 14px;")
        left_layout.addWidget(self.top_cb)

        left_layout.addWidget(self._create_separator())

        # 2. 模型与模式 (合并在一起更紧凑)
        mode_group = QGroupBox("模式与模型")
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setSpacing(10)

        # API/Model 选择
        api_row = QHBoxLayout()
        api_row.addWidget(QLabel("API:"))
        self.api_provider_combo = QComboBox()
        api_row.addWidget(self.api_provider_combo, 1)
        api_row.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        api_row.addWidget(self.model_combo, 1)
        mode_layout.addLayout(api_row)

        # 模式单选
        self.rb_single = QRadioButton("完整重构 (Single)")
        self.rb_single.setToolTip("每次重写完整背景")
        self.rb_single.setProperty("mode_id", "single")

        self.rb_dispersed = QRadioButton("增量摘要 (Dispersed)")
        self.rb_dispersed.setToolTip("仅摘要新增内容")
        self.rb_dispersed.setProperty("mode_id", "dispersed")

        self.rb_mix = QRadioButton("混合模式 (Mix)")
        self.rb_mix.setToolTip("增量 + 定期全局整合")
        self.rb_mix.setProperty("mode_id", "mix")

        self.bg_mode = QButtonGroup(self)
        self.bg_mode.addButton(self.rb_single)
        self.bg_mode.addButton(self.rb_dispersed)
        self.bg_mode.addButton(self.rb_mix)

        mode_layout.addWidget(self.rb_single)
        mode_layout.addWidget(self.rb_dispersed)
        mode_layout.addWidget(self.rb_mix)

        left_layout.addWidget(mode_group)

        left_layout.addWidget(self._create_separator())

        # 3. 挂载与触发
        trigger_group = QGroupBox("参数设置")
        t_layout = QGridLayout(trigger_group)
        t_layout.setColumnStretch(0, 1)  # 标签列比例
        t_layout.setColumnStretch(1, 3)  # 输入框列比例（标签:输入框 = 1:3）

        # 挂载位置
        self.placement_combo = QComboBox()
        self.placement_combo.addItems(['系统提示', '对话第一位'])
        t_layout.addWidget(QLabel("挂载位置:"), 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        t_layout.addWidget(self.placement_combo, 0, 1)

        # 携带系统提示
        self.include_system_prompt = QCheckBox("携带原对话系统提示")
        t_layout.addWidget(self.include_system_prompt, 1, 0, 1, 2)

        # 触发时机 (滑块)
        self.max_total_length_edit = QLineEdit()
        self.max_total_length_slider = QSlider(Qt.Orientation.Horizontal)
        t_layout.addWidget(QLabel("历史总长 ≥"), 2, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        t_layout.addWidget(self._create_slider_widget(self.max_total_length_edit, self.max_total_length_slider), 2, 1)

        self.max_segment_length_edit = QLineEdit()
        self.max_segment_length_slider = QSlider(Qt.Orientation.Horizontal)
        t_layout.addWidget(QLabel("新增长度 ≥"), 3, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        t_layout.addWidget(self._create_slider_widget(self.max_segment_length_edit, self.max_segment_length_slider), 3, 1)

        left_layout.addWidget(trigger_group)

        left_layout.addWidget(self._create_separator())

        # 4. 关注点
        hint_group = QGroupBox("关注点 (Hint)")
        h_layout = QVBoxLayout(hint_group)

        h_layout.addWidget(QLabel("提示前缀:"))
        self.long_chat_hint_prefix_edit = QLineEdit()
        h_layout.addWidget(self.long_chat_hint_prefix_edit)

        h_layout.addWidget(QLabel("自定义指令:"))
        self.custom_hint_edit = QTextEdit()
        self.custom_hint_edit.setMaximumHeight(80)
        h_layout.addWidget(self.custom_hint_edit)

        left_layout.addWidget(hint_group)

        left_layout.addStretch() # 底部留白
        left_scroll.setWidget(left_widget)


        # ================= 右侧：模板 Tab =================
        self.right_tabs = QTabWidget()

        # Tab 1: 动态模板 (根据左侧模式切换)
        self.template_stack = QStackedWidget()

        # Stack 0: Single Templates
        self.page_single = QWidget()
        p_single_layout = QVBoxLayout(self.page_single)
        p_single_layout.addWidget(QLabel("<b>Single模式: 完整重构模板</b>"))
        p_single_layout.addWidget(QLabel("<span style='color:gray'>可用变量: {hint_text}, {context_summary}, {new_content}</span>"))
        self.single_update_prompt_edit = self._create_code_edit()
        p_single_layout.addWidget(self.single_update_prompt_edit)

        h_merge = QHBoxLayout()
        h_merge.addWidget(QLabel("合并连接符:"))
        self.summary_merge_prompt_edit = QLineEdit()
        self.summary_merge_prompt_and_edit = QLineEdit()
        #self.summary_merge_prompt_and_edit.setFixedWidth(60)
        h_merge.addWidget(self.summary_merge_prompt_edit)
        h_merge.addWidget(self.summary_merge_prompt_and_edit)
        p_single_layout.addLayout(h_merge)

        # Stack 1: Dispersed Templates
        self.page_dispersed = QWidget()
        p_disp_layout = QVBoxLayout(self.page_dispersed)
        p_disp_layout.addWidget(QLabel("<b>Dispersed模式: 增量摘要模板</b>"))
        p_disp_layout.addWidget(QLabel("<span style='color:gray'>可用变量: {new_content}, {context_summary}</span>"))
        self.dispersed_summary_prompt_edit = self._create_code_edit()
        p_disp_layout.addWidget(self.dispersed_summary_prompt_edit)

        # Stack 2: Mix Templates
        self.page_mix = QWidget()
        p_mix_layout = QVBoxLayout(self.page_mix)
        p_mix_layout.addWidget(QLabel("<b>Mix模式: 全局整合模板</b>"))
        p_mix_layout.addWidget(QLabel("<span style='color:gray'>可用变量: {dispersed_contents}</span>"))
        self.mix_consolidation_prompt_edit = self._create_code_edit()
        p_mix_layout.addWidget(self.mix_consolidation_prompt_edit)

        p_mix_layout.addWidget(QLabel("<i>* 注: Mix模式的增量阶段复用Dispersed模板</i>"))

        self.template_stack.addWidget(self.page_single)
        self.template_stack.addWidget(self.page_dispersed)
        self.template_stack.addWidget(self.page_mix)

        self.right_tabs.addTab(self.template_stack, "当前模式总结模板")

        # Tab 2: 通用 LCI 背景
        tab_general = QWidget()
        l_gen = QVBoxLayout(tab_general)
        l_gen.addWidget(QLabel("<b>通用LCI背景系统提示</b> (指导模型如何提取信息)"))
        self.summary_prompt_edit = self._create_code_edit()
        l_gen.addWidget(self.summary_prompt_edit)
        self.right_tabs.addTab(tab_general, "通用背景系统提示")

        main_layout.addWidget(left_scroll, 3)
        main_layout.addWidget(self.right_tabs, 8)

        self.main_stack.addWidget(page)

    # ================= 辅助控件生成 =================

    def _create_separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #dcdcdc;")
        return line

    def _create_slider_widget(self, edit: QLineEdit, slider: QSlider) -> QWidget:
        """组合 滑块+输入框 (左:右 = 1:3)"""
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0,0,0,0)
        l.setStretch(0, 1)  # 输入框比例
        l.setStretch(1, 3)  # 滑块比例
        edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        edit.setMaximumWidth(80)  # 限制输入框最大宽度
        slider.setMinimum(1000)
        slider.setMaximum(32000)
        slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        slider.setTickInterval(5000)
        l.addWidget(edit)
        l.addWidget(slider)
        return w

    def _create_code_edit(self) -> QTextEdit:
        edit = QTextEdit()
        font = QFont("Consolas, Menlo, Monaco, Courier New, monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        if font.exactMatch():
             edit.setFont(font)
        edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        return edit

    def _init_data(self) -> None:
        """核心数据初始化：从 Settings 读取并填充 UI"""
        s = self.settings
        lci = s.lci

        # 1. 填充 API Provider 列表
        # 获取所有 Provider 名字
        providers = list(s.api.providers.keys())
        self.api_provider_combo.blockSignals(True)
        self.api_provider_combo.clear()
        self.api_provider_combo.addItems(providers)

        # 选中当前 Provider
        if lci.api_provider and lci.api_provider in providers:
            self.api_provider_combo.setCurrentText(lci.api_provider)
        self.api_provider_combo.blockSignals(False)

        # 2. 填充 Model 列表 (基于当前选中的 Provider)
        self._refresh_models()
        # 选中当前 Model
        if lci.model:
            self.model_combo.setCurrentText(lci.model)

        # 3. 状态同步 - 两个 checkbox 保持一致
        is_enabled = lci.enabled
        self.center_cb.setChecked(is_enabled)
        self.top_cb.setChecked(is_enabled)
        self._toggle_view(is_enabled)

        # 4. 模式
        if lci.mode == 'single': self.rb_single.setChecked(True)
        elif lci.mode == 'dispersed': self.rb_dispersed.setChecked(True)
        elif lci.mode == 'mix': self.rb_mix.setChecked(True)
        self._update_template_stack(lci.mode)

        # 5. 触发器
        self.max_total_length_slider.setValue(lci.max_total_length)
        self.max_total_length_edit.setText(str(lci.max_total_length))
        self.max_segment_length_slider.setValue(lci.max_segment_length)
        self.max_segment_length_edit.setText(str(lci.max_segment_length))

        # 6. 其他
        self.placement_combo.setCurrentText(lci.placement)
        self.include_system_prompt.setChecked(lci.collect_system_prompt)

        # 7. 提示词
        self.long_chat_hint_prefix_edit.setText(lci.preset.long_chat_hint_prefix)
        self.custom_hint_edit.setText(lci.hint)
        self.single_update_prompt_edit.setText(lci.preset.single_update_prompt)
        self.summary_merge_prompt_edit.setText(lci.preset.summary_merge_prompt)
        self.summary_merge_prompt_and_edit.setText(lci.preset.summary_merge_prompt_and)
        self.dispersed_summary_prompt_edit.setText(lci.preset.dispersed_summary_prompt)
        self.mix_consolidation_prompt_edit.setText(lci.preset.mix_consolidation_prompt)
        self.summary_prompt_edit.setText(lci.preset.summary_prompt)

    def _toggle_view(self, enabled: bool) -> None:
        """切换 居中CB视图(0) 和 详细配置视图(1)"""
        self.main_stack.setCurrentIndex(1 if enabled else 0)

    def _refresh_models(self) -> None:
        """根据当前选中的 API Provider 刷新 Model 列表"""
        provider = self.api_provider_combo.currentText()
        if not provider:
            return

        # 使用 settings.api.model_map 获取对应模型的列表
        models = self.settings.api.model_map.get(provider, [])

        self.model_combo.blockSignals(True)
        current_model = self.model_combo.currentText() # 暂存
        self.model_combo.clear()
        self.model_combo.addItems(models)

        # 尝试恢复之前的选择，如果不在新列表中则默认选第一个
        if current_model in models:
            self.model_combo.setCurrentText(current_model)
        elif models:
            self.model_combo.setCurrentIndex(0)
            # 如果变了，需要更新 setting
            self.settings.lci.model = models[0]

        self.model_combo.blockSignals(False)

    def setup_connections(self) -> None:
        """绑定 UI 事件到 Settings 数据 (无外部信号)"""
        s = self.settings
        lci = s.lci
        preset = s.lci.preset

        # --- 状态切换同步 ---
        def set_enabled(v):
            is_checked = (v != 0)
            lci.enabled = is_checked
            # 同步两个 checkbox 的状态
            self.center_cb.blockSignals(True)
            self.top_cb.blockSignals(True)
            self.center_cb.setChecked(is_checked)
            self.top_cb.setChecked(is_checked)
            self.center_cb.blockSignals(False)
            self.top_cb.blockSignals(False)

            self._toggle_view(is_checked)

        self.center_cb.stateChanged.connect(set_enabled)
        self.top_cb.stateChanged.connect(set_enabled)

        # --- API ---
        def on_provider_change(txt):
            lci.api_provider = txt
            self._refresh_models()
            lci.model = self.model_combo.currentText()
        self.api_provider_combo.currentTextChanged.connect(on_provider_change)
        self.model_combo.currentTextChanged.connect(lambda v: setattr(lci, 'model', v))

        # --- 模式 ---
        def on_mode_toggled(btn, checked):
            if checked:
                mode = btn.property("mode_id")
                lci.mode = mode
                self._update_template_stack(mode) # 切换右侧显示的模板
        self.bg_mode.buttonToggled.connect(on_mode_toggled)

        # --- 触发与Misc ---
        self._setup_slider_link(self.max_total_length_edit, self.max_total_length_slider, 'max_total_length')
        self._setup_slider_link(self.max_segment_length_edit, self.max_segment_length_slider, 'max_segment_length')

        self.placement_combo.currentTextChanged.connect(lambda v: setattr(lci, 'placement', v))
        self.include_system_prompt.stateChanged.connect(lambda v: setattr(lci, 'collect_system_prompt', v!=0))

        # --- 文本 ---
        self._bind_text(self.custom_hint_edit, lambda v: setattr(lci, 'hint', v))
        self._bind_text(self.long_chat_hint_prefix_edit, lambda v: setattr(preset, 'long_chat_hint_prefix', v))
        self._bind_text(self.single_update_prompt_edit, lambda v: setattr(preset, 'single_update_prompt', v))
        self._bind_text(self.summary_merge_prompt_edit, lambda v: setattr(preset, 'summary_merge_prompt', v))
        self._bind_text(self.summary_merge_prompt_and_edit, lambda v: setattr(preset, 'summary_merge_prompt_and', v))
        self._bind_text(self.dispersed_summary_prompt_edit, lambda v: setattr(preset, 'dispersed_summary_prompt', v))
        self._bind_text(self.mix_consolidation_prompt_edit, lambda v: setattr(preset, 'mix_consolidation_prompt', v))
        self._bind_text(self.summary_prompt_edit, lambda v: setattr(preset, 'summary_prompt', v))

    def _update_template_stack(self, mode: str) -> None:
        """根据模式切换右侧 Stack 的页面"""
        idx_map = {"single": 0, "dispersed": 1, "mix": 2}
        if mode in idx_map:
            self.template_stack.setCurrentIndex(idx_map[mode])

    def _setup_slider_link(self, edit: QLineEdit, slider: QSlider, attr: str) -> None:
        edit.textChanged.connect(lambda: [slider.setValue(int(edit.text())), setattr(self.settings.lci, attr, int(edit.text()))] if edit.text().isdigit() else None)
        slider.valueChanged.connect(lambda v: [edit.setText(str(v)), setattr(self.settings.lci, attr, v)])

    def _bind_text(self, widget: Union[QTextEdit, QLineEdit], setter: Callable[[str], None]) -> None:
        if isinstance(widget, QTextEdit):
            widget.textChanged.connect(lambda: setter(widget.toPlainText()))
        elif isinstance(widget, QLineEdit):
            widget.textChanged.connect(lambda: setter(widget.text()))
