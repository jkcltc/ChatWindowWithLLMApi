#chatapi_tts.py
import requests,os,sys,tempfile
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
import threading
import asyncio
import uuid
import json
from utils.tools.init_functions import install_packages
from utils.custom_widget import WindowAnimator
install_packages({'edge-tts':'edge_tts'})
import edge_tts
from edge_tts import VoicesManager, Communicate

class CosyVoiceTTSClient(QObject):
    """
    PyQt5兼容的TTS服务客户端类，提供信号反馈
    """
    processing_signal = pyqtSignal(str)  # 处理中信号（携带跟踪信息）
    success_signal = pyqtSignal(dict)    # 成功信号（携带完整响应）
    error_signal = pyqtSignal(str)       # 错误信号（携带错误信息）

    def __init__(self, server_url="http://localhost:5000/tts"):
        super().__init__()
        self.server_url = server_url

    def extract_dialogue(self,text):
        # 正则表达式模式匹配中文和英文的引号内容（包括单引号）
        # 使用非贪婪匹配，支持跨行内容
        try:
            re
        except NameError:
            import re
        pattern = r'[“"‘\'](.*?)[”"’\']'
        dialogues = re.findall(pattern, text, flags=re.DOTALL)
        return ''.join([d.strip() for d in dialogues if d.strip()])

    def send_request(self, text, prompt=None, function_type="zero-shot", audio='2342.wav',extract_dialogue=False):
        """
        异步发送TTS请求
        参数：
        - text: 需要合成的文本内容
        - prompt: 提示文本（可选）
        - function_type: 功能类型（zero-shot/cross_lingual/instruct）
        """
        if extract_dialogue:
            # 提取对话内容
            extracted_text = self.extract_dialogue(text)
            if extracted_text:
                text = extracted_text
                #return
        payload = {
            "text": text,
            "prompt": prompt,
            "function": function_type,
            "audio": audio
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            response = requests.post(
                self.server_url,
                json=payload,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code == 202:
                self.processing_signal.emit(response.json().get('message', 'Processing started'))
            elif response.ok:
                self.success_signal.emit(response.json())
            else:
                self.error_signal.emit(
                    f"请求失败（状态码：{response.status_code}）\n错误信息: {response.text}"
                )

        except requests.exceptions.ConnectionError as e:
            self.error_signal.emit(
                f"无法连接到服务器：\n{self.server_url}\n"
                f"请检查服务是否运行\n错误详情：{str(e)}"
            )
        except Exception as e:
            self.error_signal.emit(f"未知错误：{str(e)}")

    def update_server_url(self, new_url):
        """动态更新服务器地址"""
        self.server_url = new_url

class CosyVoiceTTSWindow(QWidget):
    def __init__(self):
        super().__init__()
        # 初始化客户端
        self.setWindowTitle("CosyVoice TTS设置/测试")
        self.tts_client = CosyVoiceTTSClient()


        # 连接信号
        self.tts_client.processing_signal.connect(self.show_processing)
        self.tts_client.success_signal.connect(self.handle_success)
        self.tts_client.error_signal.connect(self.show_error)

        self.main_layout = QVBoxLayout(self)

        self.send_text = QLineEdit()
        self.send_text.setPlaceholderText("请输入文本")
        self.main_layout.addWidget(self.send_text)

        # 模板音频路径 - 现在使用水平布局包含输入框和按钮
        self.audio_path_layout = QHBoxLayout()
        
        self.audio_path = QLineEdit()
        self.audio_path.setText("2342.wav")
        self.audio_path_layout.addWidget(self.audio_path)
        
        self.audio_path_button = QPushButton("选择文件")
        self.audio_path_button.clicked.connect(self.select_audio_file)
        self.audio_path_layout.addWidget(self.audio_path_button)
        
        self.main_layout.addLayout(self.audio_path_layout)

        # 模板音频文本
        self.prompt_text = QLineEdit()
        self.prompt_text.setText("博士，怎么了？啊，我没事，只是有点累。这两份档案一会儿麻烦你审核一下了，有许多新干员加入了罗德岛，我们可不能让他们失望。")
        self.main_layout.addWidget(self.prompt_text)

        self.send_request = QPushButton("发送请求")
        self.send_request.clicked.connect(self.on_send_button_clicked)
        self.main_layout.addWidget(self.send_request)

        self.extract_dialogue_checkbox = QCheckBox("尝试提取对话内容")
        self.main_layout.addWidget(self.extract_dialogue_checkbox)

        self.check_tts_server_button = QPushButton("检查TTS服务")
        self.check_tts_server_button.clicked.connect(self.check_tts_server)
        self.main_layout.addWidget(self.check_tts_server_button)

        self.stat = QLabel("")
        self.main_layout.addWidget(self.stat)

    def select_audio_file(self):
        """打开文件选择对话框选择音频文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择音频文件",
            "",  # 从当前目录开始
            "音频文件 (*.wav *.mp3 *.ogg);;所有文件 (*)"
        )
        if file_path:
            self.audio_path.setText(file_path)


    def on_send_button_clicked(self):
        """UI 按钮点击触发的槽函数"""
        self.send_tts_request()  # 不传参数，内部会从输入框读取

    def send_tts_request(self,text=None):
        # 从UI控件获取参数
        if text is None:
            text = self.send_text.text()
        prompt=self.prompt_text.text()
        audio=self.audio_path.text()
        extract_dialogue = self.extract_dialogue_checkbox.isChecked()
        
        # 发起请求
        # 使用threading创建新线程
        thread = threading.Thread(
            target=self.tts_client.send_request,
            args=(text, prompt),
            kwargs={'audio': audio, 'extract_dialogue': extract_dialogue}
        )
        self.stat.setText("正在发送请求...")
        thread.daemon = True  # 设置为守护线程
        thread.start()

    def show_processing(self, message):
        self.stat.setText(f"处理中... {message}")
        self.stat.setStyleSheet("color: blue;")

    def handle_success(self, response):
        audio_data = response.get("audio_data")
        self.play_audio(audio_data)

    def show_error(self, message):
        QMessageBox.critical(self, "错误", message)
    
    def check_tts_server(self):
        """检查TTS服务是否可用"""
        server_url = self.tts_client.server_url
        try:
            response = requests.get(server_url)
            if response.ok:
                QMessageBox.information(self, "成功", "TTS服务正常运行")
            else:
                QMessageBox.warning(self, "警告", f"TTS服务状态码：{response.status_code}")
        except requests.exceptions.ConnectionError:
            choice = QMessageBox.question(
                self,
                "错误",
                "无法连接到TTS服务，是否尝试启动服务？",
                QMessageBox.Yes | QMessageBox.No
            )
            if choice == QMessageBox.Yes:
                self.prompt_and_start_tts_server()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"未知错误：{str(e)}")

    def prompt_and_start_tts_server(self):
        """允许用户编辑启动脚本路径并尝试启动TTS服务"""
        bat_file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择启动脚本",
            r"D:\cosyvoice\CosyVoice",
            "批处理文件 (*.bat);;所有文件 (*)"
        )
        if bat_file_path:
            try: 
                os.startfile(bat_file_path)
                QMessageBox.information(self, "提示", "已尝试启动TTS服务，请稍后再试连接")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法启动TTS服务：{str(e)}")

class EdgeTTSSelectionDialog(QWidget):
    preview_requested = pyqtSignal(dict)  # 发送试听请求信号
    voice_selected = pyqtSignal(str, dict)  # 发送角色名称和语音配置

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("语音角色设置")
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        self.voice_data = []
        self.setup_ui()

    def setup_ui(self):
        main_layout = QGridLayout()
        main_layout.setContentsMargins(15,15,15,15)

        # 角色设置区域
        row=0
        pos_left=1
        pos_mlf=2
        pos_mid=3
        pos_mrt=4
        pos_right=5

        row+=1
        main_layout.setRowStretch(row,0)
        place_holder1=QFrame()
        place_holder1.setMinimumHeight(10)
        main_layout.addWidget(place_holder1)

        row+=1

        main_layout.setRowStretch(row,1)

        self.close_btn=QToolButton()
        self.close_btn.setText('X')
        self.close_btn.clicked.connect(self.close)
        self.close_btn.setMinimumSize(QSize(30,30))
        main_layout.addWidget(self.close_btn,row,pos_right+2,1,1,alignment=Qt.AlignRight | Qt.AlignTop)
        
        main_label=QLabel("指定音色")
        main_label_font = main_label.font()
        main_label_font.setPointSize(main_label_font.pointSize() + 5)
        main_label_font.setBold(True)
        main_label.setFont(main_label_font)
        main_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(main_label,row    ,pos_mlf  ,1,3)

        row+=1
        main_layout.setRowStretch(row,0)
        place_holder1=QFrame()
        place_holder1.setMinimumHeight(10)
        main_layout.addWidget(place_holder1)

        row+=1

        main_layout.addWidget(QLabel("角色:"),row   ,pos_left    ,1,1)

        self.name_edit=QLineEdit()
        self.name_edit.setToolTip('要绑定角色的名字')
        self.name_edit.textChanged.connect(self._check_enable_add)
        main_layout.addWidget(self.name_edit,row   ,pos_mrt    ,1,2)

        row+=1
        place_holder=QFrame()
        place_holder.setMinimumHeight(10)
        main_layout.addWidget(place_holder,    row,    pos_mid,1,3)

        row+=1
        main_layout.setRowStretch(row,0)

        # 语音筛选区域
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("筛选|语言:"))
        self.lang_combo = QComboBox()
        self.lang_combo.currentIndexChanged.connect(self.filter_voices)
        filter_layout.addWidget(self.lang_combo)
        filter_layout.addWidget(QLabel("筛选|性别:"))
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["全部", "男性", "女性"])
        self.gender_combo.currentIndexChanged.connect(self.filter_voices)
        filter_layout.addWidget(self.gender_combo)
        
        main_layout.addLayout(filter_layout,    row,    pos_mid,1,3)

        row+=1
        main_layout.setRowStretch(row,2)

        # 语音列表区域
        self.voice_list = QListWidget()
        self.voice_list.itemClicked.connect(self._check_enable_add)
        self.voice_list.setAlternatingRowColors(True)
        self.voice_list.itemDoubleClicked.connect(self.preview_voice)
        main_layout.addWidget(self.voice_list,   row,   pos_left,2,5)

        row+=1
        main_layout.setRowStretch(row,0)

        self.preview_btn = QPushButton("试听")
        self.preview_btn.clicked.connect(self.preview_voice)
        main_layout.addWidget(self.preview_btn,  row,   pos_right,1,1)

        row+=1
        main_layout.setRowStretch(row,0)
        place_holder2=QFrame()
        place_holder2.setMinimumHeight(10)
        main_layout.addWidget(place_holder2,    row,    pos_mid,1,3)

        row+=1
        main_layout.setRowStretch(row,0)
        
        self.add_btn = QPushButton("添加")
        self.add_btn.setToolTip('检查角色或音色是否已经填充和选择')
        self.add_btn.clicked.connect(self.accept_selection)
        self.add_btn.setEnabled(False)

        main_layout.addWidget(self.add_btn,     row,pos_mlf,1,3)

        for pos in range(pos_right+2):
            main_layout.setColumnStretch(pos,1)


        self.setLayout(main_layout)

    def set_voice_data(self, voice_data):
        """设置语音数据并初始化UI"""
        self.voice_data = voice_data
        self.populate_languages()
        self.filter_voices()

    def populate_languages(self):
        """从语音数据中提取并填充语言选项"""
        # 内置常见地区的友好名称映射
        locale_name_map = {
            "zh-CN": "中国大陆",
            "zh-HK": "香港",
            "zh-TW": "台湾",
            "en-US": "美国英语",
            "ja-JP": "日语",
            "ko-KR": "韩语"
        }
        
        locales = set()
        for voice in self.voice_data:
            locales.add(voice['Locale'])
        
        self.lang_combo.clear()
        self.lang_combo.addItem("全部")
        
        # 按优先级排序（常见地区置顶）
        ordered_locales = []
        for loc in ["zh-CN", "zh-HK", "zh-TW"]:  # 优先中文地区
            if loc in locales:
                ordered_locales.append(loc)
                locales.remove(loc)
        
        # 添加其他地区
        ordered_locales.extend(sorted(locales))
        
        for loc in ordered_locales:
            # 显示友好名称，未知地区使用原始locale
            friendly_name = locale_name_map.get(loc, loc)
            self.lang_combo.addItem(friendly_name, loc)

    def filter_voices(self):
        """根据选择的语言和性别筛选语音"""
        # 获取语言筛选条件
        selected_locale = None
        if self.lang_combo.currentIndex() > 0:
            selected_locale = self.lang_combo.itemData(self.lang_combo.currentIndex())
        
        # 获取性别筛选条件
        gender_index = self.gender_combo.currentIndex()
        gender_filter = ""
        if gender_index == 1:  # 男性
            gender_filter = "Male"
        elif gender_index == 2:  # 女性
            gender_filter = "Female"
        
        # 清空当前列表
        self.voice_list.clear()
        
        # 过滤语音数据
        for voice in self.voice_data:
            # 检查语言筛选
            if selected_locale and voice['Locale'] != selected_locale:
                continue
                
            # 检查性别筛选
            if gender_filter and voice['Gender'] != gender_filter:
                continue
                
            # 创建列表项
            item = QListWidgetItem()
            
            # 提取简洁名称（去掉"Microsoft"前缀）
            friendly_name = voice['FriendlyName']
            if friendly_name.startswith("Microsoft "):
                friendly_name = friendly_name[10:]
            
            # 主显示文本
            display_text = f"{friendly_name}"
            
            # 添加标签信息
            tags = []
            if voice.get('VoiceTag'):
                if 'ContentCategories' in voice['VoiceTag']:
                    tags.extend(voice['VoiceTag']['ContentCategories'])
                if 'VoicePersonalities' in voice['VoiceTag']:
                    tags.extend(voice['VoiceTag']['VoicePersonalities'])
            
            if tags:
                display_text += f"\n[{', '.join(tags)}]"
            
            item.setText(display_text)
            
            # 添加额外信息到tooltip
            tooltip = (f"<b>语音名称:</b> {voice['Name']}<br>"
                      f"<b>短名标识:</b> {voice['ShortName']}<br>"
                      f"<b>语言地区:</b> {voice['Locale']}<br>"
                      f"<b>性别:</b> {voice['Gender']}")
            
            if voice.get('VoiceTag'):
                tooltip += "<br><br><b>语音特性:</b>"
                if 'ContentCategories' in voice['VoiceTag']:
                    tooltip += f"<br>- 适合内容: {', '.join(voice['VoiceTag']['ContentCategories'])}"
                if 'VoicePersonalities' in voice['VoiceTag']:
                    tooltip += f"<br>- 语音风格: {', '.join(voice['VoiceTag']['VoicePersonalities'])}"
            
            item.setToolTip(tooltip)
            
            # 存储完整语音数据
            item.setData(Qt.UserRole, voice)
            
            self.voice_list.addItem(item)
            
        # 如果没有选中项，但列表有项则自动选中第一项
        if self.voice_list.count() > 0 and not self.voice_list.selectedItems():
            self.voice_list.setCurrentRow(0)

    def preview_voice(self):
        """触发试听功能"""
        if not self.voice_list.selectedItems():
            return
            
        selected_item = self.voice_list.currentItem()
        voice_info = selected_item.data(Qt.UserRole)
        self.preview_requested.emit(voice_info)

    def _check_enable_add(self):
        if (self.name_edit.text()
            and self.voice_list.selectedItems()
            ):
            self.add_btn.setEnabled(True)
            self.add_btn.setToolTip('分配此音色')
                
    def accept_selection(self):
        """确认选择并关闭窗口"""
        role_name = self.name_edit.text()

        selected_item = self.voice_list.currentItem()
        voice_info = selected_item.data(Qt.UserRole)
        
        self.voice_selected.emit(role_name, {
            'Name': voice_info['Name'],
            'ShortName': voice_info['ShortName']
        })
        self.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            delta = QPoint(event.globalPos() - self.oldPos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPos()
    
    def paintEvent(self, event):
        # 调用父类的绘制方法（确保基础样式被应用）
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 获取样式表定义的颜色
        palette = self.palette()
        bg_color = palette.color(QPalette.Window)

        if bg_color.alpha() < 255:
            painter.setCompositionMode(QPainter.CompositionMode_Source)

        # 应用圆角裁剪
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 20, 20)
        painter.setClipPath(path)

        # 绘制背景
        painter.fillRect(self.rect(), bg_color)

    def showEvent(self, event):
        """重写显示事件，添加展开动画"""
        super().showEvent(event)
        
        # 获取当前尺寸和最终尺寸
        current_size = self.size()
        target_height = int(self.sizeHint().height() * 1.4)
        target_width = int(self.sizeHint().width() * 3)
        target_size = QSize(target_width, target_height)
        
        # 如果是首次显示，从最小尺寸开始动画
        if current_size.isEmpty() or current_size == QSize(1, 1):
            start_size = QSize(1, 1)
            self.resize(start_size)
            
            # 启动动画
            WindowAnimator.animate_resize(
                self, 
                start_size=start_size,
                end_size=target_size,
                duration=100
            )
        else:
            # 非首次显示直接设置最终尺寸
            self.setFixedSize(target_size)

class EdgeTTSHandler(QObject):
    """Edge TTS功能处理器，支持在PyQt5中使用"""
    
    # 信号定义
    tts_finished = pyqtSignal(bool)                   # TTS转换完成信号（是否成功）
    voice_list_received = pyqtSignal(list)             # 接收到音色列表信号
    error_occurred = pyqtSignal(str)                  # 错误信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._loop = None  # 每个线程独立的事件循环
        self._thread = None

    def run_tts(self, text, voice, output_file):
        """执行TTS转换
        
        Args:
            text: 要转换的文本
            voice: 音色名称（如"zh-CN-XiaoxiaoNeural"）
            output_file: 输出文件路径
        """
        self._start_thread(self._execute_tts, text, voice, output_file)
    
    def fetch_all_voices(self):
        """获取所有可用的音色列表"""
        self._start_thread(self._execute_fetch_all_voices)
    
    def fetch_voices_by_attr(self, **filters):
        """根据属性筛选音色
        
        Args:
            filters: 筛选条件（如 Gender="Female", Language="zh"）
        """
        self._start_thread(self._execute_fetch_by_attr, filters)
    
    def _start_thread(self, target, *args, **kwargs):
        """启动线程执行任务"""
        # 停止任何正在运行的线程
        if self._thread and self._thread.is_alive():
            self._thread.join(0.1)
        
        # 创建新线程
        self._thread = threading.Thread(
            target=self._run_async,
            args=(target, *args),
            kwargs=kwargs,
            daemon=True
        )
        self._thread.start()
    
    def _run_async(self, task_func, *args, **kwargs):
        """在新线程中运行异步任务"""
        # 创建新事件循环
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            # 运行异步任务
            self._loop.run_until_complete(task_func(*args, **kwargs))
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            # 清理事件循环
            if self._loop.is_running():
                self._loop.stop()
            self._loop.close()
            self._loop = None
    
    async def _execute_tts(self, text, voice, output_file):
        """执行TTS转换的异步实现"""
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_file)
            self.tts_finished.emit(True)
        except Exception as e:
            self.tts_finished.emit(False)
            self.error_occurred.emit(f"TTS转换失败: {str(e)}")
    
    async def _execute_fetch_all_voices(self):
        """获取所有音色的异步实现"""
        try:
            voices = await edge_tts.list_voices()
            self.voice_list_received.emit(voices)
        except Exception as e:
            self.error_occurred.emit(f"获取音色失败: {str(e)}")
    
    async def _execute_fetch_by_attr(self, filters):
        """按属性筛选音色的异步实现"""
        try:
            voices_manager = await VoicesManager.create()
            voices = voices_manager.find(**filters)
            self.voice_list_received.emit(voices)
        except Exception as e:
            self.error_occurred.emit(f"筛选音色失败: {str(e)}")

class AudioPlayer(QObject):
    """
    MP3音频播放器类，提供播放控制和状态通知功能
    信号：
    - playback_completed: 音频播放完成时触发
    - playback_started: 音频开始播放时触发
    - playback_stopped: 音频停止播放时触发
    """
    playback_completed = pyqtSignal()
    playback_started = pyqtSignal()
    playback_stopped = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = QMediaPlayer()
        # 连接播放器状态变化信号
        self.player.stateChanged.connect(self.handle_state_change)
        # 连接媒体状态变化信号
        self.player.mediaStatusChanged.connect(self.handle_media_status)
        
        # 当前播放的文件路径
        self.current_file = None

    def load_and_play(self, mp3_path):
        """
        加载并播放MP3文件
        :param mp3_path: MP3文件路径
        """
        if not mp3_path:
            return False

        self.stop()  # 停止当前播放
        self.current_file = mp3_path

        # 创建媒体内容（支持本地文件路径）
        media_content = QMediaContent(QUrl.fromLocalFile(mp3_path))
        self.player.setMedia(media_content)
        self.player.play()
        return True

    def play(self):
        """继续播放当前音频"""
        if self.player.media().isNull():
            if self.current_file:
                self.load_and_play(self.current_file)
            return
        self.player.play()

    def pause(self):
        """暂停播放"""
        self.player.pause()

    def stop(self):
        """停止播放并重置位置"""
        self.player.stop()
        self.player.setPosition(0)  # 回到起始位置

    def set_volume(self, volume):
        """
        设置播放音量
        :param volume: 0-100之间的整数
        """
        self.player.setVolume(max(0, min(volume, 100)))

    def handle_state_change(self, state):
        """处理播放器状态变化"""
        if state == QMediaPlayer.PlayingState:
            self.playback_started.emit()
        elif state == QMediaPlayer.StoppedState:
            self.playback_stopped.emit()

    def handle_media_status(self, status):
        """处理媒体状态变化"""
        if status == QMediaPlayer.EndOfMedia:
            self.playback_completed.emit()
            self.stop()  # 播放完成后自动停止并重置

    def is_playing(self):
        """检查是否正在播放"""
        return self.player.state() == QMediaPlayer.PlayingState

    def cleanup(self):
        """清理资源"""
        self.stop()
        self.player.setMedia(QMediaContent())  # 清除媒体内容
        self.current_file = None

class VoiceItemWidget(QWidget):
    request_delete = pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.setup_animation()
        self.setup_button_animation()
        self.setMouseTracking(True)  # 启用鼠标跟踪

    def init_ui(self):
        # 创建控件
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("角色名")
        self.voice_type_hint = QLabel('音色')
        self.voice_type = QLabel()

        self.delete_btn = QPushButton("删除")

        # 设置按钮透明度效果
        self.btn_opacity_effect = QGraphicsOpacityEffect(self.delete_btn)
        self.btn_opacity_effect.setOpacity(0.0)  # 初始完全透明
        self.delete_btn.setGraphicsEffect(self.btn_opacity_effect)

        # 布局
        layout = QHBoxLayout()
        layout.addWidget(self.name_edit, 30)
        layout.addWidget(self.voice_type_hint, 10)
        layout.addWidget(self.voice_type, 60)
        layout.addWidget(self.delete_btn, 10)

        self.setLayout(layout)

        # 创建高光覆盖层
        self.highlight_overlay = QWidget(self)
        self.highlight_overlay.setStyleSheet("background-color: rgba(173, 216, 230, 50);")
        self.highlight_overlay.hide()
        self.highlight_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        # 添加透明度效果
        self.opacity_effect = QGraphicsOpacityEffect(self.highlight_overlay)
        self.opacity_effect.setOpacity(1.0)
        self.highlight_overlay.setGraphicsEffect(self.opacity_effect)

        self.delete_btn.clicked.connect(lambda _: self.request_delete.emit(self.name_edit.text()))
        self.delete_btn.clicked.connect(self.start_highlight_animation)

    def setup_animation(self):
        # 创建动画组
        self.animation_group = QSequentialAnimationGroup(self)

        # 宽度展开动画（保持原有参数）
        self.width_animation = QPropertyAnimation(self.highlight_overlay, b"geometry")
        self.width_animation.setDuration(400)
        self.width_animation.setEasingCurve(QEasingCurve.OutCubic)

        # 修改后的淡出动画（使用opacity效果）
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(450)  # 延长淡出时间
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.OutQuad)

        self.animation_group.addAnimation(self.width_animation)
        self.animation_group.addAnimation(self.fade_animation)
        self.animation_group.finished.connect(self.on_animation_finished)

    def setup_button_animation(self):
        """设置按钮透明度渐变动画"""
        # 鼠标进入时的淡入动画
        self.fade_in_animation = QPropertyAnimation(self.btn_opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(100) 
        self.fade_in_animation.setEasingCurve(QEasingCurve.Linear)
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)  # 完全不透明
        
        # 鼠标离开时的淡出动画
        self.fade_out_animation = QPropertyAnimation(self.btn_opacity_effect, b"opacity")
        self.fade_out_animation.setDuration(200)  # 200ms线性过渡
        self.fade_out_animation.setEasingCurve(QEasingCurve.Linear)
        self.fade_out_animation.setStartValue(1.0)
        self.fade_out_animation.setEndValue(0.0)  # 完全透明

    def enterEvent(self, event):
        """鼠标进入控件时切换到第二页并启动淡入动画"""
        
        # 停止任何正在进行的淡出动画
        if self.fade_out_animation.state() == QPropertyAnimation.Running:
            self.fade_out_animation.stop()
        
        # 如果淡入动画没有运行，则启动它
        if self.fade_in_animation.state() != QPropertyAnimation.Running:
            self.fade_in_animation.start()
        
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开控件时切换到第一页并启动淡出动画"""
        # 停止任何正在进行的淡入动画
        if self.fade_in_animation.state() == QPropertyAnimation.Running:
            self.fade_in_animation.stop()
        
        # 启动淡出动画
        self.fade_out_animation.start()
        
        super().leaveEvent(event)

    def set_info(self, name, voice):
        """设置变量值并触发高光动画"""
        self.name_edit.setText(name)
        self.voice_type.setText(voice)
        self.start_highlight_animation()

    def start_highlight_animation(self):
        """启动高光动画（增加初始化设置）"""
        # 重置覆盖层状态
        self.highlight_overlay.setGeometry(0, 0, 0, self.height())
        self.opacity_effect.setOpacity(1.0)  # 确保每次动画前重置透明度
        self.highlight_overlay.show()
        self.highlight_overlay.raise_()

        # 设置动画参数
        end_width = self.width()
        self.width_animation.setStartValue(QRect(0, 0, 0, self.height()))
        self.width_animation.setEndValue(QRect(0, 0, end_width, self.height()))
        
        self.animation_group.start()

    def on_animation_finished(self):
        """动画完成后完全隐藏覆盖层"""
        self.highlight_overlay.hide()
        self.opacity_effect.setOpacity(1.0)  # 重置透明度以备下次使用

class VoiceSettingsList(QListWidget):
    """支持音色配对管理的列表控件"""
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.itemDoubleClicked.connect(self.handle_item_double_click)
        
    def refresh_list(self):
        """刷新列表显示"""
        self.clear()
        for pairing in self.manager.get_all_pairings():
            item = QListWidgetItem(pairing['role_name'])
            item.setData(Qt.UserRole, pairing['id'])
            self.addItem(item)
            
    def handle_item_double_click(self, item):
        """双击项目处理"""
        unique_id = item.data(Qt.UserRole)
        self.manager.set_edit_id(unique_id)
        
        # 通知父控件打开编辑对话框
        if self.parent().edit_pairing():
            self.refresh_list()

class VoiceSettingsManager:
    """音色配对数据管理器"""
    def __init__(self):
        self.voice_pairings = {}  # 存储所有音色配对
        self.current_edit_id = None  # 当前正在编辑的配对ID
        
    def add_pairing(self, role_name, voice_config):
        """添加新音色配对"""
        unique_id = str(uuid.uuid4())
        self.voice_pairings[unique_id] = {
            'id': unique_id,
            'role_name': role_name,
            'voice_config': voice_config
        }
        return unique_id
        
    def remove_pairing(self, unique_id):
        """删除指定音色配对"""
        if unique_id in self.voice_pairings:
            del self.voice_pairings[unique_id]
            return True
        return False
        
    def update_role_name(self, unique_id, new_role_name):
        """更新角色名称"""
        if unique_id in self.voice_pairings:
            self.voice_pairings[unique_id]['role_name'] = new_role_name
            return True
        return False
        
    def update_voice_config(self, unique_id, new_voice_config):
        """更新音色配置"""
        if unique_id in self.voice_pairings:
            self.voice_pairings[unique_id]['voice_config'] = new_voice_config
            return True
        return False
        
    def get_pairing(self, unique_id):
        """获取指定配对的详细信息"""
        return self.voice_pairings.get(unique_id)
        
    def get_all_pairings(self):
        """获取所有音色配对信息"""
        return list(self.voice_pairings.values())
        
    def save_to_file(self, filename):
        """保存配置到文件"""
        with open(filename, 'w') as f:
            json.dump(self.voice_pairings, f, indent=2)
            
    def load_from_file(self, filename):
        """从文件加载配置"""
        try:
            with open(filename) as f:
                data = json.load(f)
                self.voice_pairings = {
                    k: {
                        'id': k,
                        'role_name': v['role_name'],
                        'voice_config': v['voice_config']
                    } for k, v in data.items()
                }
            return True
        except FileNotFoundError:
            return False
        except json.JSONDecodeError:
            return False

    def set_edit_id(self, unique_id):
        """设置当前编辑的配对ID"""
        self.current_edit_id = unique_id
        
    def get_edit_id(self):
        """获取当前编辑的配对ID"""
        return self.current_edit_id
        
    def clear_edit_id(self):
        """清除当前编辑的配对ID"""
        self.current_edit_id = None

class EdgeTTSMainSetting(QWidget):
    def __init__(self):
        super().__init__()
        self.manager = VoiceSettingsManager()  # 创建数据管理器
        self.setup_ui()
        
        
    def setup_ui(self):
        # 设置窗口大小和标题
        self.setGeometry(0, 0, 943, 751)
        self.setWindowTitle("EdgeTTS")
        
        # 创建网格布局
        self.grid_layout = QGridLayout(self)
        self.grid_layout.setColumnStretch(0, 1)  # 第一列拉伸因子为1
        self.grid_layout.setColumnStretch(1, 0)  # 第二列拉伸因子为0
        self.grid_layout.setColumnStretch(2, 0)  # 第三列拉伸因子为0
        self.grid_layout.setColumnStretch(3, 1)  # 第四列拉伸因子为1
        
        # 创建标签："音色绑定列表"
        self.label = QLabel("音色绑定列表")
        self.grid_layout.addWidget(self.label, 0, 1)
        
        # 创建占位符组件（左边）
        self.place_holder2 = QFrame()
        self.place_holder2.setFrameShape(QFrame.StyledPanel)
        self.place_holder2.setFrameShadow(QFrame.Raised)
        self.place_holder2.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.grid_layout.addWidget(self.place_holder2, 1, 0)
        
        # 创建列表视图
        self.voice_binding_list = VoiceSettingsList(self.manager, self)
        self.voice_binding_list.setMinimumWidth(557)
        self.voice_binding_list.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.grid_layout.addWidget(self.voice_binding_list, 1, 1, 1, 2)  # 占据1行2列
        
        # 创建占位符组件（右边）
        self.place_holder = QFrame()
        self.place_holder.setFrameShape(QFrame.StyledPanel)
        self.place_holder.setFrameShadow(QFrame.Raised)
        self.place_holder.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.grid_layout.addWidget(self.place_holder, 1, 3, 2, 1)  # 占据2行1列
        
       # 创建添加按钮
        self.add_button = QPushButton("添加")
        self.add_button.clicked.connect(self.open_voice_selection_dialog)
        self.add_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.grid_layout.addWidget(self.add_button, 2, 2, alignment=Qt.AlignLeft | Qt.AlignTop)
        
        # 创建并配置语音选择对话框
        self.voice_dialog = EdgeTTSSelectionDialog()
        self.voice_dialog.voice_selected.connect(self.add_voice_item)
        self.voice_dialog.setVisible(False)  # 初始时隐藏

        # 设置布局
        self.setLayout(self.grid_layout)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EdgeTTSMainSetting()
    window.show()
    sys.exit(app.exec_())

#if __name__ == "__main__":
#    app = QApplication(sys.argv)
#    window = TTSWindow()
#    window.show()
#    sys.exit(app.exec_())
