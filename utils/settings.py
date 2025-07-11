from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QPixmap
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

if __name__=='__main__':
    app = QApplication(sys.argv)
    
    sys.exit(app.exec_())