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


class ImageAgent(QObject):      #Factory Class
                                #waiting 0.25.2 patch
    pull_success=pyqtSignal(str)#path to image
    failure=pyqtSignal(str,str)
    def __init__(self,application_path):
        super().__init__()  # 确保正确初始化QObject
        self.generator_dict = {
            'novita': NovitaAgent,
            'siliconflow':SiliconFlowAgent,
            'baidu':BaiduAgent
        }
        self.generator_name = None
        self.generator = None 
        self.application_path=application_path
        self.api_config_path=os.path.join(self.application_path,'api_config.ini')
        self.generators = {}#只在更新时使用
        
    def set_generator(self,name):
        """
        Sets the image generator to use based on the provided name.

        This method updates the current generator by:
        - Storing the generator's name.
        - Retrieving the API key for the specified generator using the configuration reader.
        - Instantiating the generator object with the API key, application path, and a save folder.
        - Connecting the generator's `pull_success` and `failure` signals to the corresponding signals of this class.

        Args:
            name (str): The name of the image generator to set.
        """
        self.generator_name=name
        api_key=ImageApiConfigReader.get_api_key(self.api_config_path,name)
        if name in self.generator_dict:  
            self.generator=self.generator_dict[name](api_key,self.application_path,save_folder='pics')
        else:
            base_url=ImageApiConfigReader.get_api_url(provider_name=name)
            from .providers.other.other_agent import OtherAgent
            self.generator=OtherAgent(api_key,base_url,self.application_path,save_folder='pics',name=name)

        self.generator.pull_success.connect(self.pull_success.emit)
        self.generator.failure.connect(self.failure.emit)

    def create(self,params_dict):
        '''
        {
            #Required:
            'prompt': "required",     
            'model': "required", 
            'negative_prompt': "",              # 负面提示实际上没有也行
            
            
            #Unversal
            'width': 512,                       # 生成图片宽度（像素），默认512
            'height': 512,                      # 生成图片高度（像素），默认512
            'image_num': 1,
            'steps': 20,
            'seed': -1,
            'guidance_scale': 7.5,
            'image_num': 1,
            
            #Novita
            'seed': -1,                         # 随机种子，-1表示随机生成
            'clip_skip': 1,                     # CLIP跳过层数，默认1
            'sampler_name': "Euler a",          # 采样器名称，默认"Euler a"
            'guidance_scale': 7.5,               # 指导系数(CFG)，默认7.5

            #Siliconflow

            #baidu
            'refer_image': None,
            'user_id': None
        }
        '''
        self.generator.create(
            self.generator.translate_params(params_dict)
            )

    def get_model_list(self,provider):
        """
        Retrieves the list of available models for a specified provider.

        Args:
            provider (str): The name of the provider whose model list is to be retrieved.

        Returns:
            list: A list of model names available for the given provider. If the provider is not found,
                  returns a list containing a single string indicating failure.
        """
        if provider in self.generator_dict:
            generator=self.generator_dict[provider]('',self.application_path)
            return generator.get_model_list()
        else:
            return ['Fail:no model list found']
        
    
    def current_model_list(self):
        return self.generator.get_model_list()

    def update_models(self):
        # 遍历所有支持的生成器类型
        for name, generator_class in self.generator_dict.items():
            # 如果实例不存在则创建
            if name not in self.generators:
                api_key = ImageApiConfigReader.get_api_key(self.api_config_path, name)
                self.generators[name] = generator_class(
                    api_key,
                    self.application_path,
                    save_folder='pics'
                )
                # 连接信号
                self.generators[name].pull_success.connect(self.pull_success.emit)
                self.generators[name].failure.connect(self.failure.emit)
            
            # 执行模型更新
            try:
                self.generators[name].update_model_list()
            except Exception as e:
                self.failure.emit(name, f"模型更新失败: {str(e)}")


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

