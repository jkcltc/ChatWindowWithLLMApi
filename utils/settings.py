from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from PyQt6.QtGui import QPixmap
import sys,os,configparser

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

class SendMethodWindow(QWidget):
    stream_receive_changed = pyqtSignal(bool)
    def __init__(self, initial_stream_receive=True):
        super().__init__()
        self.setWindowTitle("选择接收方式")
        
        layout = QVBoxLayout()
        
        # 创建单选按钮
        self.stream_receive_radio = QRadioButton("流式接收信息")
        self.stream_receive_radio.setChecked(initial_stream_receive)
        
        self.complete_receive_radio = QRadioButton("完整接收信息")
        self.complete_receive_radio.setChecked(not initial_stream_receive)
        
        # 连接状态变更信号
        self.stream_receive_radio.toggled.connect(
            lambda checked: self.stream_receive_changed.emit(True)
        )
        self.complete_receive_radio.toggled.connect(
            lambda checked: self.stream_receive_changed.emit(False)
        )

        # 添加控件到布局
        layout.addWidget(self.stream_receive_radio)
        layout.addWidget(self.complete_receive_radio)
        
        self.setLayout(layout)

    def setState(self,state):
        self.blockSignals(True)
        self.stream_receive_radio.setChecked(state)
        self.complete_receive_radio.setChecked(not state)
        self.blockSignals(False)

class MainSettingWindow(QWidget):
    # 定义所有信号
    max_rounds_changed = pyqtSignal(int)
    long_chat_improve_changed = pyqtSignal(bool)
    long_chat_placement_changed = pyqtSignal(str)
    long_chat_api_provider_changed = pyqtSignal(str)
    long_chat_model_changed = pyqtSignal(str)
    top_p_changed = pyqtSignal(float)
    temperature_changed = pyqtSignal(float)
    presence_penalty_changed = pyqtSignal(float)
    top_p_enable_changed = pyqtSignal(bool)
    temperature_enable_changed = pyqtSignal(bool)
    presence_penalty_enable_changed = pyqtSignal(bool)
    custom_hint_changed = pyqtSignal(str)
    autoreplace_changed = pyqtSignal(bool)
    autoreplace_from_changed = pyqtSignal(str)
    autoreplace_to_changed = pyqtSignal(str)
    user_name_changed = pyqtSignal(str)
    assistant_name_changed = pyqtSignal(str)
    window_closed = pyqtSignal()
    stream_receive_changed= pyqtSignal(bool)
    include_system_prompt_changed=pyqtSignal(bool)

    title_creator_system_prompt_changed=pyqtSignal(bool)
    title_creator_use_local_changed=pyqtSignal(bool)
    title_creator_max_length_changed=pyqtSignal(int)
    title_creator_provider_changed=pyqtSignal(str)
    title_creator_model_changed=pyqtSignal(str)

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config or {}
        self.init_smw()
        self.init_ui()
        self.setup_connections()

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
        
        # 最大对话轮数设置
        rounds_group = QGroupBox("上传对话数设置")
        rounds_layout = QVBoxLayout()
        
        rounds_input_layout = QHBoxLayout()
        rounds_input_layout.addWidget(QLabel("上传对话数(无上限):"))
        self.max_rounds_edit = QLineEdit()
        self.max_rounds_edit.setText(str(self.config.get('max_message_rounds', 10)))
        rounds_input_layout.addWidget(self.max_rounds_edit)
        rounds_input_layout.addStretch()
        
        self.max_rounds_slider = QSlider(Qt.Orientation.Horizontal)
        self.max_rounds_slider.setMinimum(-1)
        self.max_rounds_slider.setMaximum(500)
        self.max_rounds_slider.setValue(self.config.get('max_message_rounds', 10))
        
        rounds_layout.addLayout(rounds_input_layout)
        rounds_layout.addWidget(self.max_rounds_slider)
        rounds_group.setLayout(rounds_layout)
        
        # 传输模式设置
        stream_group = QGroupBox("传输模式")
        stream_layout = QVBoxLayout()
        stream_layout.addWidget(self.stream_setting)
        stream_group.setLayout(stream_layout)
        
        # 添加到基本设置选项卡
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
        self.long_chat_checkbox.setChecked(self.config.get('long_chat_improve_var', False))
        enable_layout.addWidget(self.long_chat_checkbox)
        enable_layout.addStretch()
        
        # 挂载位置
        placement_layout = QHBoxLayout()
        placement_layout.addWidget(QLabel("挂载位置:"))
        self.placement_combo = QComboBox()
        self.placement_combo.addItems(['系统提示', '对话第一位'])
        self.placement_combo.setCurrentText(self.config.get('long_chat_placement', '系统提示'))
        placement_layout.addWidget(self.placement_combo)
        placement_layout.addStretch()
        
        # 携带系统提示
        self.include_system_prompt = QCheckBox("携带系统提示")
        self.include_system_prompt.setToolTip('在发送摘要请求时携带系统提示。\n如果系统提示中包含人设等信息，\n可以帮助摘要模型理解对话。')
        self.include_system_prompt.setChecked(self.config.get('enable_lci_system_prompt', True))
        
        # API设置
        api_layout = QHBoxLayout()
        api_layout.addWidget(QLabel("指定API:"))
        self.api_provider_combo = QComboBox()
        self.api_provider_combo.addItems(list(self.config.get('MODEL_MAP', {}).keys()))
        self.api_provider_combo.setCurrentText(self.config.get('long_chat_improve_api_provider', ''))
        api_layout.addWidget(self.api_provider_combo, 1) # Add stretch factor
        
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("指定模型:"))
        self.model_combo = QComboBox()
        self.update_model_combo()
        self.model_combo.setCurrentText(self.config.get('long_chat_improve_model', ''))
        model_layout.addWidget(self.model_combo, 1) # Add stretch factor
        
        # 自定义提示
        hint_group = QGroupBox("优先保留记忆（也可用于私货）")
        hint_layout = QVBoxLayout()
        self.custom_hint_edit = QTextEdit()
        self.custom_hint_edit.setText(self.config.get('long_chat_hint', ''))
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
        self.top_p_checkbox.setChecked(self.config.get('top_p_enable', False))
        param_layout.addWidget(self.top_p_checkbox, 0, 0)
        
        top_p_input_layout = QHBoxLayout()
        top_p_input_layout.addWidget(QLabel("值:"))
        self.top_p_edit = QLineEdit(str(self.config.get('top_p', 0.7)))
        self.top_p_edit.setMaximumWidth(80)
        top_p_input_layout.addWidget(self.top_p_edit)
        top_p_input_layout.addWidget(QLabel("(0.0-1.0)"))
        top_p_input_layout.addStretch()
        param_layout.addLayout(top_p_input_layout, 0, 1)
        
        # temperature 设置
        self.temp_checkbox = QCheckBox('启用自我放飞度(temperature)')
        self.temp_checkbox.setChecked(self.config.get('temperature_enable', False))
        param_layout.addWidget(self.temp_checkbox, 1, 0)
        
        temp_input_layout = QHBoxLayout()
        temp_input_layout.addWidget(QLabel("值:"))
        self.temp_edit = QLineEdit(str(self.config.get('temperature', 1.0)))
        self.temp_edit.setMaximumWidth(80)
        temp_input_layout.addWidget(self.temp_edit)
        temp_input_layout.addWidget(QLabel("(0.0-2.0)"))
        temp_input_layout.addStretch()
        param_layout.addLayout(temp_input_layout, 1, 1)
        
        # presence_penalty 设置
        self.penalty_checkbox = QCheckBox('启用词意重复惩罚(presence_penalty)')
        self.penalty_checkbox.setChecked(self.config.get('presence_penalty_enable', False))
        param_layout.addWidget(self.penalty_checkbox, 2, 0)
        
        penalty_input_layout = QHBoxLayout()
        penalty_input_layout.addWidget(QLabel("值:"))
        self.penalty_edit = QLineEdit(str(self.config.get('presence_penalty', 0.0)))
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
        self.autoreplace_checkbox.setChecked(self.config.get('autoreplace_var', False))
        replace_layout.addWidget(self.autoreplace_checkbox)
        
        # 替换规则
        rule_layout = QVBoxLayout()
        rule_layout.addWidget(QLabel("替换规则 (分隔符为 ; , 需正则时前缀 re:#)"))
        
        from_layout = QHBoxLayout()
        from_layout.addWidget(QLabel("将:"))
        self.autoreplace_from_edit = QLineEdit(self.config.get('autoreplace_from', ''))
        from_layout.addWidget(self.autoreplace_from_edit)
        
        to_layout = QHBoxLayout()
        to_layout.addWidget(QLabel("替换为:"))
        self.autoreplace_to_edit = QLineEdit(self.config.get('autoreplace_to', ''))
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
        
        # 代称设置组
        name_group = QGroupBox("对话代称设置")
        name_layout = QGridLayout()
        
        name_layout.addWidget(QLabel("聊天记录中你的代称:"), 0, 0)
        self.user_name_edit = QLineEdit(self.config.get('name_user', '用户'))
        name_layout.addWidget(self.user_name_edit, 0, 1)
        
        name_layout.addWidget(QLabel("聊天记录中AI的代称:"), 1, 0)
        self.ai_name_edit = QLineEdit(self.config.get('name_ai', 'AI'))
        name_layout.addWidget(self.ai_name_edit, 1, 1)
        
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
        
        # 生成方式选择（单选按钮）
        method_group = QGroupBox("生成方式")
        method_layout = QHBoxLayout()
        
        self.title_local_radio = QRadioButton("使用本地生成")
        self.title_llm_radio = QRadioButton("使用LLM生成")
        
        # 设置默认选择
        use_local = self.config.get('title_creator_use_local', False)
        self.title_local_radio.setChecked(use_local)
        self.title_llm_radio.setChecked(not use_local)
        
        method_layout.addWidget(self.title_local_radio)
        method_layout.addWidget(self.title_llm_radio)
        method_layout.addStretch()
        method_group.setLayout(method_layout)
        title_layout.addWidget(method_group)
        
        # 创建堆叠窗口
        self.title_stack = QStackedWidget()
        
        # 本地生成页面（简单页面，可以留空或添加本地特定设置）
        local_page = QWidget()
        local_layout = QVBoxLayout()
        local_layout.addWidget(QLabel("使用本地算法生成标题"))
        local_layout.addStretch()
        local_page.setLayout(local_layout)
        
        # LLM生成页面（详细设置）
        llm_page = QWidget()
        llm_layout = QVBoxLayout()
        
        # 启用系统提示
        self.title_system_prompt_checkbox = QCheckBox("启用系统提示")
        self.title_system_prompt_checkbox.setChecked(self.config.get('title_creator_system_prompt', True))
        self.title_system_prompt_checkbox.setToolTip("为标题生成使用专门的系统提示")
        llm_layout.addWidget(self.title_system_prompt_checkbox)
        
        # 最大标题长度
        max_length_layout = QHBoxLayout()
        max_length_layout.addWidget(QLabel("最大标题长度:"))
        self.title_max_length_edit = QLineEdit()
        self.title_max_length_edit.setText(str(self.config.get('title_creator_max_length', 20)))
        self.title_max_length_edit.setMaximumWidth(60)
        max_length_layout.addWidget(self.title_max_length_edit)
        
        self.title_max_length_slider = QSlider(Qt.Orientation.Horizontal)
        self.title_max_length_slider.setMinimum(5)
        self.title_max_length_slider.setMaximum(50)
        self.title_max_length_slider.setValue(self.config.get('title_creator_max_length', 20))
        max_length_layout.addWidget(self.title_max_length_slider)
        llm_layout.addLayout(max_length_layout)
        
        # API提供者
        api_layout = QHBoxLayout()
        api_layout.addWidget(QLabel("指定API:"))
        self.title_provider_combo = QComboBox()
        self.title_provider_combo.addItems(list(self.config.get('MODEL_MAP', {}).keys()))
        self.title_provider_combo.setCurrentText(self.config.get('title_creator_provider', ''))
        api_layout.addWidget(self.title_provider_combo,1)
        api_layout.addStretch()
        llm_layout.addLayout(api_layout)
        
        # 模型选择
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("指定模型:"))
        self.title_model_combo = QComboBox()
        self.update_title_model_combo()
        self.title_model_combo.setCurrentText(self.config.get('title_creator_model', ''))
        model_layout.addWidget(self.title_model_combo,1)
        model_layout.addStretch()
        llm_layout.addLayout(model_layout)
        
        llm_layout.addStretch()
        llm_page.setLayout(llm_layout)
        
        # 将页面添加到堆叠窗口
        self.title_stack.addWidget(local_page)
        self.title_stack.addWidget(llm_page)
        
        # 根据当前选择设置堆叠窗口的索引
        self.title_stack.setCurrentIndex(0 if use_local else 1)
        
        title_layout.addWidget(self.title_stack)
        title_group.setLayout(title_layout)
        layout.addWidget(title_group)
        layout.addStretch()
        
        title_tab.setLayout(layout)
        self.tab_widget.addTab(title_tab, "标题生成")
    
    def init_smw(self):
        '''
        SendMethodWindow
        '''
        def emit_src(_):
            self.stream_receive_changed.emit(_)
        self.stream_setting=SendMethodWindow()
        self.stream_setting.stream_receive_changed.connect(emit_src)


    def setup_connections(self):
        # 最大轮数设置
        self.max_rounds_edit.textChanged.connect(self.handle_max_rounds_text)
        self.max_rounds_slider.valueChanged.connect(self.handle_max_rounds_slider)
        
        # 长对话优化
        self.long_chat_checkbox.stateChanged.connect(
            lambda state: self.long_chat_improve_changed.emit(state == Qt.CheckState.Checked))
        
        self.include_system_prompt.stateChanged.connect(self.include_system_prompt_changed.emit)

        
        self.placement_combo.currentTextChanged.connect(
            self.long_chat_placement_changed.emit)
        
        self.api_provider_combo.currentTextChanged.connect(
            lambda text: (self.update_model_combo(), 
                          self.long_chat_api_provider_changed.emit(text)))
        
        self.model_combo.currentTextChanged.connect(
            self.long_chat_model_changed.emit)
        
        # 参数设置
        self.top_p_checkbox.stateChanged.connect(
            lambda state: self.top_p_enable_changed.emit(state == Qt.CheckState.Checked))
        self.top_p_edit.textChanged.connect(
            lambda text: self.handle_float_change(text, self.top_p_changed))
        
        self.temp_checkbox.stateChanged.connect(
            lambda state: self.temperature_enable_changed.emit(state == Qt.CheckState.Checked))
        self.temp_edit.textChanged.connect(
            lambda text: self.handle_float_change(text, self.temperature_changed))
        
        self.penalty_checkbox.stateChanged.connect(
            lambda state: self.presence_penalty_enable_changed.emit(state == Qt.CheckState.Checked))
        self.penalty_edit.textChanged.connect(
            lambda text: self.handle_float_change(text, self.presence_penalty_changed))
        
        # 自定义提示
        self.custom_hint_edit.textChanged.connect(
            lambda: self.custom_hint_changed.emit(self.custom_hint_edit.toPlainText()))
        
        # 自动替换
        self.autoreplace_checkbox.stateChanged.connect(
            lambda state: self.autoreplace_changed.emit(state == Qt.CheckState.Checked))
        self.autoreplace_from_edit.textChanged.connect(
            self.autoreplace_from_changed.emit)
        self.autoreplace_to_edit.textChanged.connect(
            self.autoreplace_to_changed.emit)
        
        # 代称设置
        self.user_name_edit.textChanged.connect(self.user_name_changed.emit)
        self.ai_name_edit.textChanged.connect(self.assistant_name_changed.emit)

        # 标题生成设置连接
        self.title_local_radio.toggled.connect(self.handle_title_method_changed)
        self.title_llm_radio.toggled.connect(self.handle_title_method_changed)
        
        self.title_system_prompt_checkbox.stateChanged.connect(
            lambda state: self.title_creator_system_prompt_changed.emit(state == Qt.CheckState.Checked))
        
        self.title_max_length_edit.textChanged.connect(
            lambda text: self.handle_title_max_length_text(text))
        
        self.title_max_length_slider.valueChanged.connect(
            lambda value: self.handle_title_max_length_slider(value))
        
        self.title_provider_combo.currentTextChanged.connect(
            lambda text: (self.update_title_model_combo(), 
                         self.title_creator_provider_changed.emit(text)))
        
        self.title_model_combo.currentTextChanged.connect(
            self.title_creator_model_changed.emit)
        
        # 确认按钮
        self.confirm_button.clicked.connect(self.close)

    def update_api_provider_combo(self):
        model_map = self.config.get('MODEL_MAP', {})
        self.api_provider_combo.clear()
        self.api_provider_combo.addItems(list(model_map.keys()))
        self.api_provider_combo.setCurrentText(self.config.get('long_chat_improve_api_provider', ''))

    def update_model_combo(self):
        current_api = self.api_provider_combo.currentText()
        model_map = self.config.get('MODEL_MAP', {})
        self.model_combo.clear()
        if current_api in model_map:
            self.model_combo.addItems(model_map[current_api])

    def handle_max_rounds_text(self, text):
        try:
            value = int(text)
            self.max_rounds_slider.setValue(value)
            self.max_rounds_changed.emit(value if value >= 0 else 999)
        except ValueError:
            pass

    def handle_max_rounds_slider(self, value):
        self.max_rounds_edit.setText(str(value))
        self.max_rounds_changed.emit(value if value >= 0 else 999)

    def handle_float_change(self, text, signal):
        try:
            value = float(text)
            signal.emit(value)
        except ValueError:
            pass

    def update_title_model_combo(self):
        """更新标题生成模型下拉框"""
        current_api = self.title_provider_combo.currentText()
        model_map = self.config.get('MODEL_MAP', {})
        self.title_model_combo.clear()
        if current_api in model_map:
            self.title_model_combo.addItems(model_map[current_api])

    def populate_values(self,config):
        """填充控件值的方法"""
        self.config:dict=config
        self.blockSignals(True)
        self.update_api_provider_combo()
        self.update_model_combo()
        self.update_title_model_combo()
        
        # 最大对话轮数设置
        self.max_rounds_edit.setText(str(self.config.get('max_message_rounds', 10)))
        self.max_rounds_slider.setValue(self.config.get('max_message_rounds', 10))

        #流式设置
        self.stream_setting.setState(self.config.get('stream_receive',True))

        # 长对话优化设置
        self.long_chat_checkbox.setChecked(self.config.get('long_chat_improve_var', False))
        self.placement_combo.setCurrentText(self.config.get('long_chat_placement', '系统提示'))
        self.include_system_prompt.setChecked(self.config.get('enable_lci_system_prompt', True))
        self.api_provider_combo.setCurrentText(self.config.get('long_chat_improve_api_provider', ''))
        self.model_combo.setCurrentText(self.config.get('long_chat_improve_model', ''))
        self.custom_hint_edit.setText(self.config.get('long_chat_hint', ''))
        
        # 参数设置
        self.top_p_checkbox.setChecked(self.config.get('top_p_enable', False))
        self.top_p_edit.setText(str(self.config.get('top_p', 0.7)))
        self.temp_checkbox.setChecked(self.config.get('temperature_enable', False))
        self.temp_edit.setText(str(self.config.get('temperature', 1.0)))
        self.penalty_checkbox.setChecked(self.config.get('presence_penalty_enable', False))
        self.penalty_edit.setText(str(self.config.get('presence_penalty', 0.0)))
        
        # 自动替换设置
        self.autoreplace_checkbox.setChecked(self.config.get('autoreplace_var', False))
        self.autoreplace_from_edit.setText(self.config.get('autoreplace_from', ''))
        self.autoreplace_to_edit.setText(self.config.get('autoreplace_to', ''))
        
        # 代称设置
        self.user_name_edit.setText(self.config.get('name_user', '用户'))
        self.ai_name_edit.setText(self.config.get('name_ai', 'AI'))

        # 标题生成设置
        use_local = self.config.get('title_creator_use_local', False)
        self.title_local_radio.setChecked(use_local)
        self.title_llm_radio.setChecked(not use_local)
        self.title_stack.setCurrentIndex(0 if use_local else 1)
        
        self.title_system_prompt_checkbox.setChecked(self.config.get('title_creator_system_prompt', True))
        self.title_max_length_edit.setText(str(self.config.get('title_creator_max_length', 20)))
        self.title_max_length_slider.setValue(self.config.get('title_creator_max_length', 20))
        self.title_provider_combo.setCurrentText(self.config.get('title_creator_provider', ''))
        self.title_model_combo.setCurrentText(self.config.get('title_creator_model', ''))
        self.blockSignals(False)
    
    def handle_title_max_length_text(self, text):
        """处理标题最大长度文本变化"""
        try:
            value = int(text)
            self.title_max_length_slider.setValue(value)
            self.title_creator_max_length_changed.emit(value)
        except ValueError:
            pass

    def handle_title_max_length_slider(self, value):
        """处理标题最大长度滑块变化"""
        self.title_max_length_edit.setText(str(value))
        self.title_creator_max_length_changed.emit(value)

    def handle_title_method_changed(self):
        """处理标题生成方式变化"""
        use_local = self.title_local_radio.isChecked()
        # 更新堆叠窗口显示
        self.title_stack.setCurrentIndex(0 if use_local else 1)
        # 发射信号
        self.title_creator_use_local_changed.emit(use_local)

#配置管理器
class ConfigManager:
    @staticmethod
    def init_settings(obj, filename='chatapi.ini', exclude=None):
        """
        初始化对象属性 from INI文件
        :param obj: 需要初始化属性的对象实例
        :param filename: 配置文件路径
        :param exclude: 需要排除的属性名列表（不导入这些属性）
        """
        config = configparser.ConfigParser()
        exclude_set = set(exclude) if exclude is not None else set()

        if os.path.exists(filename):
            try:
                config.read(filename)
            except:
                config.read(filename,encoding='utf=8')
            for section in config.sections():
                for option in config[section]:
                    if option in exclude_set:  # 跳过被排除的属性
                        continue
                    try:
                        value = config.getboolean(section, option)
                    except ValueError:
                        try:
                            value = config.getfloat(section, option)
                            try:
                                if int(value) == value:
                                    value = int(value)
                            except:
                                pass
                        except ValueError:
                            value = config.get(section, option)
                    setattr(obj, option, value)

    @staticmethod
    def config_save(obj:QObject, filename='chatapi.ini', section="others"):
        """
        保存对象属性到INI文件
        :param obj: 需要保存属性的对象实例
        :param filename: 配置文件路径
        :param section: 配置项分组名称
        """
        config = configparser.ConfigParser()
        config[section] = {}

        for key, value in vars(obj).items():
            if key.startswith("_"):
                continue
            if isinstance(value, bool):
                config[section][key] = "true" if value else "false"
            elif isinstance(value, (int, float, str)):
                config[section][key] = str(value)

        with open(filename, "w", encoding="utf-8") as f:
            config.write(f)

if __name__=='__main__':
    app = QApplication(sys.argv)
    
    sys.exit(app.exec())