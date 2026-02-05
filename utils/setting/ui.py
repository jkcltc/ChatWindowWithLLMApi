from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from PyQt6.QtGui import QFont
from utils.setting.data import APP_SETTINGS, AppSettings

# 简易小组件
class QuickSeparator(QFrame):
    """统一风格的分隔线组件"""
    def __init__(self, orientation="h"):
        super().__init__()
        if orientation == "h":
            self.setFrameShape(QFrame.Shape.HLine)
            self.setFrameShadow(QFrame.Shadow.Sunken)
        else:
            self.setFrameShape(QFrame.Shape.VLine)
            self.setFrameShadow(QFrame.Shadow.Sunken)

class LongChatSettingsWidget(QWidget):
    """
    长对话优化设置控件 (Refactored v4)
    交互逻辑：
    1. 默认显示居中的开启按钮。
    2. 开启后进入分栏配置界面。
    3. 右侧面板根据左侧选择的模式动态切换显示的模板编辑框。
    """

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings

        # 主布局使用堆叠布局，用于切换 [未启用页] 和 [配置页]
        self.main_stack = QStackedLayout(self)

        self._init_disabled_page()
        self._init_enabled_page()
        self.setup_connections()
        self._init_data() # 初始化数据

    def _init_disabled_page(self):
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

    def _init_enabled_page(self):
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
        t_layout.setColumnMinimumWidth(0, 80)  # 标签最小宽度

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

        main_layout.addWidget(left_scroll, 4)  # 左侧占比 4
        main_layout.addWidget(self.right_tabs, 6)  # 右侧占比 6

        self.main_stack.addWidget(page)

    # ================= 辅助控件生成 =================

    def _create_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #dcdcdc;")
        return line

    def _create_slider_widget(self, edit, slider):
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

    def _create_code_edit(self):
        edit = QTextEdit()
        font = QFont("Consolas, Menlo, Monaco, Courier New, monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        if font.exactMatch():
             edit.setFont(font)
        edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        return edit

    def _init_data(self):
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

    def _toggle_view(self, enabled):
        """切换 居中CB视图(0) 和 详细配置视图(1)"""
        self.main_stack.setCurrentIndex(1 if enabled else 0)

    def _refresh_models(self):
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

    def setup_connections(self):
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

    def _update_template_stack(self, mode):
        """根据模式切换右侧 Stack 的页面"""
        idx_map = {"single": 0, "dispersed": 1, "mix": 2}
        if mode in idx_map:
            self.template_stack.setCurrentIndex(idx_map[mode])

    def _setup_slider_link(self, edit, slider, attr):
        edit.textChanged.connect(lambda: [slider.setValue(int(edit.text())), setattr(self.settings.lci, attr, int(edit.text()))] if edit.text().isdigit() else None)
        slider.valueChanged.connect(lambda v: [edit.setText(str(v)), setattr(self.settings.lci, attr, v)])

    def _bind_text(self, widget, setter):
        if isinstance(widget, QTextEdit):
            widget.textChanged.connect(lambda: setter(widget.toPlainText()))
        elif isinstance(widget, QLineEdit):
            widget.textChanged.connect(lambda: setter(widget.text()))

class MainSettingWindow(QWidget):
    lci_enabled_changed = pyqtSignal(bool)       
    title_provider_changed = pyqtSignal(str, str)    

    def __init__(self, settings: AppSettings = None, parent=None):
        super().__init__(parent)
        self.settings = settings or APP_SETTINGS
        self.init_ui()
        self.setup_connections()

    def init_ui(self):
        self.setWindowTitle("对话设置")
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        
        width = int(screen_geometry.width() * 0.7)
        height = int(screen_geometry.height() * 0.7)
        
        left = (screen_geometry.width() - width) // 2
        top = (screen_geometry.height() - height) // 2
        
        self.setGeometry(left, top, width, height)

        # 创建主布局和选项卡
        main_layout = QVBoxLayout()
        self.tab_widget = QTabWidget()
        
        # 创建各个选项卡
        self.create_basic_tab()
        self.create_long_chat_tab()
        self.create_parameter_tab()
        self.create_replace_tab()
        self.create_name_tab()
        self.create_title_creator_tab()
        
        # 将选项卡添加到主窗口
        main_layout.addWidget(self.tab_widget)
        
        # 确认按钮放在底部
        self.confirm_button = QPushButton("完成")
        main_layout.addWidget(self.confirm_button)
        
        self.setLayout(main_layout)

    def create_basic_tab(self):
        """创建基本设置选项卡"""
        basic_tab = QWidget()
        layout = QVBoxLayout()

        # === 最大对话轮数设置 ===
        rounds_group = QGroupBox("上传对话数设置")
        rounds_layout = QVBoxLayout()

        rounds_input_layout = QHBoxLayout()
        rounds_input_layout.addWidget(QLabel("上传对话数(无上限):"))
        self.max_rounds_edit = QLineEdit()
        rounds_input_layout.addWidget(self.max_rounds_edit)
        rounds_input_layout.addStretch()

        self.max_rounds_slider = QSlider(Qt.Orientation.Horizontal)
        self.max_rounds_slider.setMinimum(-1)
        self.max_rounds_slider.setMaximum(500)

        rounds_layout.addLayout(rounds_input_layout)
        rounds_layout.addWidget(self.max_rounds_slider)
        rounds_group.setLayout(rounds_layout)

        # === 传输模式设置 ===
        stream_group = QGroupBox("传输模式")
        stream_layout = QVBoxLayout()

        self.stream_receive_radio = QRadioButton("流式接收信息")
        self.complete_receive_radio = QRadioButton("完整接收信息")

        stream_layout.addWidget(self.stream_receive_radio)
        stream_layout.addWidget(self.complete_receive_radio)
        stream_group.setLayout(stream_layout)

        # === 组装 ===
        layout.addWidget(rounds_group)
        layout.addWidget(stream_group)
        layout.addStretch()

        basic_tab.setLayout(layout)
        self.tab_widget.addTab(basic_tab, "基本设置")

    def create_long_chat_tab(self):
        """创建长对话优化选项卡 - 使用独立的LongChatSettingsWidget"""
        self.lci_widget = LongChatSettingsWidget(self.settings)
        self.lci_widget.top_cb.toggled.connect(self.lci_enabled_changed)
        self.tab_widget.addTab(self.lci_widget, "长对话优化")

    def create_parameter_tab(self):
        """创建参数设置选项卡"""
        param_tab = QWidget()
        layout = QVBoxLayout()

        # 参数设置组
        param_group = QGroupBox("AI参数设置")
        param_layout = QGridLayout()

        # top_p 设置
        self.top_p_checkbox = QCheckBox('启用词汇多样性(top_p)')
        param_layout.addWidget(self.top_p_checkbox, 0, 0)

        top_p_input_layout = QHBoxLayout()
        top_p_input_layout.addWidget(QLabel("值:"))
        self.top_p_edit = QLineEdit()
        self.top_p_edit.setMaximumWidth(80)
        top_p_input_layout.addWidget(self.top_p_edit)
        top_p_input_layout.addWidget(QLabel("(0.0-1.0)"))
        top_p_input_layout.addStretch()
        param_layout.addLayout(top_p_input_layout, 0, 1)

        # temperature 设置
        self.temp_checkbox = QCheckBox('启用自我放飞度(temperature)')
        param_layout.addWidget(self.temp_checkbox, 1, 0)

        temp_input_layout = QHBoxLayout()
        temp_input_layout.addWidget(QLabel("值:"))
        self.temp_edit = QLineEdit()
        self.temp_edit.setMaximumWidth(80)
        temp_input_layout.addWidget(self.temp_edit)
        temp_input_layout.addWidget(QLabel("(0.0-2.0)"))
        temp_input_layout.addStretch()
        param_layout.addLayout(temp_input_layout, 1, 1)

        # presence_penalty 设置
        self.penalty_checkbox = QCheckBox('启用词意重复惩罚(presence_penalty)')
        param_layout.addWidget(self.penalty_checkbox, 2, 0)

        penalty_input_layout = QHBoxLayout()
        penalty_input_layout.addWidget(QLabel("值:"))
        self.penalty_edit = QLineEdit()
        self.penalty_edit.setMaximumWidth(80)
        penalty_input_layout.addWidget(self.penalty_edit)
        penalty_input_layout.addWidget(QLabel("(-2.0-2.0)"))
        penalty_input_layout.addStretch()
        param_layout.addLayout(penalty_input_layout, 2, 1)

        param_group.setLayout(param_layout)
        layout.addWidget(param_group)
        layout.addStretch()

        param_tab.setLayout(layout)
        self.tab_widget.addTab(param_tab, "AI参数")

    def create_replace_tab(self):
        """创建自动替换选项卡"""
        replace_tab = QWidget()
        layout = QVBoxLayout()

        # 自动替换设置
        replace_group = QGroupBox("自动替换设置")
        replace_layout = QVBoxLayout()

        # 启用复选框
        self.autoreplace_checkbox = QCheckBox("启用自动替换")
        replace_layout.addWidget(self.autoreplace_checkbox)

        # 替换规则
        rule_layout = QVBoxLayout()
        rule_layout.addWidget(QLabel("替换规则 (分隔符为 ; , 需正则时前缀 re:#)"))

        from_layout = QHBoxLayout()
        from_layout.addWidget(QLabel("将:"))
        self.autoreplace_from_edit = QLineEdit()
        from_layout.addWidget(self.autoreplace_from_edit)

        to_layout = QHBoxLayout()
        to_layout.addWidget(QLabel("替换为:"))
        self.autoreplace_to_edit = QLineEdit()
        to_layout.addWidget(self.autoreplace_to_edit)

        rule_layout.addLayout(from_layout)
        rule_layout.addLayout(to_layout)
        replace_layout.addLayout(rule_layout)

        replace_group.setLayout(replace_layout)
        layout.addWidget(replace_group)
        layout.addStretch()

        replace_tab.setLayout(layout)
        self.tab_widget.addTab(replace_tab, "自动替换")

    def create_name_tab(self):
        """创建代称设置选项卡"""
        name_tab = QWidget()
        layout = QVBoxLayout()

        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # 代称设置组
        name_group = QGroupBox("对话代称设置")
        name_layout = QGridLayout()

        name_layout.setContentsMargins(10, 20, 10, 10) 
        name_layout.setVerticalSpacing(12)
        name_layout.setHorizontalSpacing(10)

        name_layout.addWidget(QuickSeparator(), 0, 0, 1, 2)

        self.character_enforce_checkbox = QCheckBox("消息携带额外name字段")

        name_layout.addWidget(self.character_enforce_checkbox, 1, 0, 1, 2)

        name_layout.addWidget(QuickSeparator(), 2, 0, 1, 2)

        # 标签和输入框对齐
        name_layout.addWidget(QLabel("你的代称:"), 3, 0)
        self.user_name_edit = QLineEdit() 
        name_layout.addWidget(self.user_name_edit, 3, 1)

        name_layout.addWidget(QLabel("AI的代称:"), 4, 0)
        self.ai_name_edit = QLineEdit() 
        name_layout.addWidget(self.ai_name_edit, 4, 1)

        name_layout.addWidget(QuickSeparator(), 5, 0, 1, 2)

        desc_label = QLabel("设置后，如果预设未设置代称，"
                           "则对话中将使用这些代称。"
                           "如果全部为空，将使用模型名。")
        desc_label.setWordWrap(True)

        name_layout.addWidget(desc_label, 6, 0, 1, 2) 

        name_group.setLayout(name_layout)
        layout.addWidget(name_group)
        layout.addStretch()

        name_tab.setLayout(layout)
        self.tab_widget.addTab(name_tab, "代称设置")

    def create_title_creator_tab(self):
        """创建标题生成设置选项卡"""
        title_tab = QWidget()
        layout = QVBoxLayout()

        # 标题生成设置组
        title_group = QGroupBox("标题生成设置")
        title_layout = QVBoxLayout()

        # === 生成方式选择 ===
        method_group = QGroupBox("生成方式")
        method_layout = QHBoxLayout()

        self.title_local_radio = QRadioButton("使用本地生成")
        self.title_llm_radio = QRadioButton("使用LLM生成")

        method_layout.addWidget(self.title_local_radio)
        method_layout.addWidget(self.title_llm_radio)
        method_layout.addStretch()
        method_group.setLayout(method_layout)
        title_layout.addWidget(method_group)

        # === 堆叠窗口 ===
        self.title_stack = QStackedWidget()

        # 本地生成页面
        local_page = QWidget()
        local_layout = QVBoxLayout()
        local_layout.addWidget(QLabel("使用本地算法生成标题"))
        local_layout.addStretch()
        local_page.setLayout(local_layout)

        # LLM生成页面
        llm_page = QWidget()
        llm_layout = QVBoxLayout()

        # 启用系统提示
        self.title_system_prompt_checkbox = QCheckBox("携带系统提示")
        self.title_system_prompt_checkbox.setToolTip("系统提示将作为标题生成的上下文")
        llm_layout.addWidget(self.title_system_prompt_checkbox)

        # 最大标题长度
        max_length_layout = QHBoxLayout()
        max_length_layout.addWidget(QLabel("最大标题长度:"))
        self.title_max_length_edit = QLineEdit()
        self.title_max_length_edit.setMaximumWidth(60)
        max_length_layout.addWidget(self.title_max_length_edit)

        self.title_max_length_slider = QSlider(Qt.Orientation.Horizontal)
        self.title_max_length_slider.setMinimum(5)
        self.title_max_length_slider.setMaximum(50)
        max_length_layout.addWidget(self.title_max_length_slider)
        llm_layout.addLayout(max_length_layout)

        # API提供者
        api_layout = QHBoxLayout()
        api_layout.addWidget(QLabel("指定API:"))
        self.title_provider_combo = QComboBox()
        api_layout.addWidget(self.title_provider_combo, 1)
        api_layout.addStretch()
        llm_layout.addLayout(api_layout)

        # 模型选择
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("指定模型:"))
        self.title_model_combo = QComboBox()
        model_layout.addWidget(self.title_model_combo, 1)
        model_layout.addStretch()
        llm_layout.addLayout(model_layout)

        llm_layout.addStretch()
        llm_page.setLayout(llm_layout)

        # 添加到堆叠窗口
        self.title_stack.addWidget(local_page)
        self.title_stack.addWidget(llm_page)

        title_layout.addWidget(self.title_stack)
        title_group.setLayout(title_layout)
        layout.addWidget(title_group)
        layout.addStretch()

        title_tab.setLayout(layout)
        self.tab_widget.addTab(title_tab, "标题生成")

    def setup_connections(self):
        s = self.settings
        to_bool = lambda state: state != 0
        to_float = float

        # 通用绑定函数：信号 -> 转换 -> 赋值
        def bind(signal, setter, converter=None):
            def _slot(value):
                try:
                    if converter:
                        value = converter(value)
                    setter(value)
                except ValueError as e:
                    print(f"转换失败: {e}")
                    pass
            signal.connect(_slot)

        # 3. 无参绑定函数：专门对付 QTextEdit 这种信号不带参数的组件
        def bind_text_edit(signal, ui_getter, setter):
            signal.connect(lambda: setter(ui_getter()))

        # === 最大轮数 ===
        self.max_rounds_edit.textChanged.connect(self._handle_max_rounds_text)
        self.max_rounds_slider.valueChanged.connect(self._handle_max_rounds_slider)

        # === 流式接收 ===
        def set_stream(v): s.generation.stream_receive = v
        bind(self.stream_receive_radio.toggled, set_stream)

        # === 生成参数 (TopP / Temp / Penalty) ===

        # Top P
        def set_top_p_en(v): s.generation.top_p_enable = v
        bind(self.top_p_checkbox.stateChanged, set_top_p_en, to_bool)

        def set_top_p(v): s.generation.top_p = v
        bind(self.top_p_edit.textChanged, set_top_p, to_float)

        # Temperature
        def set_temp_en(v): s.generation.temperature_enable = v
        bind(self.temp_checkbox.stateChanged, set_temp_en, to_bool)

        def set_temp(v): s.generation.temperature = v
        bind(self.temp_edit.textChanged, set_temp, to_float)

        # Penalty
        def set_penalty_en(v): s.generation.presence_penalty_enable = v
        bind(self.penalty_checkbox.stateChanged, set_penalty_en, to_bool)

        def set_penalty(v): s.generation.presence_penalty = v
        bind(self.penalty_edit.textChanged, set_penalty, to_float)

        # === 自动替换 ===
        def set_replace_en(v): s.replace.autoreplace_var = v
        bind(self.autoreplace_checkbox.stateChanged, set_replace_en, to_bool)

        def set_replace_from(v): s.replace.autoreplace_from = v
        bind(self.autoreplace_from_edit.textChanged, set_replace_from)

        def set_replace_to(v): s.replace.autoreplace_to = v
        bind(self.autoreplace_to_edit.textChanged, set_replace_to)

        # === 代称 (带信号发射) ===
        def set_user_name(v): s.names.user = v
        bind(self.user_name_edit.textChanged, set_user_name)

        def set_ai_name(v): s.names.ai = v
        bind(self.ai_name_edit.textChanged, set_ai_name)

        def set_char_enforce(v): s.names.character_enforce = v
        bind(self.character_enforce_checkbox.stateChanged, set_char_enforce, to_bool)

        # === 标题生成 ===
        self.title_local_radio.toggled.connect(self._handle_title_method)

        def set_title_sys(v): s.title.include_sys_pmt = v
        bind(self.title_system_prompt_checkbox.stateChanged, set_title_sys, to_bool)

        self.title_max_length_edit.textChanged.connect(self._handle_title_max_length_text)
        self.title_max_length_slider.valueChanged.connect(self._handle_title_max_length_slider)
        self.title_provider_combo.currentTextChanged.connect(self._handle_title_provider)

        def update_title_model(text):
            s.title.model = text
            self.title_provider_changed.emit(s.title.provider, text)
        bind(self.title_model_combo.currentTextChanged, update_title_model)

        # === 确认按钮 ===
        self.confirm_button.clicked.connect(self.close)

    # ====== 辅助方法 ======
    def _set_float(self, obj, attr, text):
        try:
            setattr(obj, attr, float(text))
        except ValueError:
            pass

    def _handle_max_rounds_text(self, text):
        try:
            value = int(text)
            self.max_rounds_slider.blockSignals(True)
            self.max_rounds_slider.setValue(value)
            self.max_rounds_slider.blockSignals(False)
            self.settings.limits.max_send_rounds = value if value >= 0 else 999
        except ValueError:
            pass

    def _handle_max_rounds_slider(self, value):
        self.max_rounds_edit.blockSignals(True)
        self.max_rounds_edit.setText(str(value))
        self.max_rounds_edit.blockSignals(False)
        self.settings.limits.max_send_rounds = value if value >= 0 else 999

    def _handle_title_method(self, checked):
        if self.title_local_radio.isChecked() == checked:
            self.settings.title.use_local = checked
            self.title_stack.setCurrentIndex(0 if checked else 1)

    def _handle_title_max_length_text(self, text):
        try:
            value = int(text)
            self.title_max_length_slider.blockSignals(True)
            self.title_max_length_slider.setValue(value)
            self.title_max_length_slider.blockSignals(False)
            self.settings.title.max_length = value
        except ValueError:
            pass

    def _handle_title_max_length_slider(self, value):
        self.title_max_length_edit.blockSignals(True)
        self.title_max_length_edit.setText(str(value))
        self.title_max_length_edit.blockSignals(False)
        self.settings.title.max_length = value

    def _handle_title_provider(self, text):
        self.settings.title.provider = text
        self._update_title_model_combo()
        self.title_provider_changed.emit(text, self.settings.title.model)

    # ====== 下拉框更新 ======
    def _update_title_model_combo(self):
        provider = self.title_provider_combo.currentText()
        models = self.settings.api.model_map.get(provider, [])
        self.title_model_combo.clear()
        self.title_model_combo.addItems(models)

    def _populate_provider_combos(self):
        providers = list(self.settings.api.model_map.keys())
        self.title_provider_combo.clear()
        self.title_provider_combo.addItems(providers)

    # ====== 值填充 ======
    def populate_values(self):
        """从 settings 读取并填充所有控件"""
        s = self.settings

        # 全部阻塞信号，防止填充时触发回调
        self._block_all_signals(True)

        # 先填充下拉框选项
        self._populate_provider_combos()

        # 生成参数
        self.max_rounds_edit.setText(str(s.limits.max_send_rounds))
        self.max_rounds_slider.setValue(s.limits.max_send_rounds)
        self.top_p_checkbox.setChecked(s.generation.top_p_enable)
        self.top_p_edit.setText(str(s.generation.top_p))
        self.temp_checkbox.setChecked(s.generation.temperature_enable)
        self.temp_edit.setText(str(s.generation.temperature))
        self.penalty_checkbox.setChecked(s.generation.presence_penalty_enable)
        self.penalty_edit.setText(str(s.generation.presence_penalty))

        # 流式接收
        self.stream_receive_radio.setChecked(s.generation.stream_receive)
        self.complete_receive_radio.setChecked(not s.generation.stream_receive)

        # 自动替换
        self.autoreplace_checkbox.setChecked(s.replace.autoreplace_var)
        self.autoreplace_from_edit.setText(s.replace.autoreplace_from)
        self.autoreplace_to_edit.setText(s.replace.autoreplace_to)

        # 代称
        self.user_name_edit.setText(s.names.user)
        self.ai_name_edit.setText(s.names.ai)
        self.character_enforce_checkbox.setChecked(s.names.character_enforce)

        # 标题生成
        self.title_local_radio.setChecked(s.title.use_local)
        self.title_llm_radio.setChecked(not s.title.use_local)
        self.title_stack.setCurrentIndex(0 if s.title.use_local else 1)
        self.title_system_prompt_checkbox.setChecked(s.title.include_sys_pmt)
        self.title_max_length_edit.setText(str(s.title.max_length))
        self.title_max_length_slider.setValue(s.title.max_length)
        self.title_provider_combo.setCurrentText(s.title.provider)
        self._update_title_model_combo()
        self.title_model_combo.setCurrentText(s.title.model)

        self._block_all_signals(False)

    def _block_all_signals(self, block: bool):
        """批量阻塞/恢复信号"""
        widgets = [
            self.max_rounds_edit, self.max_rounds_slider,
            self.top_p_checkbox, self.top_p_edit,
            self.temp_checkbox, self.temp_edit,
            self.penalty_checkbox, self.penalty_edit,
            self.autoreplace_checkbox, self.autoreplace_from_edit, self.autoreplace_to_edit,
            self.user_name_edit, self.ai_name_edit,
            self.title_local_radio, self.title_llm_radio,
            self.title_system_prompt_checkbox,
            self.title_max_length_edit, self.title_max_length_slider,
            self.title_provider_combo, self.title_model_combo,
            self.stream_receive_radio, self.complete_receive_radio,
        ]
        for w in widgets:
            w.blockSignals(block)
