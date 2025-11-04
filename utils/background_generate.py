from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from PyQt6.QtGui import QPixmap
from jsonfinder import jsonfinder
from .chat_history_manager import ChatHistoryTools
from .preset_data import BackGroundPresetVars,LongChatImprovePersetVars
from .tools.one_shot_api_request import APIRequestHandler
from .text_to_image.image_agents import ImageAgent
from .custom_widget import AspectLabel

#背景生成管线
class BackGroundWorker(QObject):
    request_opti_bar_update=pyqtSignal()
    poll_success=pyqtSignal(str)
    failure=pyqtSignal(str,str)
    debug=pyqtSignal(str)

    def __init__(self,
                 default_apis={'provider':{'url':'url','key':'sk-xxx'}},
                 application_path='',
                 summary_api_provider='',
                 summary_model='',
                 image_api_provider='',
                 image_model='',
                 ):
        super().__init__()
        self.default_apis=default_apis
        self.application_path=application_path
        self.summary_api_provider   =   summary_api_provider
        self.summary_model          =   summary_model
        self.image_api_provider     =   image_api_provider
        self.image_model            =   image_model
        self.failure.connect(print)
        self.poll_success.connect(print)
        self.debug.connect(print)

    def set_providers(self,             summary_api_provider='',
                                        summary_model='',
                                        image_api_provider='',
                                        image_model='',):
        
        self.summary_api_provider   =   summary_api_provider
        self.summary_model          =   summary_model
        self.image_api_provider     =   image_api_provider
        self.image_model            =   image_model
    
    def _init_api_requester(self,summary_api_provider):
        self.request_sender=APIRequestHandler(api_config={
                "url":self.default_apis[summary_api_provider]['url'],
                "key":self.default_apis[summary_api_provider]['key']
                }
            )
        self.request_sender.request_completed.connect(self._handle_image_prompt_receive)
        self.request_sender.error_occurred.connect(lambda infos :self.failure.emit('request_sender',infos))
        
    def _finish_api_requester(self):
        if hasattr(self, 'request_sender') and self.request_sender is not None:
            try:
                self.request_sender.request_completed.disconnect(self._handle_image_prompt_receive)
            except:
                pass  # 可能之前没有连接，或者对象已被删除
            # 请求对象销毁
            self.request_sender.deleteLater()
            self.request_sender = None

    def _init_image_agent(self,application_path,image_api_provider):
        self.creator = ImageAgent(application_path=application_path)
        self.creator.set_generator(image_api_provider)
        self.creator.failure.connect(lambda s1, s2: self.failure.emit(s1, s2))
        self.creator.pull_success.connect(self.poll_success.emit)
    
    def _finish_image_agent(self):
        if hasattr(self, 'creator') and self.creator is not None:
            # 断开信号连接
            try:
                self.creator.pull_success.disconnect(self.poll_success.emit)
            except Exception as e:
                print('self.creator.pull_success.disconnect()',e)
                pass  # 可能之前没有连接，或者对象已被删除
            # 请求对象销毁
            self.creator.deleteLater()
            self.creator = None

    # 启动方法：
    # 初始化发送器
    # 组织参数发到back_ground_update_summary，用于请求prompt
    def generate(self,chathistory,background_style,required_lenth):
        self.request_opti_bar_update.emit()
        self._finish_image_agent()
        self._finish_api_requester()
        try:
            self.back_ground_update_summary(chathistory,
                       background_style,
                       self.summary_api_provider,
                       self.summary_model,
                       required_lenth=required_lenth
                    )
        except Exception as e:
            self.failure.emit('back_ground_update',f'error code: {e}')

    def _get_readable_story(self,chathistory,required_length):
            total_chars = 0
            index = 0
            last_full_story = []

            # 从后往前遍历 chathistory
            for message in reversed(chathistory):
                if message["role"] != "system":
                    content = message["content"]
                    total_chars += len(content)
                    index += 1
                    if total_chars >= required_length:
                        # 如果字符数达到 required_length，截取从当前消息到列表末尾的部分
                        last_full_story = chathistory[-index:]
                        break

            # 如果遍历结束后总字符数不足 required_length，返回所有非 system 消息
            if total_chars < required_length:
                last_full_story = [msg for msg in chathistory if msg["role"] != "system"]
            return ChatHistoryTools.to_readable_str(last_full_story)
    
    def _get_last_full_story(self,chathistory):#summaried
        if chathistory[0]["role"] == "system":
            # 从系统消息中尝试提取上次摘要
            try:
                last_summary = str(
                    chathistory[0]["content"].split(
                        LongChatImprovePersetVars.before_last_summary
                    )[1]
                )
            except IndexError:
                last_summary = ''
            return last_summary
        else:
            return ''
    
    #组织过去的故事
    def _get_background_prompt_from_chathistory(
            self,
            chathistory,
            background_style='',
            required_length=2000,
            image_model=''
        ): 
        """
            Generates a background prompt for a story based on chat history and specified style.
            This method constructs a prompt by combining system summary, scene hints, user summary, 
            and optional background style requirements. It utilizes preset variables and helper methods 
            to extract relevant information from the chat history.
            Args:
                chathistory (list): The chat history containing messages and story context.
                background_style (str, optional): The desired style for the background prompt. Defaults to ''.
                required_length (int, optional): The minimum required length for the readable story. Defaults to 2000.
            Returns:
                str: The user summary portion of the constructed background prompt.
        """
        if not image_model:
            image_model=self.image_model
        last_full_story=''

        #添加自迭代摘要结果 
        summary_in_system=self._get_last_full_story(chathistory)
        if summary_in_system:
            last_full_story += (
                BackGroundPresetVars.system_prompt_hint+'\n'
                +summary_in_system+'\n'
            )

        last_full_story += (
            BackGroundPresetVars.scene_hint+'\n'
            + str(self._get_readable_story(chathistory,required_length=required_length))+'\n'
        )

        #添加用户主请求，从常量类取user_summary
        user_summary=BackGroundPresetVars.user_summary
        last_full_story+=user_summary+'\n'

        # 添加风格要求
        if background_style != '':
            last_full_story+=(
                BackGroundPresetVars.style_hint +'\n'
                + background_style +'\n'
                + '\n'
            )
        if 'irag' in image_model:
            last_full_story+=BackGroundPresetVars.IRAG_USE_CHINESE
        return last_full_story

    #背景更新：聊天记录到prompt
    def back_ground_update_summary(self,
                                  chathistory,
                                  background_style='',
                                  summary_api_provider='',
                                  summary_model='',
                                  required_lenth=2000
                                  ):
        """
        Updates the background summary by sending a prompt to a summary API provider.
        This method prepares a system prompt and retrieves the latest full story from the chat history,
        then sends a request to the specified summary API provider using the given model. The response
        is handled asynchronously, with signals connected for completion and error handling.
        Args:
            chathistory (list or object): The chat history data used to generate the background prompt.
            background_style (str, optional): The style to apply when generating the background prompt. Defaults to ''.
            summary_api_provider (str, optional): The key identifying which summary API provider to use. Defaults to ''.
            summary_model (str, optional): The model name to use for the summary API request. Defaults to ''.
        Emits:
            failure (signal): Emitted if an exception occurs during the request, with the thread name and error message.
        """
        #先设置系统提示
        summary_prompt=BackGroundPresetVars.summary_prompt
        #再获取
        last_full_story=self._get_background_prompt_from_chathistory(chathistory=chathistory,
                                                                    background_style=background_style,
                                                                    required_length=required_lenth)
        messages=[
            {"role":"system","content":summary_prompt},
            {"role":"user","content":last_full_story}
        ]

        try:
            self._init_api_requester(summary_api_provider=summary_api_provider)
        except Exception as e:
            self.failure.emit('APIRequestHandler init',str(e))
            return
        
        try:
            self.debug.emit(f"场景生成：prompt请求发送。\n发送内容长度:{len(last_full_story)}")
            self.request_sender.send_request(message=messages,model=summary_model)
            
        except Exception as e:
            # 如果线程中发生异常，也通过信号通知主线程
            self.failure.emit('back_ground_update_thread',f"Error: {str(e)}")

    #将prompt组合实例变量，转发到图像生成
    def _handle_image_prompt_receive(self,return_prompt):
        self._finish_image_agent()
        self._finish_api_requester()
        self.debug.emit(f'return_prompt received:{return_prompt}')
        self.back_ground_update_generate_image(
            return_prompt=return_prompt,
            image_api_provider=self.image_api_provider,
            image_model=self.image_model,
            application_path=self.application_path,
        )

    def back_ground_update_generate_image(
            self,
            return_prompt='',
            image_api_provider='',
            image_model='',
            application_path=''
        ):
        param={}
        for _, __, obj in jsonfinder(return_prompt,json_only=True):
            if isinstance(obj, dict):
                param=obj
            
        if (not 'prompt' in param) or (not 'negative_prompt' in param):
            self.failure.emit(
                'background_image',
                f'prompt extract failed, param extracted:{param},return_prompt:{return_prompt}'
            )
            return
        print('image',image_model)
        param['width']=1280
        param['height']=720
        param['model']=image_model

        try:
            self._init_image_agent(application_path,image_api_provider)
        except Exception as e:
            self.failure.emit('background_image creater init',f"Error: {str(e)}")

        try:
            self.creator.create(params_dict=param)
        except Exception as e:
            # 如果线程中发生异常，也通过信号通知主线程
            self.failure.emit('background_image_create',f"Error: {str(e)}")

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
    """背景设置主组件，包含信号机制和优化布局"""
    
    # 定义信号
    modelProviderChanged = pyqtSignal(str)
    modelChanged = pyqtSignal(str)
    imageProviderChanged = pyqtSignal(str)
    imageModelChanged = pyqtSignal(str)
    updateSettingChanged = pyqtSignal(bool)
    lockBackground = pyqtSignal(bool)
    updateIntervalChanged = pyqtSignal(int)
    historyLengthChanged = pyqtSignal(int)
    styleChanged = pyqtSignal(str)
    updateModelRequested = pyqtSignal()
    updateImageModelRequested = pyqtSignal()
    backgroundImageChanged = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.background_image_path = None
        self.setup_ui()
        self.setup_connections()
        self.initing=False#信号已经block了，但文件选择框还是触发了
        
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

    def initialize_settings(self, settings_dict:dict):
        """
        使用传入的字典设置初始化所有控件
        settings_dict: 包含所有初始化设置的字典
            - model_map: {provider: [model_names]} 提示词模型映射
            - image_model_map: {provider: [model_names]} 绘图模型映射
            - back_ground_update_var: 是否启用后台更新（bool）
            - lock_background,是否指定背景（bool）
            - max_background_rounds: 更新间隔值（int）
            - max_backgound_lenth: 参考对话长度（int）
            - background_style: 生成风格文本（str）
            - background_image_path: 背景图片路径（str，如果指定了背景）
            - current_model: 当前选择的提示词模型 (provider, model_name)
            - current_image_model: 当前选择的绘图模型 (provider, model_name)
        """
        # 使用信号阻塞确保初始化时不触发事件
        self.blockSignals(True)
        self.initing=True
        # 保存模型映射到实例变量
        self.model_map = settings_dict.get('model_map', {})
        self.image_model_map = settings_dict.get('image_model_map', {})
        
        try:
            # =================== 填充模型下拉框 ===================
            # 清空现有选项
            self.provider_combo.clear()
            self.model_combo.clear()
            self.image_provider_combo.clear()
            self.image_model_combo.clear()
            
            # 添加提示词模型提供者
            self.provider_combo.addItems(list(self.model_map.keys()))
            
            # 添加绘图模型提供者
            self.image_provider_combo.addItems(list(self.image_model_map.keys()))
            
            # =================== 更新其他控件 ===================
            # 更新设置组
            self.enable_update_check.setChecked(settings_dict.get('back_ground_update_var', False))
            self.specify_background_check.setChecked(settings_dict.get('lock_background', False))
            
            # 数值控件
            update_interval = settings_dict.get('max_background_rounds', 15)
            self.update_slider.setValue(update_interval)
            self.update_spin.setValue(update_interval)
            
            history_length = settings_dict.get('max_backgound_lenth', 500)
            self.history_slider.setValue(history_length)
            self.history_spin.setValue(history_length)
            
            # 生成风格文本
            self.style_text_edit.setText(settings_dict.get('background_style', ''))
            
            # 激活/禁用关联控件
            update_enabled = settings_dict.get('back_ground_update_var', False)
            self.update_slider.setEnabled(update_enabled)
            self.update_spin.setEnabled(update_enabled)
            self.history_slider.setEnabled(update_enabled)
            self.history_spin.setEnabled(update_enabled)
            
            # =================== 设置选中模型 ===================
            # 设置当前提示词模型
            current_model = settings_dict.get('current_model', (None, None))
            if current_model[0] in self.model_map and current_model[1] in self.model_map[current_model[0]]:
                self.provider_combo.setCurrentText(current_model[0])
                self.model_combo.addItems(self.model_map[current_model[0]])
                self.model_combo.setCurrentText(current_model[1])
            
            # 设置当前绘图模型
            current_image_model = settings_dict.get('current_image_model', (None, None))
            if current_image_model[0] in self.image_model_map and current_image_model[1] in self.image_model_map[current_image_model[0]]:
                self.image_provider_combo.setCurrentText(current_image_model[0])
                self.image_model_combo.addItems(self.image_model_map[current_image_model[0]])
                self.image_model_combo.setCurrentText(current_image_model[1])
            
            # =================== 背景图片处理 ===================
            background_image_path = settings_dict.get('background_image_path', None)
            if settings_dict.get('lock_background', False) and background_image_path:
                self.background_image_path = background_image_path
                self._update_preview_image(background_image_path)
            else:
                self.preview_area.clear()
                self.preview_area.setText("背景预览区域")
        except Exception as e:
            print('init background generate fail:',e)
        finally:
            # 解除信号阻塞
            self.initing=False
            self.blockSignals(False)


    
    def setup_connections(self):
        # 模型提供者改变信号
        self.provider_combo.currentTextChanged.connect(
            lambda text: [
                self.model_combo.clear(),
                self.model_combo.addItems(self.model_map[text]),
                self.modelProviderChanged.emit(text)
            ] if text else None
        )
        # 绘图模型提供者改变信号
        self.image_provider_combo.currentTextChanged.connect(
            lambda text: [
                self.image_model_combo.clear(),
                self.image_model_combo.addItems(self.image_model_map[text]),
                self.imageProviderChanged.emit(text),
            ]if text else None
        )
        
        # 模型选择改变信号
        self.model_combo.currentTextChanged.connect(self.modelChanged.emit)
        self.image_model_combo.currentTextChanged.connect(self.imageModelChanged.emit)
        
        # 更新按钮信号
        self.update_model_button.clicked.connect(self.updateModelRequested.emit)
        self.update_image_model_button.clicked.connect(self.updateImageModelRequested.emit)
        
        # 设置更新信号
        self.enable_update_check.toggled.connect(self.updateSettingChanged.emit)
        self.specify_background_check.toggled.connect(self.lockBackground.emit)
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

        # 新增：指定背景复选框状态改变处理
        self.specify_background_check.toggled.connect(self.on_specify_background_toggled)
        
        # 新增：启用后台更新时取消指定背景
        self.enable_update_check.toggled.connect(
            lambda state: state and self.specify_background_check.setChecked(False)
            )
    
    def on_specify_background_toggled(self, checked):
        """处理指定背景复选框状态变化"""
        # 当选中时选择图片
        if self.initing:
            return
        if checked:
            self.enable_update_check.setChecked(False)  # 取消选中后台更新
            file_path, _ = QFileDialog.getOpenFileName(
                self, 
                "选择背景图片",
                "",
                "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
            )
            
            if file_path:
                self.background_image_path = file_path
                self._update_preview_image(file_path)
                self.backgroundImageChanged.emit(file_path)
            else:
                self.specify_background_check.setChecked(False)  # 未选择图片则取消选中
        
        # 取消选中时清除背景
        else:
            self.background_image_path = None
            self.preview_area.clear()
            self.preview_area.setText("背景预览区域")
            self.backgroundImageChanged.emit("")
    
    def _update_preview_image(self, file_path):
        """更新预览区域的图片"""
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            self.preview_area.setText('')
            self.preview_area.update_icon(pixmap)

    def show(self):
        super().show()
        self.resize(int(1.5 * self.height()),  self.height())
        screen = QApplication.primaryScreen()
        if self.parent():
            screen = self.parent().screen()
        
        # 计算居中位置
        screen_geometry = screen.availableGeometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        
        # 设置位置（考虑屏幕偏移）
        self.move(screen_geometry.left() + x, 
                 screen_geometry.top() + y)

#背景生成Agent类
class BackgroundAgent(QObject):
    poll_success=pyqtSignal(str)
    def __init__(
            self,
            default_apis,
            model_map,
            application_path,
        ):
        super().__init__()
        self.default_apis=default_apis
        self.model_map=model_map
        self.application_path=application_path
        self.image_agent=ImageAgent(application_path=application_path)
        self.setting_window=BackgroundSettingsWidget()
        self.update_worker=BackGroundWorker(
            default_apis=self.default_apis,
            application_path=self.application_path,
        )
        self.update_worker_processing=False
        self.update_worker.poll_success.connect(self.poll_success.emit)
        self.update_worker.poll_success.connect(lambda _:setattr(self,'update_worker_processing',False))
        self.update_worker.poll_success.connect(lambda _:print('self.update_worker.poll_success received at BackgroundAgent'))
        self.update_worker.failure.connect(lambda _:setattr(self,'update_worker_processing',False))

    def setup_setting_window(self,param_dict):
        """
        使用传入的字典设置初始化所有控件
        settings_dict: 包含所有初始化设置的字典
            - back_ground_update: 是否启用后台更新（bool）
            - max_background_rounds: 更新间隔值（int）
            - max_backgound_lenth: 参考对话长度（int）
            - background_style: 生成风格文本（str）
            - back_ground_update: 是否指定背景（bool）
            - background_image_path: 背景图片路径（str，如果指定了背景）
            - current_model: 当前选择的提示词模型 (provider, model_name)
            - current_image_model: 当前选择的绘图模型 (provider, model_name)
        """
        if not hasattr(self,'setting_window'):
            self.setting_window=BackgroundSettingsWidget()
        param_dict['model_map']=self.model_map
        param_dict['image_model_map']=self.image_agent.get_model_map()
        self.setting_window.initialize_settings(param_dict)
    
    def generate(self,default_apis={},
                 summary_api_provider='',
                 summary_model='',
                 image_api_provider='',
                 image_model='',
                 chathistory=[],
                 background_style='',
                 required_lenth=2000
                 ):
        if self.update_worker_processing:
            return
        self.update_worker_processing=True
        #在主类调用时default_apis可以不传
        self.default_apis = default_apis if default_apis else self.default_apis
        self.update_worker.set_providers(
            summary_api_provider=summary_api_provider,
            summary_model=summary_model,
            image_api_provider=image_api_provider,
            image_model=image_model,
        )
        self.update_worker.generate(
            chathistory=chathistory,
            background_style=background_style,
            required_lenth=required_lenth,
        )

    def show(self):
        self.setting_window.show()
    
    def raise_(self):
        self.setting_window.raise_()