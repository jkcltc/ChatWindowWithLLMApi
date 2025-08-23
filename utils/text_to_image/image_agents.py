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
        config.read(application_path,encoding='utf-8')
        return config[provider_name]['key']

    @staticmethod
    def get_api_url(application_path='api_config.ini',provider_name=''):
        if not '.ini' in application_path:
            raise AttributeError('api_config should be a .ini file')
        
        config = configparser.ConfigParser()
        config.read(application_path,encoding='utf-8')
        return config[provider_name]['url']

class ImageAgent(QObject):
    pull_success = pyqtSignal(str)  # path to image
    failure = pyqtSignal(str, str)
    
    def __init__(self, application_path):
        super().__init__()
        self.generator_dict = {
            'novita': NovitaAgent,
            'siliconflow': SiliconFlowAgent,
            'baidu': BaiduAgent
        }
        self.generator_name = None
        self.generator = None
        self.application_path = application_path
        self.api_config_path = os.path.join(application_path, 'api_config.ini')
        
        self._model_cache = {}  # 缓存模型列表
        self._model_map_cache = None  # 缓存全局模型映射

        self.generators = {}
    
    def set_generator(self, name):
        """设置当前使用的图片生成器"""
        self.generator_name = name
        
        # 清空之前的生成器连接
        if self.generator:
            try:
                self.generator.pull_success.disconnect()
                self.generator.failure.disconnect()
            except TypeError:
                # 处理未连接的情况
                pass
        
        if name in self.generator_dict:
            api_key = ImageApiConfigReader.get_api_key(self.api_config_path, name)
            self.generator = self.generator_dict[name](
                api_key, 
                self.application_path,
                save_folder='pics'
            )
            # 连接信号
            self.generator.pull_success.connect(self.pull_success.emit)
            self.generator.pull_success.connect(lambda path:print('generator.pull_success',path))
            self.generator.failure.connect(self.failure.emit)
        else:
            # OtherAgent接口，报错
            self.failure.emit(name, "Provider not supported")
            self.generator = None
    
    # 创建主函数
    def create(self, params_dict):
        """创建图片请求"""
        if self.generator:
            self.generator.create(
                self.generator.translate_params(params_dict)
            )
    
    # 获取所有供应商的模型映射
    def get_model_map(self):
        """新增：获取所有提供商的模型映射{provider: [models]}"""
        if self._model_map_cache:
            return self._model_map_cache
        
        model_map = {}
        for provider in self.generator_dict:
            model_map[provider] = self.get_model_list(provider)
        
        self._model_map_cache = model_map
        return model_map
    
    # 获取模型列表
    def get_model_list(self, provider):
        """获取指定供应商的模型列表 - 优化缓存"""
        # 优先使用缓存
        if provider in self._model_cache:
            return self._model_cache[provider]
        
        if provider in self.generator_dict:  
            try:
                # 轻量级获取模型列表
                generator = self.generator_dict[provider]('', self.application_path)
                models = generator.get_model_list()
                self._model_cache[provider] = models
                return models
            except Exception:
                return ['Fail: model list unavailable']
        else:
            return ['Fail:no model list found']
    
    #获取当前模型列表
    def current_model_list(self):
        """获取当前生成器的模型列表"""
        if self.generator:
            return self.generator.get_model_list()
        return []

    def update_models(self):
        """更新模型列表 - 优化缓存管理"""
        # 清除所有缓存
        self._model_cache = {}
        self._model_map_cache = None
        
        for name in self.generator_dict:
            # 重用现有generators字典中的实例或创建新实例
            if name not in self.generators:
                api_key = ImageApiConfigReader.get_api_key(self.api_config_path, name)
                self.generators[name] = self.generator_dict[name](
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
                # 更新缓存
                self._model_cache[name] = self.generators[name].get_model_list()
            except Exception as e:
                self.failure.emit(name, f"模型更新失败: {str(e)}")

