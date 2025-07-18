#chatapi_tts.py
import requests,os,sys,re
from collections import Counter
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
import threading
import asyncio
import random
import json

class WindowAnimator:
    @staticmethod
    def animate_resize(window: QWidget, 
                      start_size: QSize, 
                      end_size: QSize, 
                      duration: int = 300):
        """
        窗口尺寸平滑过渡动画
        :param window: 要应用动画的窗口对象
        :param start_size: 起始尺寸（QSize）
        :param end_size: 结束尺寸（QSize）
        :param duration: 动画时长（毫秒，默认300）
        """
        # 创建并配置动画
        anim = QPropertyAnimation(window, b"size", window)
        anim.setDuration(duration)
        anim.setStartValue(start_size)
        anim.setEndValue(end_size)
        anim.setEasingCurve(QEasingCurve.InOutQuad)  # 平滑过渡
        
        # 启动动画
        anim.start()

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
        pattern = r'[“"‘\'](.*?)[”"’\']'
        dialogues = re.findall(pattern, text, flags=re.DOTALL)
        result= ''.join([d.strip() for d in dialogues if d.strip()])
        return result if result else text
    

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
    enable_dialog_extract=pyqtSignal(bool)
    def __init__(self,_=''):
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
        self.extract_dialogue_checkbox.clicked.connect(self.enable_dialog_extract.emit)
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

    def send_tts_request(self,text=None,name=''):
        # 从UI控件获取参数
        if text is None:
            text = self.send_text.text()
        prompt=self.prompt_text.text()
        audio=self.audio_path.text()
        
        # 发起请求
        # 使用threading创建新线程
        thread = threading.Thread(
            target=self.tts_client.send_request,
            args=(text, prompt),
            kwargs={'audio': audio, 'extract_dialogue': False}
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
    voice_selected = pyqtSignal(str, dict,int)  # 发送角色名称和语音配置
    closeing=pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("语音角色设置")
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        self.voice_data = []
        self.voice_id=0
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
            "zh-HK": "中国香港",
            "zh-TW": "中国台湾",
            "en-US": "英语",
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
        
        self.lang_combo.setCurrentText('中国大陆')

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
        },self.voice_id)
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
        target_height = int(self.sizeHint().height() * 1.4)
        target_width = int(self.sizeHint().width() * 3)
        target_size = QSize(target_width, target_height)
        self.resize(target_size)
        screen = QApplication.primaryScreen().availableGeometry()
        
        # 获得窗口实际尺寸
        size = self.size()
        
        # 计算居中位置
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        
        # 移动窗口
        self.move(x, y)     

    def close(self):
        # 如果已经处于关闭动画中，则忽略
        self.closeing.emit()
        if hasattr(self, '_closing') and self._closing:
            return
        self._closing = True

        # 禁用窗口
        self.setEnabled(False)

        # 创建动画组
        self.anim_group = QParallelAnimationGroup()

        # 透明度动画
        opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        opacity_anim.setDuration(75)
        opacity_anim.setStartValue(self.windowOpacity())
        opacity_anim.setEndValue(0.0)

        self.anim_group.addAnimation(opacity_anim)

        # 动画结束后，真正关闭窗口
        self.anim_group.finished.connect(self._real_close)
        self.anim_group.start()

    def _real_close(self):
        # 断开信号，防止多次调用
        self.anim_group.finished.disconnect()
        # 调用父类的close
        super().close()

class EdgeTTSHandler(QObject):
    """Edge TTS功能处理器，支持在PyQt5中使用"""
    
    # 信号定义
    tts_finished = pyqtSignal(str)                   # TTS转换完成信号（是否成功）
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
        """在新线程中运行异步任务（修复事件循环管理）"""
        try:
            # 每个线程独立创建并管理事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 运行异步任务
            loop.run_until_complete(task_func(*args, **kwargs))
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            # 安全关闭事件循环
            try:
                if loop.is_running():
                    loop.stop()
                # 关闭前先执行待定回调
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.run_until_complete(loop.shutdown_default_executor())
            finally:
                loop.close()
    
    async def _execute_tts(self, text, voice, output_file):
        """执行TTS转换的异步实现"""
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_file)
            self.tts_finished.emit(str(output_file))
        except Exception as e:
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = QMediaPlayer()
        self.play_queue = []        # 存储待播放文件路径
        
        # 连接媒体状态变化信号
        self.player.mediaStatusChanged.connect(self.handle_media_status)
        
    def add_play_task(self, mp3_path):
        """
        将MP3文件加入播放队列，自动按顺序播放
        :param mp3_path: MP3文件路径
        """
        # 添加到播放队列
        self.play_queue.append(mp3_path)
        
        # 如果没有正在播放的项目，立即开始播放
        if self.player.state() != QMediaPlayer.PlayingState:
            self._play_next()

    def handle_media_status(self, status):
        """处理媒体状态变化事件"""
        # 当前媒体播放完成且队列中有待播文件
        if status == QMediaPlayer.EndOfMedia and self.play_queue:
            self._play_next()
    
    def _play_next(self):
        """播放队列中的下一个文件"""
        if not self.play_queue:
            return
            
        # 获取并移除队列中的首个文件
        next_path = self.play_queue.pop(0)
        media_content = QMediaContent(QUrl.fromLocalFile(next_path))
        
        # 设置媒体内容并开始播放
        self.player.setMedia(media_content)
        self.player.play()

class VoiceItemWidget(QWidget):
    request_delete = pyqtSignal(int)
    request_change = pyqtSignal(int)
    def __init__(self, item_id,parent=None):
        super().__init__(parent)
        self.init_ui()
        self.setup_animation()
        self.setup_button_animation()
        self.setMouseTracking(True)  # 启用鼠标跟踪
        self.item_id=item_id

    def init_ui(self):
        # 创建控件
        self.name_edit = QLabel()
        self.voice_type_hint = QLabel('音色：')
        self.voice_type_hint.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.voice_type = QLabel()

        self.delete_btn = QPushButton("删除")

        # 设置按钮透明度效果
        self.btn_opacity_effect = QGraphicsOpacityEffect(self.delete_btn)
        self.btn_opacity_effect.setOpacity(0.0)  # 初始完全透明
        self.delete_btn.setGraphicsEffect(self.btn_opacity_effect)
        
        self.change_btn=QPushButton()
        self.change_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.change_btn.setStyleSheet('''
QPushButton {
    background: transparent;
    border: 1px solid #d0d8e0;
    border-radius: 4px; 
    padding: 10px 20px;
}
''')
        self.change_btn.clicked.connect(lambda _: self.request_change.emit(self.item_id))
        self.change_btn.clicked.connect(self.start_highlight_animation)

        # 布局
        layout = QGridLayout()
        layout.addWidget(self.name_edit,        0,0,1,1, alignment=Qt.AlignVCenter | Qt.AlignHCenter)
        layout.addWidget(self.voice_type_hint,  0,1,1,1,alignment=Qt.AlignVCenter | Qt.AlignRight)
        layout.addWidget(self.voice_type,       0,2,1,2)

        #作为背景重叠在信息上面
        layout.addWidget(self.change_btn,       0,0,1,5)

        layout.addWidget(self.delete_btn,       0,4,1,1)

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

        self.delete_btn.clicked.connect(lambda _: self.request_delete.emit(self.item_id))

        self.setMaximumHeight(self.sizeHint().height())
        

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

class EdgeTTSMainSettingWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.setup_animations()

    def setup_ui(self):
        # 设置窗口大小和标题
        self.setWindowTitle("EdgeTTS")
        screen = QApplication.primaryScreen()
        screen_size = screen.size()
        target_width=min(screen_size.width(),1600)
        target_height=min(int(screen_size.height()/1.33),1000)
        self.setMinimumWidth(target_width)
        self.setMinimumHeight(target_height)
        
        # 创建网格布局
        self.grid_layout = QGridLayout(self)
        self.grid_layout.setColumnStretch(0, 1)  # 第一列拉伸因子为1
        self.grid_layout.setColumnStretch(1, 0)  # 第二列拉伸因子为0
        self.grid_layout.setColumnStretch(2, 0)  # 第三列拉伸因子为0
        self.grid_layout.setColumnStretch(3, 1)  # 第四列拉伸因子为1
        
        # 创建标签："音色绑定列表"
        self.label = QLabel("音色绑定列表")
        self.grid_layout.addWidget(self.label, 0, 1,1,2,alignment=Qt.AlignVCenter | Qt.AlignHCenter)
        
        # 创建占位符组件（左边）
        self.place_holder2 = QFrame()
        self.place_holder2.setFrameShape(QFrame.StyledPanel)
        self.place_holder2.setFrameShadow(QFrame.Raised)
        self.place_holder2.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.grid_layout.addWidget(self.place_holder2, 1, 0)
        
        # 创建列表视图
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)  # 重要：允许内容部件自动调整大小
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # 始终显示垂直滚动条
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # 禁用水平滚动条
        
        # 创建滚动区域的内容部件
        self.scroll_content = QWidget()
        self.voice_binding_layout = QVBoxLayout(self.scroll_content)
        self.voice_binding_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)  # 确保布局可以收缩到最小
        self.scroll_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)  # 优先竖向最小
        
        # 设置滚动区域的内容部件
        self.scroll_area.setWidget(self.scroll_content)
        self.scroll_area.setMinimumWidth(600)
        self.grid_layout.addWidget(self.scroll_area, 1, 1, 1, 2)  # 占据1行2列
        
        # 创建占位符组件（右边）
        self.place_holder = QFrame()
        self.place_holder.setFrameShape(QFrame.StyledPanel)
        self.place_holder.setFrameShadow(QFrame.Raised)
        self.place_holder.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.grid_layout.addWidget(self.place_holder, 1, 3, 2, 1)  # 占据2行1列
        
       # 创建添加按钮
        self.add_button = QPushButton("添加")
        self.add_button.setEnabled(False)
        self.grid_layout.addWidget(self.add_button, 2, 2)

        self.enable_extract_button=QCheckBox('启用对话提取')
        self.grid_layout.addWidget(self.enable_extract_button,2,1)

        self.hide_mask=QPushButton()
        self.hide_mask.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.hide_mask.setStyleSheet("""
        QPushButton {
            background:rgba(0,0,0,0.7);
            border: none;
        }""")  

        self.grid_layout.addWidget(self.hide_mask,0,0,3,4)
        self.hide_mask.hide()

        # 设置布局
        self.setLayout(self.grid_layout)

    def setup_animations(self):
        # 创建透明度效果
        self.mask_opacity = QGraphicsOpacityEffect(self.hide_mask)
        self.mask_opacity.setOpacity(0.0)  # 初始完全透明
        self.hide_mask.setGraphicsEffect(self.mask_opacity)
        self.hide_mask.setHidden(True)  # 初始隐藏
        
        # 淡入动画
        self.fade_in = QPropertyAnimation(self.mask_opacity, b"opacity")
        self.fade_in.setDuration(150)  # 300毫秒动画
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(0.7)  # 70%不透明
        self.fade_in.setEasingCurve(QEasingCurve.OutQuad)
        
        # 淡出动画
        self.fade_out = QPropertyAnimation(self.mask_opacity, b"opacity")
        self.fade_out.setDuration(50)  # 200毫秒动画
        self.fade_out.setStartValue(0.7)
        self.fade_out.setEndValue(0.0)
        self.fade_out.setEasingCurve(QEasingCurve.InQuad)
        
        # 连接按钮信号
        self.add_button.clicked.connect(self.show_mask_animation)
        self.hide_mask.clicked.connect(self.hide_mask_animation)
        
        # 动画结束时隐藏控件
        self.fade_out.finished.connect(lambda: self.hide_mask.setHidden(True))

    def show_mask_animation(self):
        """显示遮罩并执行淡入动画"""
        # 确保遮罩在最顶层
        self.hide_mask.raise_()
        self.hide_mask.setHidden(False)  # 先显示再动画
        self.fade_in.start()
        
    def hide_mask_animation(self):
        """执行淡出动画"""
        self.fade_out.start()

class EdgeTTSMainSetting(EdgeTTSMainSettingWindow):
    enable_dialog_extract=pyqtSignal(bool)
    def __init__(self,application_path=''):
        super().__init__()
        self.voice_binding={}
        self.voice_library=[]
        self.save_path=os.path.join(application_path,'audio')
        self.setup_player()
        self.setup_tts_handler()
        self.setup_ui_connection()
        self.load_binding_from_json()
     
    def setup_tts_handler(self):
        self.tts_handler=EdgeTTSHandler()
        self.tts_handler.tts_finished.connect(self.player.add_play_task)
        self.fetched_mark=False#不希望实例化时立刻更新，在打开窗口时再考虑更新。
        self.tts_handler.voice_list_received.connect(self._handle_tts_list_update)

    def setup_player(self):
        self.player=AudioPlayer()

    def setup_ui_connection(self):
        self.add_button.clicked.connect(self._handle_add_button_click)
        self.enable_extract_button.clicked.connect(self.enable_dialog_extract.emit)

    def _handle_tts_list_update(self,voice_list):
        self.voice_library=voice_list
        self.add_button.setEnabled(True)

    def _handle_add_button_click(self):
        self.show_mask_animation()
        self.voice_choice_window=EdgeTTSSelectionDialog()
        self.voice_choice_window.preview_requested.connect(self._shoot_tts_request)
        self.voice_choice_window.set_voice_data(self.voice_library)
        self.voice_choice_window.voice_selected.connect(self.add_voice_binding)
        self.voice_choice_window.closeing.connect(self.hide_mask_animation)
        self.hide_mask.clicked.connect(self.voice_choice_window.close)
        self.voice_choice_window.show()
 
    def add_voice_binding(self,name,voice_info,binding_id=0):
        
        voice=voice_info['ShortName']
        if not binding_id:
            binding_id= random.randint(100000, 999999)
        voice_item=VoiceItemWidget(binding_id)
        voice_item.item_id=binding_id   #用于唤起修改窗口
        voice_item.set_info(name=name,voice=voice)
        voice_item.request_delete.connect(self.del_voice_binding)
        voice_item.request_change.connect(self._handle_voice_change)

        self.voice_binding[binding_id]={
            'name':name,
            'voice_id':voice,
            'item':voice_item
        }
        self.voice_binding_layout.addWidget(voice_item)

        self.save_binding_to_json()

    def add_voice_binding_load_mode(self,name,voice_info,binding_id=0):
        voice=voice_info['ShortName']
        if not binding_id:
            binding_id= random.randint(100000, 999999)
        voice_item=VoiceItemWidget(binding_id)
        voice_item.item_id=binding_id   #用于唤起修改窗口
        voice_item.set_info(name=name,voice=voice)
        voice_item.request_delete.connect(self.del_voice_binding)
        voice_item.request_change.connect(self._handle_voice_change)

        self.voice_binding[binding_id]={
            'name':name,
            'voice_id':voice,
            'item':voice_item
        }
        self.voice_binding_layout.addWidget(voice_item)


    def del_voice_binding(self, binding_id):
        if binding_info := self.voice_binding.pop(binding_id, None):
            item = binding_info['item']
            
            # 从布局移除
            layout = self.voice_binding_layout
            layout.removeWidget(item)
            
            # 安全删除
            item.setParent(None)
            item.deleteLater()

        self.save_binding_to_json()
    
    def _handle_voice_change(self,binding_id):
        self.show_mask_animation()
        self.voice_change_window=EdgeTTSSelectionDialog()
        self.voice_change_window.set_voice_data(self.voice_library)
        self.voice_change_window.voice_id=binding_id
        self.voice_change_window.name_edit.setText(self.voice_binding[binding_id]['name'])
        self.voice_change_window.preview_requested.connect(self._shoot_tts_request)
        self.voice_change_window.voice_selected.connect(self.change_voice_binding)
        self.voice_change_window.closeing.connect(self.hide_mask_animation)
        self.hide_mask.clicked.connect(self.voice_change_window.close)
        self.voice_change_window.show()

    def change_voice_binding(self,name,voice_info,binding_id=None):
        if not binding_id:
            print('what?',name,voice_info)
        voice=voice_info['ShortName']
        self.voice_binding[binding_id]['name']=name
        self.voice_binding[binding_id]['voice_id']=voice
        self.voice_binding[binding_id]['item'].name_edit.setText(name)
        self.voice_binding[binding_id]['item'].voice_type.setText(voice)

        self.save_binding_to_json()

    def _shoot_tts_request(self,voice_type,content='你好，这是我的声音！'):
        if type(voice_type)==dict:
            voice=voice_type['ShortName']
        elif type(voice_type)==str:
            voice=voice_type
        result_id=str(random.randint(100000,999999))
        output_file=os.path.join(self.save_path,result_id+' '+voice+'.mp3')
        self.tts_handler.run_tts(text=content,voice=voice,output_file=output_file)

    def send_tts_request(self,name,text):
        voice_type=''
        for bind_id,item in self.voice_binding.items():
            if name==item['name']:
                voice_type=item['voice_id']
        if not voice_type and self.voice_binding:
            print(f'name {name} not found,using default')
            voice_type=self.voice_binding[list(self.voice_binding.keys())[0]]['voice_id']
        self._shoot_tts_request(voice_type=voice_type,content=text)

    def save_binding_to_json(self):
        """
        将音色绑定配置保存为JSON格式
        保存格式为字典: {id数字: {'name':名称, 'voice_id':音色ID}}
        """
        
        # 创建保存配置的数据结构
        binding_data = {}
        for binding_id, binding_info in self.voice_binding.items():
            binding_data[binding_id] = {
                'name': binding_info['name'],
                'voice_id': binding_info['voice_id']
            }
        
        # 创建配置目录路径
        os.makedirs(self.save_path, exist_ok=True)  # 确保目录存在
        config_file = os.path.join(self.save_path, 'voice_binding.json')
        
        # 写入JSON文件
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(binding_data, f, indent=4, ensure_ascii=False)
    
        except Exception as e:
            print(f"保存配置失败: {str(e)}")

    
    def load_binding_from_json(self):
        """
        从JSON文件加载音色绑定配置
        加载格式与保存格式一致：{id: {'name':名称, 'voice_id':音色ID}}
        """
        
        # 创建配置目录路径
        os.makedirs(self.save_path, exist_ok=True)  # 确保目录存在
        config_file = os.path.join(self.save_path, 'voice_binding.json')
        
        # 检查配置文件是否存在
        if not os.path.exists(config_file):
            return
        
        try:
            # 读取并解析JSON文件
            with open(config_file, 'r', encoding='utf-8') as f:
                binding_data = json.load(f)
                
            # 清除当前所有绑定
            current_binding_ids = list(self.voice_binding.keys())
            for binding_id in current_binding_ids:
                self.del_voice_binding(binding_id)
            
            # 加载新的绑定配置
            for binding_id_str, binding_info in binding_data.items():
                # 将字符串ID转换为整数
                binding_id = int(binding_id_str)
                
                # 创建临时voice_info结构（与现有API兼容）
                voice_info = {"ShortName": binding_info["voice_id"]}
                
                # 添加绑定（注意：使用原有的binding_id）
                self.add_voice_binding_load_mode(
                    name=binding_info["name"],
                    voice_info=voice_info,
                    binding_id=binding_id  # 使用原有ID而非生成新ID
                )
            
            return True
            
        except Exception as e:
            print(f"加载配置失败: {str(e)}")
            return False
    
    
    def show(self):
        if not self.fetched_mark:
            self.tts_handler.fetch_all_voices()
            self.fetched_mark=True
        self.raise_()
        super().show()
        return


class TTSMainSettingMini(QGroupBox):
    enable_dialog_extract=pyqtSignal(bool)
    def __init__(self,title='快速设置',parent=None):
        super().__init__(title=title)
        widget_layout=QGridLayout()
        self.parent_wiget=parent
        self.setLayout(widget_layout)

        self.use_extract=QCheckBox('启用对话提取')
        self.use_extract.clicked.connect(self.enable_dialog_extract.emit)
        widget_layout.addWidget(self.use_extract,0,0,1,1)

        self.show_mainsetting=QPushButton('打开主设置')
        self.show_mainsetting.clicked.connect(
            lambda _: parent.show() if self.parent_wiget else None
            )
        widget_layout.addWidget(self.show_mainsetting,1,0,1,1)

class TTSIncomeMessageHandler:
    def __init__(self):
        """初始化TTS消息处理器
        
        属性:
        - previous_income: 记录上次已处理的文本内容
        - TERMINATORS: 句子终止符集合（中英文标点）
        - result_list: 临时存储提取的句子列表
        - trans_table: Markdown符号过滤表（替换为空格）
        """
        self.previous_income=''
        self.TERMINATORS = frozenset({'。', '.', '!', '?', '！', '？'})
        self.result_list=[]
        mark_down_symbols = [
            '*', '#', '>', '-', '`', '|', '=', '[', ']', '(', ')', '!', 
            '^', '@', '$', '~', ':', '{', '}', ' ', '\n', '_'
        ]
        self.trans_table=str.maketrans({c: ' ' for c in mark_down_symbols})


    def _find_sentence(self, message: str) -> str:
        if not message or not isinstance(message, str):
            return ''
            
        prev_len = len(self.previous_income)
        
        # 使用字符串方法替代切片比较
        if prev_len > 0 and not message.startswith(self.previous_income):
            self.previous_income = ''
            prev_len = 0

        # 直接遍历原始字符串，避免生成中间切片
        for i in range(prev_len, len(message)):
            if message[i] in self.TERMINATORS:
                end_index = i + 1
                self.previous_income = message[:end_index]
                # 直接返回切片，避免多次计算长度
                return message[prev_len:end_index]
        
        return ''

    def patch_sentence(self, message='',target_length=20,force_remain=False,extrat_dialog=False):
        """消息分句处理（按终止符拆分）
        
        参数:
        - message: 输入文本
        - target_length: 输出触发长度（默认20字符）
        - force_remain: 强制返回剩余文本模式
        
        返回:
        - 达到目标长度: 返回拼接的完整句子
        - 未达目标长度: 返回空字符串
        - 强制模式: 直接返回剩余文本
        
        处理流程:
        1. 清洗消息（移除Markdown符号）
        2. 强制模式直接返回未处理内容
        3. 循环提取完整句子存入result_list
        4. 结果长度达标后清空缓存并返回
        """
        message=self.clean_message(message)
        if extrat_dialog:
            message=self.extract_dialogue(message)
        if force_remain:
            result=message.replace(self.previous_income,'')
            self.previous_income=message
            return result
        iters=0
        final=''
        while iters<20:
            iters+=1
            this_round_result=self._find_sentence(message)
            if this_round_result=="":
                break
            else:
                self.result_list+=[this_round_result]
            final=''.join(self.result_list)
        if len(final)>target_length:
            self.result_list=[]
            return final
        else:
            return ''
        
    def clean_message(self,message):
        """消息清洗器
        
        参数:
        - message: 原始文本
        
        返回:
        - 清洗后的文本（无Markdown符号和空格）
        
        处理逻辑:
        1. 通过转换表替换符号为空格
        2. 移除所有空格
        """
        cleaned = message.translate(self.trans_table)
        
        return cleaned.replace(' ','')

    def extract_dialogue(self,text):
        # 用于存储匹配结果的列表
        dialogues = []
        
        # 匹配完整的引号对（包括单双引号）
        paired_pattern = r'([“"‘\'])(.*?)([”"’\'])'
        for match in re.finditer(paired_pattern, text, flags=re.DOTALL):
            dialogues.append(match.group(2))  # 只捕获引号中间的内容
        
        # 检查未匹配部分（通过替换已匹配区域）
        placeholder = "\x00"  # 使用非常见字符作为占位符
        temp_text = re.sub(paired_pattern, placeholder, text, flags=re.DOTALL)
        
        # 匹配只有左引号（未闭合）的情况
        lonely_left = r'([“"‘\'])((?!.*[”"’\']).*$)'
        left_matches = re.findall(lonely_left, temp_text)
        for match in left_matches:
            dialogues.append(match[1])  # 添加左引号后的内容
        
        # 匹配只有右引号（未闭合）的情况
        lonely_right = r'^((?!.*[“"‘\']).*?)([”"’\'])'
        right_matches = re.findall(lonely_right, temp_text)
        for match in right_matches:
            dialogues.append(match[0])  # 添加右引号前的内容
        # 合并结果
        result = ''.join(d.strip() for d in dialogues if d.strip())
        return result if result else text

class TTSAgent(QGroupBox):
    tts_state=pyqtSignal(bool,str)
    def __init__(self,application_path=''):
        super().__init__()
        self.function_dict={
            'Edge-tts':EdgeTTSMainSetting,
            'CosyVoice':CosyVoiceTTSWindow
        }
        self.message_handler=TTSIncomeMessageHandler()
        self.tts_enabled=False
        self.application_path=application_path
        self.agent_layout=QGridLayout()
        self.setLayout(self.agent_layout)
        self.agent_layout.addWidget(QLabel('声音合成器'),0,0,1,1)
        self.generator_selector=QComboBox()
        self.generator_selector.addItems(['不使用TTS']+list(self.function_dict.keys()))
        self.agent_layout.addWidget(self.generator_selector,1,0,1,1)

        self.current_generator = self.generator_selector.currentText()

        self.generator_selector.currentTextChanged.connect(self.confirm_generator_change)
        self.enable_dialog_extract=False

        self.call_iter=0

    
    def confirm_generator_change(self, name):
        if not name in self.function_dict:
            self.tts_enabled=False
            self.tts_state.emit(self.tts_enabled,'')
        if not hasattr(self, 'generator'):
            self.set_generator(name)
            self.current_generator = name
            return
            
        # 与当前生成器相同时不处理
        if name == self.current_generator:
            return
            
        reply = QMessageBox.question(
            self,
            '生成器更换',
            f'生成器将被更换为{name}，旧任务将被抛弃，要继续吗？',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.set_generator(name)
            self.current_generator = name
            self.tts_state.emit(self.tts_enabled,name)
        else:
            # 还原到更改前的选项
            self.generator_selector.blockSignals(True)  # 临时阻塞信号
            self.generator_selector.setCurrentText(self.current_generator)
            self.generator_selector.blockSignals(False)  # 恢复信号连接


    def set_generator(self, name):
        if not name in self.function_dict:
            self.generator=None
            self.tts_enabled=False
            if hasattr(self,'mini_setting'):
                self.mini_setting.deleteLater()
            return
        self.generator=self.function_dict[name](self.application_path)
        self.generator.enable_dialog_extract.connect(lambda state:setattr(self,'enable_dialog_extract',state))
        self.mini_setting=TTSMainSettingMini(parent=self.generator)
        self.mini_setting.enable_dialog_extract.connect(lambda state:setattr(self,'enable_dialog_extract',state))
        self.agent_layout.addWidget(self.mini_setting,0,1,3,1)
        self.tts_enabled=True

    def send_tts_request(self,name,text,force_remain=False):
        self.call_iter+=1
        if not self.tts_enabled or not text:
            return
        if not force_remain and self.call_iter%5!=0:
            return
        text=self.patch_sentence(message=text,force_remain=force_remain)
        if text:
            self.generator.send_tts_request(name=name,text=text)

    def show_setting(self):
        self.generator.show()
    
    def get_mini_setting_window(self):
        return getattr(self,'mini_setting',QLabel('尚未初始化'))

    def patch_sentence(self,message='',target_length=20,force_remain=False):
        result= self.message_handler.patch_sentence(
            message=message,
            target_length=target_length,
            force_remain=force_remain,
            extrat_dialog=self.enable_dialog_extract)
        return result

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TTSAgent()
    window.show()
    sys.exit(app.exec_())
