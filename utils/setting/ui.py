from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from PyQt6.QtGui import QPixmap
from utils.setting.data import APP_SETTINGS, AppSettings
#简易小组件
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


class MainSettingWindow(QWidget):
    lci_enabled_changed = pyqtSignal(bool)       
    title_provider_changed = pyqtSignal(str, str)    

    def __init__(self, settings: AppSettings = None, parent=None):
        super().__init__(parent)
        self.settings = settings or APP_SETTINGS
        self.init_ui()           # ← 加这行
        self.setup_connections() # ← 加这行

    def init_ui(self):
        self.setWindowTitle("对话设置")
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        
        width = int(screen_geometry.width() * 0.6)
        height = int(screen_geometry.height() * 0.6)
        
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
        """创建长对话优化选项卡"""
        long_chat_tab = QWidget()
        layout = QVBoxLayout()

        # 启用设置
        enable_layout = QHBoxLayout()
        self.long_chat_checkbox = QCheckBox("启用自动长对话优化")
        enable_layout.addWidget(self.long_chat_checkbox)
        enable_layout.addStretch()

        # 挂载位置
        placement_layout = QHBoxLayout()
        placement_layout.addWidget(QLabel("挂载位置:"))
        self.placement_combo = QComboBox()
        self.placement_combo.addItems(['系统提示', '对话第一位'])
        placement_layout.addWidget(self.placement_combo)
        placement_layout.addStretch()

        # 携带系统提示
        self.include_system_prompt = QCheckBox("携带系统提示")
        self.include_system_prompt.setToolTip(
            '在发送摘要请求时携带系统提示。\n'
            '如果系统提示中包含人设等信息，\n'
            '可以帮助摘要模型理解对话。'
        )

        # API设置
        api_layout = QHBoxLayout()
        api_layout.addWidget(QLabel("指定API:"))
        self.api_provider_combo = QComboBox()
        api_layout.addWidget(self.api_provider_combo, 1)

        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("指定模型:"))
        self.model_combo = QComboBox()
        model_layout.addWidget(self.model_combo, 1)

        # 自定义提示
        hint_group = QGroupBox("优先保留记忆")
        hint_layout = QVBoxLayout()
        self.custom_hint_edit = QTextEdit()
        self.custom_hint_edit.setMaximumHeight(150)
        hint_layout.addWidget(self.custom_hint_edit)
        hint_group.setLayout(hint_layout)

        # 添加到布局
        layout.addLayout(enable_layout)
        layout.addLayout(placement_layout)
        layout.addWidget(self.include_system_prompt)
        layout.addLayout(api_layout)
        layout.addLayout(model_layout)
        layout.addWidget(hint_group)
        layout.addStretch()

        long_chat_tab.setLayout(layout)
        self.tab_widget.addTab(long_chat_tab, "长对话优化")

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
                    pass # 忽略 float 转换时的非法输入
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

        # === LCI (长上下文) ===
        self.long_chat_checkbox.stateChanged.connect(self._handle_lci_enabled) # 复杂联动保留

        def set_lci_sys(v): s.lci.collect_system_prompt = v
        bind(self.include_system_prompt.stateChanged, set_lci_sys, to_bool)

        def set_lci_place(v): s.lci.placement = v
        bind(self.placement_combo.currentTextChanged, set_lci_place)

        self.api_provider_combo.currentTextChanged.connect(self._handle_lci_provider) # 复杂联动保留

        def set_lci_model(v): s.lci.model = v
        bind(self.model_combo.currentTextChanged, set_lci_model)

        # 特殊：QTextEdit 信号不带参数，需主动获取
        def set_lci_hint(v): s.lci.hint = v
        bind_text_edit(self.custom_hint_edit.textChanged, 
                       self.custom_hint_edit.toPlainText, 
                       set_lci_hint)

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

    def _handle_lci_enabled(self, state):
        enabled = state != 0
        self.settings.lci.enabled = enabled
        self.lci_enabled_changed.emit(enabled)

    def _handle_lci_provider(self, text):
        self.settings.lci.api_provider = text
        self.model_combo.blockSignals(True)
        self._update_model_combo()
        self.model_combo.blockSignals(False)

    def _handle_title_method(self, checked):
        if self.title_local_radio.isChecked() == checked:  # 防止重复触发
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
    def _update_model_combo(self):
        provider = self.api_provider_combo.currentText()
        models = self.settings.api.model_map.get(provider, [])
        self.model_combo.clear()
        self.model_combo.addItems(models)

    def _update_title_model_combo(self):
        provider = self.title_provider_combo.currentText()
        models = self.settings.api.model_map.get(provider, [])
        self.title_model_combo.clear()
        self.title_model_combo.addItems(models)

    def _populate_provider_combos(self):
        providers = list(self.settings.api.model_map.keys())
        self.api_provider_combo.clear()
        self.api_provider_combo.addItems(providers)
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


        # LCI
        self.long_chat_checkbox.setChecked(s.lci.enabled)
        self.include_system_prompt.setChecked(s.lci.collect_system_prompt)
        self.placement_combo.setCurrentText(s.lci.placement)
        self.api_provider_combo.setCurrentText(s.lci.api_provider or '')
        self._update_model_combo()
        self.model_combo.setCurrentText(s.lci.model or '')
        self.custom_hint_edit.setText(s.lci.hint)

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
            self.long_chat_checkbox, self.include_system_prompt,
            self.placement_combo, self.api_provider_combo, self.model_combo,
            self.custom_hint_edit,
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
