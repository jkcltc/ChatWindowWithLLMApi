from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import sys,os,configparser

#简易小组件
class QuickSeparator(QFrame):
    """统一风格的分隔线组件"""
    def __init__(self, orientation="h"):
        super().__init__()
        if orientation == "h":
            self.setFrameShape(QFrame.HLine)
            self.setFrameShadow(QFrame.Sunken)
        else:
            self.setFrameShape(QFrame.VLine)
            self.setFrameShadow(QFrame.Sunken)

class SectionWidget(QWidget):
    """分组组件模板，提供标题和分组框样式"""
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(6)
        
        if title:
            title_label = QLabel(title)
            title_label.setStyleSheet("font-weight: bold;")
            self.layout.addWidget(title_label)

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

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config or {}
        self.init_smw()
        self.init_ui()
        self.setup_connections()

    def init_ui(self):
        self.setWindowTitle("对话设置")
        self.setGeometry(400, 200, 400, 600)
        
        grid_layout = QGridLayout()
        
        row=0

        grid_layout.addWidget(QuickSeparator(),row, 0, 1, 2)

        row+=1

        # 最大对话轮数设置
        grid_layout.addWidget(QLabel("上传对话数"), row, 0)
        self.max_rounds_edit = QLineEdit()
        self.max_rounds_edit.setText(str(self.config.get('max_message_rounds', 10)))
        grid_layout.addWidget(self.max_rounds_edit, row, 1)

        row+=1

        self.max_rounds_slider = QSlider(Qt.Horizontal)
        self.max_rounds_slider.setMinimum(-1)
        self.max_rounds_slider.setMaximum(50)
        self.max_rounds_slider.setValue(self.config.get('max_message_rounds', 10))
        grid_layout.addWidget(self.max_rounds_slider, row, 0, 1, 2)
        
        row+=1

        grid_layout.addWidget(QuickSeparator(),row, 0, 1, 2)

        row+=1

        stream_box=QLabel("传输模式")
        grid_layout.addWidget(stream_box, row, 0, 1, 1)
        grid_layout.addWidget(self.stream_setting,row,1,2,1)

        row+=2

        grid_layout.addWidget(QuickSeparator(),row, 0, 1, 2)

        row+=1

        # 长对话优化设置
        self.long_chat_checkbox = QCheckBox("启用自动长对话优化\t挂载位置：")
        self.long_chat_checkbox.setChecked(self.config.get('long_chat_improve_var', False))
        grid_layout.addWidget(self.long_chat_checkbox, row, 0, 1, 1)
        
        self.placement_combo = QComboBox()
        self.placement_combo.addItems(['系统提示', '对话第一位'])
        self.placement_combo.setCurrentText(self.config.get('long_chat_placement', '系统提示'))
        grid_layout.addWidget(self.placement_combo, row, 1, 1, 1)
        
        row+=1

        self.include_system_prompt=QCheckBox("携带系统提示")
        self.include_system_prompt.setToolTip('在发送摘要请求时携带系统提示。\n如果系统提示中包含人设等信息，\n可以帮助摘要模型理解对话。')
        self.include_system_prompt.setChecked(self.config.get('enable_lci_system_prompt', True))
        grid_layout.addWidget(self.include_system_prompt,row,1,1,1)

        row+=1

        grid_layout.addWidget(QLabel("长对话优化指定api"), row, 0)
        self.api_provider_combo = QComboBox()
        self.api_provider_combo.addItems(list(self.config.get('MODEL_MAP', {}).keys()))
        self.api_provider_combo.setCurrentText(self.config.get('long_chat_improve_api_provider', ''))
        grid_layout.addWidget(self.api_provider_combo, row, 1, 1, 1)
        
        row+=1

        grid_layout.addWidget(QLabel("长对话优化指定模型"), row, 0)
        self.model_combo = QComboBox()
        self.update_model_combo()
        self.model_combo.setCurrentText(self.config.get('long_chat_improve_model', ''))
        grid_layout.addWidget(self.model_combo, row, 1, 1, 1)
        
        row+=1
        
        # 自定义提示
        grid_layout.addWidget(QLabel("优先保留记忆\n也可用于私货"), row, 0)
        self.custom_hint_edit = QTextEdit()
        self.custom_hint_edit.setText(self.config.get('long_chat_hint', ''))
        grid_layout.addWidget(self.custom_hint_edit, row, 1, 1, 1)

        row+=1

        grid_layout.addWidget(QuickSeparator(),row, 0, 1, 2)

        row+=1

        # 参数设置
        self.top_p_checkbox = QCheckBox('AI词汇多样性top_p')
        self.top_p_checkbox.setChecked(self.config.get('top_p_enable', False))
        grid_layout.addWidget(self.top_p_checkbox, row, 0)
        self.top_p_edit = QLineEdit(str(self.config.get('top_p', 0.7)))
        grid_layout.addWidget(self.top_p_edit, row, 1)
        
        row+=1

        self.temp_checkbox = QCheckBox('AI自我放飞度temperature')
        self.temp_checkbox.setChecked(self.config.get('temperature_enable', False))
        grid_layout.addWidget(self.temp_checkbox, row, 0)
        self.temp_edit = QLineEdit(str(self.config.get('temperature', 1.0)))
        grid_layout.addWidget(self.temp_edit, row, 1)
        
        row+=1

        self.penalty_checkbox = QCheckBox('词意重复惩罚presence_penalty')
        self.penalty_checkbox.setChecked(self.config.get('presence_penalty_enable', False))
        grid_layout.addWidget(self.penalty_checkbox, row, 0)
        self.penalty_edit = QLineEdit(str(self.config.get('presence_penalty', 0.0)))
        grid_layout.addWidget(self.penalty_edit, row, 1)
        
        row+=1

        grid_layout.addWidget(QuickSeparator(),row, 0, 1, 2)

        row+=1

        # 自动替换
        self.autoreplace_checkbox = QCheckBox("自动替换(分隔符为 ; ,需正则时前缀re:#)")
        self.autoreplace_checkbox.setChecked(self.config.get('autoreplace_var', False))
        grid_layout.addWidget(self.autoreplace_checkbox, row, 0, 1, 1)
        
        self.autoreplace_from_edit = QLineEdit(self.config.get('autoreplace_from', ''))
        grid_layout.addWidget(self.autoreplace_from_edit, row, 1, 1, 1)
        
        row+=1

        grid_layout.addWidget(QLabel("为"), row, 0)
        self.autoreplace_to_edit = QLineEdit(self.config.get('autoreplace_to', ''))
        grid_layout.addWidget(self.autoreplace_to_edit, row, 1, 1, 1)
        
        row+=1

        grid_layout.addWidget(QuickSeparator(),row, 0, 1, 2)

        row+=1

        # 代称设置
        grid_layout.addWidget(QLabel("聊天记录中你的代称"), row, 0)
        self.user_name_edit = QLineEdit(self.config.get('name_user', '用户'))
        grid_layout.addWidget(self.user_name_edit, row, 1)
        
        row+=1

        grid_layout.addWidget(QLabel("聊天记录中AI的代称"), row, 0)
        self.ai_name_edit = QLineEdit(self.config.get('name_ai', 'AI'))
        grid_layout.addWidget(self.ai_name_edit, row, 1)
        
        row+=1

        # 确认按钮
        self.confirm_button = QPushButton("确认")
        grid_layout.addWidget(self.confirm_button, row, 0, 1, 2)
        
        self.setLayout(grid_layout)

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
            lambda state: self.long_chat_improve_changed.emit(state == Qt.Checked))
        
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
            lambda state: self.top_p_enable_changed.emit(state == Qt.Checked))
        self.top_p_edit.textChanged.connect(
            lambda text: self.handle_float_change(text, self.top_p_changed))
        
        self.temp_checkbox.stateChanged.connect(
            lambda state: self.temperature_enable_changed.emit(state == Qt.Checked))
        self.temp_edit.textChanged.connect(
            lambda text: self.handle_float_change(text, self.temperature_changed))
        
        self.penalty_checkbox.stateChanged.connect(
            lambda state: self.presence_penalty_enable_changed.emit(state == Qt.Checked))
        self.penalty_edit.textChanged.connect(
            lambda text: self.handle_float_change(text, self.presence_penalty_changed))
        
        # 自定义提示
        self.custom_hint_edit.textChanged.connect(
            lambda: self.custom_hint_changed.emit(self.custom_hint_edit.toPlainText()))
        
        # 自动替换
        self.autoreplace_checkbox.stateChanged.connect(
            lambda state: self.autoreplace_changed.emit(state == Qt.Checked))
        self.autoreplace_from_edit.textChanged.connect(
            self.autoreplace_from_changed.emit)
        self.autoreplace_to_edit.textChanged.connect(
            self.autoreplace_to_changed.emit)
        
        # 代称设置
        self.user_name_edit.textChanged.connect(self.user_name_changed.emit)
        self.ai_name_edit.textChanged.connect(self.assistant_name_changed.emit)
        
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

    #def closeEvent(self, event):
    #    self.window_closed.emit()
    #    super().closeEvent(event)

class BackgroundSettingsWidget(QWidget):
    """背景设置主组件，包含信号机制和优化布局"""
    
    # 定义信号
    modelProviderChanged = pyqtSignal(str)
    modelChanged = pyqtSignal(str)
    imageProviderChanged = pyqtSignal(str)
    imageModelChanged = pyqtSignal(str)
    updateSettingChanged = pyqtSignal(bool)
    backgroundSpecifyChanged = pyqtSignal(bool)
    updateIntervalChanged = pyqtSignal(int)
    historyLengthChanged = pyqtSignal(int)
    styleChanged = pyqtSignal(str)
    updateModelRequested = pyqtSignal()
    updateImageModelRequested = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        # 主窗口设置
        self.setWindowTitle("背景设置")
        self.setMinimumSize(1500,1000)
        
        # 主布局 - 左侧设置区域和右侧预览区域
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)
        
        # 左侧设置面板
        settings_panel = QWidget()
        settings_layout = QVBoxLayout(settings_panel)
        settings_layout.setSpacing(16)
        
        # 顶部标题
        title_label = QLabel("背景设置")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        settings_layout.addWidget(title_label)
        
        # 提示词模型分组
        model_section = SectionWidget("提示词生成模型")
        
        model_row = QHBoxLayout()
        model_row.setContentsMargins(0, 0, 0, 0)
        model_label = QLabel("模型选择")
        model_label.setSizePolicy(model_label.sizePolicy().horizontalPolicy(), 
                                 model_label.sizePolicy().verticalPolicy())
        self.update_model_button = QPushButton('更新模型')
        self.update_model_button.setFixedWidth(100)
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
        self.update_image_model_button.setFixedWidth(100)
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
        
        # 配置选项分组
        config_section = SectionWidget("更新配置")
        
        # 复选框设置
        self.enable_update_check = QCheckBox("启用后台更新")
        self.specify_background_check = QCheckBox("指定背景")
        config_section.layout.addWidget(self.enable_update_check)
        config_section.layout.addWidget(self.specify_background_check)
        
        # 间隔设置
        interval_group = QWidget()
        interval_layout = QGridLayout(interval_group)
        interval_layout.setContentsMargins(0, 0, 0, 0)
        
        interval_label = QLabel("更新间隔")
        self.update_slider = QSlider(Qt.Horizontal)
        self.update_slider.setEnabled(False)
        self.update_slider.setRange(1, 100)
        self.update_slider.setValue(15)
        self.update_spin = QSpinBox()
        self.update_spin.setEnabled(False)
        self.update_spin.setRange(1, 100)
        self.update_spin.setValue(15)
        self.update_spin.setSuffix('次对话')
        self.update_spin.setSingleStep(1)
        self.update_spin.setFixedWidth(120)
        
        interval_layout.addWidget(interval_label, 0, 0)
        interval_layout.addWidget(self.update_slider, 1, 0)
        interval_layout.addWidget(self.update_spin, 1, 1, Qt.AlignRight)
        
        config_section.layout.addWidget(interval_group)
        
        # 对话长度设置
        history_group = QWidget()
        history_layout = QGridLayout(history_group)
        history_layout.setContentsMargins(0, 0, 0, 0)
        
        history_label = QLabel("参考对话长度")
        self.history_slider = QSlider(Qt.Horizontal)
        self.history_slider.setEnabled(False)
        self.history_slider.setRange(200, 128000)
        self.history_slider.setValue(500)
        self.history_slider.setSingleStep(100)
        self.history_spin = QSpinBox()
        self.history_spin.setEnabled(False)
        self.history_spin.setRange(200, 128000)
        self.history_spin.setValue(500)
        self.history_spin.setSingleStep(100)
        self.history_spin.setFixedWidth(120)
        
        history_layout.addWidget(history_label, 0, 0)
        history_layout.addWidget(self.history_slider, 1, 0)
        history_layout.addWidget(self.history_spin, 1, 1, Qt.AlignRight)
        
        config_section.layout.addWidget(history_group)
        
        settings_layout.addWidget(config_section)
        
        # 分隔线
        settings_layout.addWidget(QuickSeparator("h"))
        
        # 生成风格分组
        style_section = SectionWidget("生成风格")
        style_label = QLabel("提示词生成风格")
        self.style_text_edit = QTextEdit()
        #self.style_text_edit.setMinimumHeight(120)
        self.style_text_edit.setPlaceholderText("在此输入生成风格描述...")
        
        style_section.layout.addWidget(style_label)
        style_section.layout.addWidget(self.style_text_edit)
        
        settings_layout.addWidget(style_section)
        
        # 设置面板添加到主布局左侧
        main_layout.addWidget(settings_panel, 0)  # 可拉伸比例为1
        
        # 垂直分隔线
        main_layout.addWidget(QuickSeparator("v"),0)
        
        # 右侧预览面板
        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setSpacing(8)

        # 创建一个占位容器用于预览区域
        preview_container = QWidget()
        preview_container_layout = QVBoxLayout(preview_container)
        preview_container_layout.setContentsMargins(0, 0, 0, 0)
            
        preview_title = QLabel("预览")
        preview_title.setStyleSheet("font-weight: bold;")
        preview_layout.addWidget(preview_title)
        
        preview_area = QLabel("背景预览区域")
        preview_area.setAlignment(Qt.AlignCenter)
        preview_area.setFrameShape(QFrame.Box)
        preview_area.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        preview_layout.addWidget(preview_area)
        preview_layout.addStretch()

        preview_container_layout.addWidget(preview_area)
        preview_layout.addWidget(preview_container, 1)  
        
        # 添加到主布局右侧
        main_layout.addWidget(preview_panel, 1)
        
    def populate_combos(self, model_map, image_model_map):
        # 填充模型选择框
        self.model_map = model_map
        self.image_model_map = image_model_map
        
        # 清空现有选项
        self.provider_combo.clear()
        self.model_combo.clear()
        self.image_provider_combo.clear()
        self.image_model_combo.clear()
        
        # 添加新选项
        self.provider_combo.addItems(list(self.model_map.keys()))
        if self.model_map:
            self.model_combo.addItems(self.model_map[self.provider_combo.currentText()])
        
        self.image_provider_combo.addItems(list(self.image_model_map.keys()))
        if self.image_model_map:
            self.image_model_combo.addItems(self.image_model_map[self.image_provider_combo.currentText()])
    
    def setup_connections(self):
        # 模型提供者改变信号
        self.provider_combo.currentTextChanged.connect(
            lambda text: [
                self.model_combo.clear(),
                self.model_combo.addItems(self.model_map[text]),
                self.modelProviderChanged.emit(text)
            ]
        )
        
        # 绘图模型提供者改变信号
        self.image_provider_combo.currentTextChanged.connect(
            lambda text: [
                self.image_model_combo.clear(),
                self.image_model_combo.addItems(self.image_model_map[text]),
                self.imageProviderChanged.emit(text)
            ]
        )
        
        # 模型选择改变信号
        self.model_combo.currentTextChanged.connect(self.modelChanged.emit)
        self.image_model_combo.currentTextChanged.connect(self.imageModelChanged.emit)
        
        # 更新按钮信号
        self.update_model_button.clicked.connect(self.updateModelRequested.emit)
        self.update_image_model_button.clicked.connect(self.updateImageModelRequested.emit)
        
        # 设置更新信号
        self.enable_update_check.toggled.connect(self.updateSettingChanged.emit)
        self.specify_background_check.toggled.connect(self.backgroundSpecifyChanged.emit)
        self.style_text_edit.textChanged.connect(lambda: self.styleChanged.emit(self.style_text_edit.toPlainText()))
        
        # 滑块和微调框值同步
        self.update_slider.valueChanged.connect(
            lambda val: [
                self.update_spin.setValue(val),
                self.updateIntervalChanged.emit(val)
            ]
        )
        self.update_spin.valueChanged.connect(
            lambda val: [
                self.update_slider.setValue(val),
                self.updateIntervalChanged.emit(val)
            ]
        )
        
        self.history_slider.valueChanged.connect(
            lambda val: [
                self.history_spin.setValue(val),
                self.historyLengthChanged.emit(val)
            ]
        )
        self.history_spin.valueChanged.connect(
            lambda val: [
                self.history_slider.setValue(val),
                self.historyLengthChanged.emit(val)
            ]
        )
        
        # 启用更新时激活相关控件
        self.enable_update_check.toggled.connect(
            lambda state: [
                self.update_slider.setEnabled(state),
                self.update_spin.setEnabled(state),
                self.history_slider.setEnabled(state),
                self.history_spin.setEnabled(state)
            ]
        )

class BackgroundSettingsAgent(QObject):
    """背景设置协调器"""
    # 信号定义
    settingChanged = pyqtSignal()
    modelMapUpdated = pyqtSignal(dict, dict)  # 文本模型映射，图像模型映射
    
    def __init__(self, application_path):
        super().__init__()
        self.application_path = application_path
        self.api_config_path = os.path.join(application_path, 'api_config.ini')
        
        # 默认设置
        self.settings = {
            'model_provider': 'novita',
            'model': '',
            'image_provider': 'novita',
            'image_model': '',
            'enable_update': True,
            'specify_background': False,
            'update_interval': 15,
            'history_length': 500,
            'style': '',
            'api_key': ''
        }
        
        # 缓存模型映射
        self.model_map = {}
        self.image_model_map = {}
        
    def get_settings(self):
        """返回当前所有设置"""
        return self.settings
    
    def get_setting(self, key):
        """获取单个设置值"""
        return self.settings.get(key, None)
    
    def set_setting(self, key, value):
        """更新单个设置"""
        if key in self.settings:
            self.settings[key] = value
            self.settingChanged.emit()
    
    def save_to_config(self):
        """保存到配置文件"""
        config = configparser.ConfigParser()
        if os.path.exists(self.api_config_path):
            config.read(self.api_config_path)
        
        # 确保novita部分存在
        if 'novita' not in config:
            config['novita'] = {'url': 'https://api.novita.ai/v3/', 'key': ''}
        
        # 更新API密钥
        config['novita']['key'] = self.settings['api_key']
        
        # 保存设置
        config['settings'] = self.settings
        
        with open(self.api_config_path, 'w') as configfile:
            config.write(configfile)
    
    def load_from_config(self):
        """从配置文件加载设置"""
        config = configparser.ConfigParser()
        config.read(self.api_config_path)
        
        if 'settings' in config:
            for key, value in config['settings'].items():
                if key in self.settings:
                    # 处理特殊类型
                    if key in ['enable_update', 'specify_background']:
                        self.settings[key] = value.lower() == 'true'
                    elif key in ['update_interval', 'history_length']:
                        try:
                            self.settings[key] = int(value)
                        except:
                            pass
                    else:
                        self.settings[key] = value
        
        # 加载API密钥
        if 'novita' in config and 'key' in config['novita']:
            self.settings['api_key'] = config['novita']['key']
    
    def update_model_maps(self, text_models, image_models):
        """更新模型映射"""
        self.model_map = text_models
        self.image_model_map = image_models
        self.modelMapUpdated.emit(self.model_map, self.image_model_map)
        
        # 确保当前模型在更新后仍然有效
        current_provider = self.settings['model_provider']
        current_model = self.settings['model']
        if current_provider in self.model_map and self.model_map[current_provider]:
            if current_model not in self.model_map[current_provider]:
                self.settings['model'] = self.model_map[current_provider][0]
                
        image_provider = self.settings['image_provider']
        image_model = self.settings['image_model']
        if image_provider in self.image_model_map and self.image_model_map[image_provider]:
            if image_model not in self.image_model_map[image_provider]:
                self.settings['image_model'] = self.image_model_map[image_provider][0]


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = BackgroundSettingsWidget()
    widget.show()
    sys.exit(app.exec_())