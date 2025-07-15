#chatapi_tts.py
import requests,os,sys
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
import threading
from utils.tools.init_functions import install_packages
from utils.custom_widget import WindowAnimator

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
        with open(r'C:\Users\Administrator\Desktop\github\ChatWindowWithLLMApi\theme\ds-r1-0528.qss','r',encoding='utf-8') as f:
            self.setStyleSheet(f.read())
        self.setWindowTitle("语音角色设置")
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        self.voice_data = []
        self.setup_ui()

    def setup_ui(self):
        main_layout = QGridLayout()
        main_layout.setContentsMargins(15,15,15,15)

        # 角色设置区域
        row=0
        main_layout.setRowStretch(row,1)
        pos_left=1
        pos_mlf=2
        pos_mid=3
        pos_mrt=4
        pos_right=5
        
        main_label=QLabel("指定音色")
        main_label_font = main_label.font()
        main_label_font.setPointSize(main_label_font.pointSize() + 5)
        main_label_font.setBold(True)
        main_label.setFont(main_label_font)
        main_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(main_label,row    ,pos_left  ,2,2)

        main_layout.setRowStretch(row,0)

        main_layout.addWidget(QLabel("角色:"),row   ,pos_mid    ,1,1)


        self.name_edit=QLineEdit()
        self.name_edit.setToolTip('要绑定角色的名字')
        self.name_edit.textChanged.connect(self._check_enable_add)
        main_layout.addWidget(self.name_edit,row   ,pos_mrt    ,1,2)


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
        place_holder=QFrame()
        place_holder.setMinimumHeight(10)
        main_layout.addWidget(place_holder,    row,    pos_mid,1,3)


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

        main_layout.addWidget(QFrame(),row,pos_mid,1,1)

        row+=1
        main_layout.setRowStretch(row,0)
        
        self.add_btn = QPushButton("添加")
        self.add_btn.clicked.connect(self.accept_selection)
        self.add_btn.setEnabled(False)

        main_layout.addWidget(self.add_btn,     row,pos_mlf,1,3)

        #占位符

        #main_layout.addWidget(QFrame(),0,0,row,2)
        #main_layout.addWidget(QFrame(),0,pos_right,row,2)


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


#if __name__ == "__main__":
#    app = QApplication(sys.argv)
#    window = TTSWindow()
#    window.show()
#    sys.exit(app.exec_())
def run():
    install_packages({'edge-tts':'edge_tts'})
    'run'