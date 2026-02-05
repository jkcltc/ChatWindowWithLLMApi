from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from PyQt6.QtGui import QPixmap
from jsonfinder import jsonfinder
import os
from core.session.chat_history_manager import ChatHistoryTools
from utils.preset_data import BackGroundPresetVars,LongChatImprovePersetVars
from service.chat_completion import APIRequestHandler
from service.text_to_image import ImageAgent
from ui.custom_widget import AspectLabel
from config import APP_SETTINGS,APP_RUNTIME



#背景生成管线
class BackgroundWorker(QObject):
    request_opti_bar_update = pyqtSignal()
    poll_success = pyqtSignal(str)
    failure = pyqtSignal(str, str)
    debug = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.request_sender = None
        self.creator = None

        self.failure.connect(print)
        self.poll_success.connect(print)
        self.debug.connect(print)

    # ========== 配置属性，统一从 APP_SETTINGS 读 ==========

    @property
    def application_path(self):
        return APP_RUNTIME.paths.application_path

    @property
    def background_cfg(self):
        """背景配置快捷访问"""
        return APP_SETTINGS.background

    @property
    def summary_provider(self):
        return self.background_cfg.summary_provider

    @property
    def summary_model(self):
        return self.background_cfg.summary_model

    @property
    def image_provider(self):
        return self.background_cfg.image_provider

    @property
    def image_model(self):
        return self.background_cfg.image_model

    @property
    def background_style(self):
        return self.background_cfg.style

    @property
    def required_length(self):
        return self.background_cfg.max_length

    def _get_api_config(self, provider: str) -> tuple:
        """从全局设置获取 API 配置"""
        return APP_SETTINGS.api.endpoints.get(provider, ("", ""))

    # ========== API 请求器生命周期 ==========

    def _init_api_requester(self):
        """用当前配置初始化 API 请求器"""
        url, key = self._get_api_config(self.summary_provider)
        self.request_sender = APIRequestHandler(api_config={
            "url": url,
            "key": key
        })
        self.request_sender.request_completed.connect(self._handle_image_prompt_receive)
        self.request_sender.error_occurred.connect(
            lambda infos: self.failure.emit('request_sender', infos)
        )

    def _finish_api_requester(self):
        if self.request_sender is not None:
            try:
                self.request_sender.request_completed.disconnect(self._handle_image_prompt_receive)
            except Exception as e:
                self.debug.emit(f"BGW Warning: _finish_api_requester Failed: {e}")
            self.request_sender.deleteLater()
            self.request_sender = None

    # ========== 图像生成器生命周期 ==========

    def _init_image_agent(self):
        """用当前配置初始化图像生成器"""
        self.creator = ImageAgent()
        self.creator.set_generator(self.image_provider)
        self.creator.failure.connect(lambda s1, s2: self.failure.emit(s1, s2))
        self.creator.pull_success.connect(self.poll_success.emit)

    def _finish_image_agent(self):
        if self.creator is not None:
            try:
                self.creator.pull_success.disconnect(self.poll_success.emit)
            except Exception as e:
                print('self.creator.pull_success.disconnect()', e)
            self.creator.deleteLater()
            self.creator = None

    # ========== 主流程 ==========

    def generate(self, chathistory):
        """生成背景图 - 入口方法"""
        self.request_opti_bar_update.emit()
        self._finish_image_agent()
        self._finish_api_requester()
        try:
            self._request_image_prompt(chathistory)
        except Exception as e:
            self.failure.emit('back_ground_update', f'error code: {e}')

    def _request_image_prompt(self, chathistory):
        """第一步：请求LLM生成图像prompt"""
        summary_prompt = BackGroundPresetVars.summary_prompt
        last_full_story = self._get_background_prompt_from_chathistory(chathistory)

        messages = [
            {"role": "system", "content": summary_prompt},
            {"role": "user", "content": last_full_story}
        ]

        try:
            self._init_api_requester()
        except Exception as e:
            self.failure.emit('APIRequestHandler init', str(e))
            return

        try:
            self.debug.emit(f"场景生成：prompt请求发送。\n发送内容长度:{len(last_full_story)}")
            self.request_sender.send_request(message=messages, model=self.summary_model)
        except Exception as e:
            self.failure.emit('back_ground_update_thread', f"Error: {str(e)}")

    def _handle_image_prompt_receive(self, return_prompt):
        """第二步：收到prompt后，请求生成图像"""
        self._finish_api_requester()
        self.debug.emit(f'return_prompt received:{return_prompt}')
        self._generate_image(return_prompt)

    def _generate_image(self, return_prompt):
        """第三步：调用图像生成API"""
        param = {}
        for _, __, obj in jsonfinder(return_prompt, json_only=True):
            if isinstance(obj, dict):
                param = obj

        if 'prompt' not in param or 'negative_prompt' not in param:
            self.failure.emit(
                'background_image',
                f'prompt extract failed, param extracted:{param}, return_prompt:{return_prompt}'
            )
            return

        param['width'] = 1280
        param['height'] = 720
        param['model'] = self.image_model

        try:
            self._init_image_agent()
        except Exception as e:
            self.failure.emit('background_image creater init', f"Error: {str(e)}")
            return

        try:
            self.creator.create(params_dict=param)
        except Exception as e:
            self.failure.emit('background_image_create', f"Error: {str(e)}")

    # ========== 辅助方法 ==========

    def _get_readable_story(self, chathistory) -> str:
        """从聊天记录提取指定长度的可读文本"""
        required_length = self.required_length
        total_chars = 0
        index = 0
        last_full_story = []

        for message in reversed(chathistory):
            if message["role"] != "system":
                content = message["content"]
                total_chars += len(content)
                index += 1
                if total_chars >= required_length:
                    last_full_story = chathistory[-index:]
                    break

        if total_chars < required_length:
            last_full_story = [msg for msg in chathistory if msg["role"] != "system"]

        return ChatHistoryTools.to_readable_str(last_full_story)

    def _get_last_full_story(self, chathistory) -> str:
        """从系统消息提取上次摘要"""
        if chathistory and chathistory[0]["role"] == "system":
            try:
                return str(
                    chathistory[0]["content"].split(
                        LongChatImprovePersetVars.before_last_summary
                    )[1]
                )
            except IndexError:
                return ''
        return ''

    def _get_background_prompt_from_chathistory(self, chathistory) -> str:
        """组装发给LLM的完整prompt"""
        last_full_story = ''

        # 添加自迭代摘要结果 
        summary_in_system = self._get_last_full_story(chathistory)
        if summary_in_system:
            last_full_story += (
                BackGroundPresetVars.system_prompt_hint + '\n'
                + summary_in_system + '\n'
            )

        # 添加场景内容
        last_full_story += (
            BackGroundPresetVars.scene_hint + '\n'
            + self._get_readable_story(chathistory) + '\n'
        )

        # 添加用户主请求
        last_full_story += BackGroundPresetVars.user_summary + '\n'

        # 添加风格要求
        if self.background_style:
            last_full_story += (
                BackGroundPresetVars.style_hint + '\n'
                + self.background_style + '\n\n'
            )

        # IRAG 特殊处理
        if 'irag' in self.image_model.lower():
            last_full_story += BackGroundPresetVars.IRAG_USE_CHINESE

        return last_full_story
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
        self.update_spin.setFixedWidth(120)
        
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
        self.history_spin.setFixedWidth(120)
        
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
        
        self.preview_area = AspectLabel(text="背景预览区域")
        self.preview_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_area.setFrameShape(QFrame.Shape.Box)
        self.preview_area.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        preview_layout.addWidget(self.preview_area)
        preview_layout.addStretch()

        preview_container_layout.addWidget(self.preview_area)
        preview_layout.addWidget(preview_container, 1)  
        
        # 添加到主布局右侧
        main_layout.addWidget(preview_panel, 1)

    def load_from_settings(self):
        """从 APP_SETTINGS 加载到控件"""
        self._initializing = True
        # 怎么光flag没有用的
        # self.blockSignals(True)
        try:
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

            # --- 控件启用状态 ---
            self._update_controls_enabled(self.cfg.enabled)

            # --- 背景预览 ---
            if self.cfg.lock and self.cfg.image_path:
                self._update_preview_image(self.cfg.image_path)
            else:
                self.preview_area.clear()
                self.preview_area.setText("背景预览区域")

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
        self.cfg.style = self.style_text_edit.toPlainText()
    
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
            self.preview_area.setText("背景预览区域")
            self.previewImageChanged.emit("")

    def _update_preview_image(self, file_path: str):
        """更新预览区域的图片"""
        if not file_path:
            self.preview_area.clear()
            self.preview_area.setText("背景预览区域")
            return

        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            self.preview_area.clear()
            self.preview_area.setText("图片加载失败")
            return

        self.preview_area.setText('')  # 清掉文字
        self.preview_area.update_icon(pixmap)

    
    def _update_controls_enabled(self, enabled: bool):
        """启用/禁用相关控件"""
        self.update_slider.setEnabled(enabled)
        self.update_spin.setEnabled(enabled)
        self.history_slider.setEnabled(enabled)
        self.history_spin.setEnabled(enabled)

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

# 背景生成代理
class BackgroundAgent(QObject):
    """背景生成代理 - 协调 Worker 和 SettingsWidget"""

    poll_success = pyqtSignal(str)
    failure = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._processing = False

        # 子组件，都自己读 APP_SETTINGS
        self.image_agent = ImageAgent()
        self.setting_window = BackgroundSettingsWidget()
        self.worker = BackgroundWorker()

        self._setup_connections()

    @property
    def cfg(self):
        return APP_SETTINGS.background

    @property
    def is_processing(self) -> bool:
        return self._processing

    def _setup_connections(self):
        # Worker 信号
        self.worker.poll_success.connect(self._on_generate_success)
        self.worker.failure.connect(self._on_generate_failure)

        # SettingsWidget 信号 - 更新图像模型列表
        self.setting_window.updateImageModelRequested.connect(self._refresh_image_models)

        # 预览图变化 → 可以转发给外部
        self.setting_window.previewImageChanged.connect(self.poll_success.emit)

        self.poll_success.connect(self._on_poll_success)
    
    def _on_poll_success(self, image_path: str):
        self.cfg.image_path = image_path

    def _on_generate_success(self, image_path: str):
        self._processing = False
        self.poll_success.emit(image_path)

    def _on_generate_failure(self, source: str, error: str):
        self._processing = False
        self.failure.emit(f"BGA Failed: {source} {error}")

    def _refresh_image_models(self):
        """刷新图像模型列表"""
        image_model_map = self.image_agent.get_image_model_map()
        self.setting_window.set_image_model_map(image_model_map)

    # ==================== 公开方法 ====================

    def initialize(self):
        """初始化设置窗口（首次显示前调用）"""
        # 加载图像模型映射
        self._refresh_image_models()
        # Widget 会自己从 APP_SETTINGS 加载其他配置

    def generate(self, chathistory: list):
        """
        生成背景图
        只需要传 chathistory，其他参数全从 APP_SETTINGS.background 读
        """
        if self._processing:
            print('[BackgroundAgent] 正在处理中，忽略重复请求')
            return False

        if not self.cfg.enabled:
            return False

        if self.cfg.lock:
            # 锁定模式，不自动生成
            return False

        self._processing = True
        self.worker.generate(chathistory)
        return True

    def force_generate(self, chathistory: list):
        """强制生成，忽略 enabled 和 lock 状态"""
        if self._processing:
            return False

        self._processing = True
        self.worker.generate(chathistory)
        return True

    def show_settings(self):
        """显示设置窗口"""
        self.initialize()  # 确保模型列表是最新的
        self.setting_window.show()
        self.setting_window.raise_()
        self.setting_window.activateWindow()

    # 兼容旧接口
    def show(self):
        self.show_settings()

    def raise_(self):
        self.setting_window.raise_()
