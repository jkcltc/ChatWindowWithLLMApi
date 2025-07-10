from PyQt5.QtCore import QObject,pyqtSignal
import os
import configparser
if __name__=='__main__':
    from providers.novita.novita_model_manager import NovitaAgent
    from providers.siliconflow.siliconflow_agent import SiliconFlowAgent
    from providers.baidu.baidu_agent import BaiduAgent
else:
    from .providers.novita.novita_model_manager import NovitaAgent
    from .providers.siliconflow.siliconflow_agent import SiliconFlowAgent
    from .providers.baidu.baidu_agent import BaiduAgent


class ImageApiConfigReader:
    @staticmethod
    def get_api_key(application_path='api_config.ini',provider_name=''):
        if not '.ini' in application_path:
            raise AttributeError('api_config should be a .ini file')
        
        config = configparser.ConfigParser()
        config.read(application_path)
        return config[provider_name]['key']

    @staticmethod
    def get_api_url(application_path='api_config.ini',provider_name=''):
        if not '.ini' in application_path:
            raise AttributeError('api_config should be a .ini file')
        
        config = configparser.ConfigParser()
        config.read(application_path)
        return config[provider_name]['url']

class ImageAgent(QObject):
    pull_success = pyqtSignal(str)  # path to image
    failure = pyqtSignal(str, str)
    
    def __init__(self, application_path):
        super().__init__()
        # 预定义支持的生成器类型
        self.generator_classes = {
            'novita': NovitaAgent,
            'siliconflow': SiliconFlowAgent,
            'baidu': BaiduAgent
        }
        self.active_generator = None
        self.application_path = application_path
        self.api_config_path = os.path.join(application_path, 'api_config.ini')
        
        # 缓存模型列表，键值对: {provider_name: [model_list]}
        self.model_cache = {}  
        
    def set_generator(self, name):
        """设置当前使用的图片生成器"""
        self.active_generator = None
        
        if name in self.generator_classes:
            api_key = ImageApiConfigReader.get_api_key(self.api_config_path, name)
            self.active_generator = self.generator_classes[name](
                api_key, self.application_path, save_folder='pics'
            )
            # 连接信号
            self.active_generator.pull_success.connect(self.pull_success.emit)
            self.active_generator.failure.connect(self.failure.emit)
        else:
            # OtherAgent 接口保留但暂时不做实现
            self.failure.emit(name, "Provider not supported")
            
    def create(self, params_dict):
        """创建图片请求"""
        if self.active_generator:
            self.active_generator.create(
                self.active_generator.translate_params(params_dict)
            )

    def get_model_map(self):
        """获取所有提供商的模型映射表（轻量级）"""
        # 尝试读取缓存
        if hasattr(self, '_model_map_cache'):
            return self._model_map_cache
        
        model_map = {}
        for provider in self.generator_classes:
            model_map[provider] = self._get_cached_model_list(provider)
        
        # 缓存结果
        self._model_map_cache = model_map
        return model_map

    def _get_cached_model_list(self, provider):
        """获取缓存的模型列表，避免重复实例化"""
        if provider in self.model_cache:
            return self.model_cache[provider]
        
        if provider in self.generator_classes:
            try:
                # 轻量级获取模型列表：使用最低权限实例
                temp_agent = self.generator_classes[provider]('', self.application_path)
                model_list = temp_agent.get_model_list()
                self.model_cache[provider] = model_list
                return model_list
            except Exception:
                return ['Failed to load models']
        return ['Provider not available']
    
    def current_model_list(self):
        """获取当前生成器的模型列表"""
        if self.active_generator:
            return self.active_generator.get_model_list()
        return []
    
    def update_models(self):
        """更新所有提供商的模型列表"""
        # 清除缓存
        self.model_cache = {}
        self._model_map_cache = None
        
        for provider in self.generator_classes:
            try:
                api_key = ImageApiConfigReader.get_api_key(self.api_config_path, provider)
                temp_agent = self.generator_classes[provider](api_key, self.application_path)
                temp_agent.update_model_list()
                # 更新缓存
                self.model_cache[provider] = temp_agent.get_model_list()
            except Exception as e:
                self.failure.emit(provider, f"Model update failed: {str(e)}")
#我先丢一坨需要重构的屎在这里

#图片创建器
'''
class PromptGenerationWorker(QThread):# 0.25.2 等待重构
    result_ready = pyqtSignal(str)
    
    def __init__(self, func, mode, input_text):
        super().__init__()
        self.func = func
        self.mode = mode
        self.input_text = input_text

    def run(self):
        result = self.func(mode=self.mode, pic_creater_input=self.input_text)
        self.result_ready.emit(str(result))

class APICallWorker(QThread):# 0.25.2 等待重构
    finished = pyqtSignal()
    
    def __init__(self, main_window, return_prompt):
        super().__init__()
        self.main_window = main_window
        self.return_prompt = return_prompt

    def run(self):
        self.main_window.back_ground_update_thread_to_novita(
            return_prompt=self.return_prompt
        )
        self.finished.emit()

class PicCreaterWindow(QWidget):# 0.25.2 等待重构
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window)
        self.resize(600, 400)
        self.main_window = parent
        self.setup_ui()
        
    def setup_ui(self):
        layout = QGridLayout(self)
        
        # 第一行控件
        label_desc = QLabel("文生图描述")
        layout.addWidget(label_desc, 1, 0, 1, 1)
        
        self.send_btn = QPushButton("发送")
        layout.addWidget(self.send_btn, 1, 1, 1, 1)
        
        # 第二行控件
        self.desc_input = QTextEdit()
        layout.addWidget(self.desc_input, 2, 0, 1, 2)
        
        # 第三行控件
        self.label_prompt = QLabel("生成的prompt")
        layout.addWidget(self.label_prompt, 3, 0, 1, 2)
        
        # 第四行控件
        self.ai_created_prompt = QTextBrowser()
        layout.addWidget(self.ai_created_prompt, 4, 0, 1, 2)
        self.novita_model = QComboBox()
        self.novita_model.addItems(NOVITA_MODEL_OPTIONS)
        # 设置默认选中项
        self.novita_model.setCurrentText('foddaxlPhotorealism_v45_122788.safetensors')
        self.main_window.novita_model = self.novita_model.currentText()
        layout.addWidget(self.novita_model,0,0,1,2)
        
        # 设置布局自适应
        layout.setColumnStretch(0, 3)
        layout.setColumnStretch(1, 1)
        layout.setRowStretch(1, 2)
        layout.setRowStretch(3, 2)
        
        self.send_btn.clicked.connect(self.start_background_task)


    def start_background_task(self):
        self.send_btn.setEnabled(False)
        self.ai_created_prompt.setText('已发送。等待生成。')
        self.label_prompt.setText("生成的prompt")

        if self.main_window and not hasattr(self.main_window, 'novita_model'):
            self.main_window.novita_model = self.novita_model.currentText()
        input_text = self.desc_input.toPlainText()
        self.prompt_worker = PromptGenerationWorker(
            func=self.main_window.back_ground_update_thread,
            mode='pic_creater',
            input_text=input_text
        )
        self.prompt_worker.result_ready.connect(self.handle_result)
        self.prompt_worker.start()

    def handle_result(self, return_prompt):
        # UI操作保持在主线程
        self.ai_created_prompt.setText(return_prompt)
        # 启动新的线程处理API调用
        self.api_worker = NovitaAPICallWorker(
            self.main_window, 
            return_prompt
        )
        self.api_worker.start()
        self.send_btn.setEnabled(True)
        self.label_prompt.setText("等待Novita api响应")
'''

if __name__=='__main__':
    from PyQt5.QtWidgets import QApplication
    import sys
    app = QApplication([])
    a=ImageAgent(application_path=r'C:\Users\kcji\Desktop\te\ChatWindowWithLLMApi')
    a.set_generator('baidu')
    a.pull_success.connect(print)
    a.failure.connect(print)
    a.create(
        {
        'prompt': "一棵飞行的苹果树",      # 必选
        'model': "irag-1.0",      # 模型名称
        'negative_prompt': "卡通",     # 负面提示词
        }
    )
    sys.exit(app.exec_())

