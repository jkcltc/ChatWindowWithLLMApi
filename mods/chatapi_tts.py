#chatapi_tts.py
import requests,os,sys
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
import threading
from utils.tools.init_functions import install_packages

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


#if __name__ == "__main__":
#    app = QApplication(sys.argv)
#    window = TTSWindow()
#    window.show()
#    sys.exit(app.exec_())
def run():
    install_packages({'edge-tts':'edge_tts'})
    'run'