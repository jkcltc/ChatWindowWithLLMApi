from PyQt5.QtCore import QObject,pyqtSignal
import threading,os
import configparser
from typing import Dict, Type
if __name__=="__main__":#single file test only
    from novita_model_manager import NovitaImageGenerator
else:
    from .novita_model_manager import NovitaImageGenerator

class NovitaAgent(QObject):
    pull_success=pyqtSignal(str)
    failure=pyqtSignal(str,str)

    def __init__(self, api_key,application_path):
        """
        Initializes the model manager with the provided API key and application path.
        Args:
            api_key (str): The API key used for authentication with the Novita image generator.
            application_path (str): The path to the application directory.
        Attributes:
            generator (NovitaImageGenerator): Instance responsible for image generation and event signaling.
            thread_list (list): List to keep track of threads, reset on successful pull.
        Signals:
            request_emit: Connected to NA_poll_result method to handle request events.
            pull_success: Connected to both pull_success.emit and a lambda to reset thread_list.
            failure: Connected to failure.emit to handle failure events.
        """

        self.generator=NovitaImageGenerator(api_key,application_path)
        self.generator.request_emit.connect(self.poll_result)
        self.generator.pull_success.connect(self.pull_success.emit)
        self.generator.failure.connect(self.failure.emit)
        self.generator.pull_success.connect(lambda _:setattr(self,'thread_list',[]))
        self.thread_list=[]

    def create(self, config):
        """
        升级为自动工作流，接受字典参数
        config 字典需包含以下键（括号内为默认值）：
            prompt:         正向提示词（必需）
            model_name:     模型名称（必需）
            negative_prompt:负面提示词（必需）
            width:          图片宽度(512)
            height:         图片高度(512)
            image_num:      生成数量(1)
            steps:          迭代步数(20)
            seed:           随机种子(-1)
            clip_skip:      CLIP跳过层数(1)
            sampler_name:   采样器名称("Euler a")
            guidance_scale: 指导系数(7.5)
        """
        # 解包字典参数并设置默认值
        self.create_thread = threading.Thread(target=self.generator.generate, args=(
            config['prompt'],
            config['model_name'],
            config['negative_prompt'],
            config.get('width', 512),
            config.get('height', 512),
            config.get('image_num', 1),
            config.get('steps', 20),
            config.get('seed', -1),
            config.get('clip_skip', 1),
            config.get('sampler_name', "Euler a"),
            config.get('guidance_scale', 7.5)
        ))
        
        self.thread_list.append(self.create_thread)
        self.create_thread.start()
    
    def poll_result(self,task_id):
        self.poll_thread=threading.Thread(target=self.generator.poll_result,args=(
            task_id
            )
        )
        self.thread_list+=[self.poll_thread]
        self.poll_thread.start()
    
    def clear_thread(self):
        self.thread_list=[]

class ParamTranslator:
    @staticmethod
    def translate_params(target_model,params_dict):
        #当前只支持了novita，直接返回就可以了
        return params_dict


class ImageApiConfigReader:
    @staticmethod
    def get_api_key(application_path='api_config.ini',provider_name=''):
        if not '.ini' in application_path:
            raise AttributeError('api_config should be a .ini file')
        config = configparser.ConfigParser()
        config.read(application_path)
        return config[provider_name]['key']
    

class ImageAgent(QObject):      #Factory Class
                                #waiting 0.25.2 patch
    pull_success=pyqtSignal(str)
    failure=pyqtSignal(str,str)
    def __init__(self,application_path):
        super().__init__()  # 确保正确初始化QObject
        self.generator_dict = {
            'novita': NovitaAgent
        }
        self.generator_name = None
        self.generator = None 
        self.application_path=application_path
        self.api_config_path=os.path.join(self.application_path,'api_config.ini')
        
    def set_generator(self,name):
        self.generator_name=name
        api_key=ImageApiConfigReader.get_api_key(self.api_config_path,name)
        self.generator=self.generator_dict[name](api_key,self.application_path)
        self.generator.pull_success.connect(self.pull_success.emit)
        self.generator.failure.connect(self.failure.emit)

    def create(self,params_dict):
        self.generator.create(
            self.translate_params(params_dict)
            )
    
    def translate_params(self,params_dict):
        return ParamTranslator.translate_params(self.generator_name,params_dict)

