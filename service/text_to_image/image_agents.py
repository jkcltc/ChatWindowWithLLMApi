from PyQt6.QtCore import QObject, pyqtSignal
from utils.text_to_image.providers.novita.novita_model_manager import NovitaAgent
from utils.text_to_image.providers.siliconflow.siliconflow_agent import SiliconFlowAgent
from utils.text_to_image.providers.baidu.baidu_agent import BaiduAgent

from utils.setting import APP_SETTINGS, APP_RUNTIME


class ImageAgent(QObject):
    pull_success = pyqtSignal(str)  # path to image
    failure = pyqtSignal(str, str)

    # 支持的图片生成供应商
    SUPPORTED_PROVIDERS = {
        'novita': NovitaAgent,
        'siliconflow': SiliconFlowAgent,
        'baidu': BaiduAgent
    }

    def __init__(self):
        super().__init__()
        self.generator_name = None
        self.generator = None
        self.generators = {}

        # >>> 缓存只保留图片模型的，和文本模型分开 <<<
        self._image_model_cache = {}
        # 天哪 是老api
        self.generator_dict=self.SUPPORTED_PROVIDERS

    @property
    def application_path(self):
        return APP_RUNTIME.paths.application_path

    def _get_api_key(self, provider: str) -> str:
        """从全局配置获取 API Key"""
        if provider in APP_SETTINGS.api.providers:
            return APP_SETTINGS.api.providers[provider].key
        return ""

    def set_generator(self, name: str):
        """设置当前使用的图片生成器"""
        self.generator_name = name

        # 清空之前的生成器连接
        if self.generator:
            try:
                self.generator.pull_success.disconnect()
                self.generator.failure.disconnect()
            except TypeError:
                pass

        if name in self.SUPPORTED_PROVIDERS:
            api_key = self._get_api_key(name)
            self.generator = self.SUPPORTED_PROVIDERS[name](
                api_key, 
                self.application_path,
                save_folder='pics'
            )
            self.generator.pull_success.connect(self.pull_success.emit)
            self.generator.pull_success.connect(lambda path: print('generator.pull_success', path))
            self.generator.failure.connect(self.failure.emit)
        else:
            self.failure.emit(name, "Provider not supported")
            self.generator = None

    def create(self, params_dict):
        """创建图片请求"""
        if self.generator:
            self.generator.create(
                self.generator.translate_params(params_dict)
            )

    def get_image_model_map(self) -> dict:
        """
        获取图片生成供应商的模型映射
        注意：这是图片模型，和 APP_SETTINGS.api.model_map（文本模型）不同
        """
        if self._image_model_cache:
            return self._image_model_cache

        model_map = {}
        for provider in self.SUPPORTED_PROVIDERS:
            model_map[provider] = self.get_model_list(provider)

        self._image_model_cache = model_map
        return model_map

    def get_model_list(self, provider: str) -> list:
        """获取指定供应商的图片模型列表"""
        if provider in self._image_model_cache:
            return self._image_model_cache[provider]

        if provider in self.SUPPORTED_PROVIDERS:
            try:
                api_key = self._get_api_key(provider)
                generator = self.SUPPORTED_PROVIDERS[provider](
                    api_key, 
                    self.application_path
                )
                models = generator.get_model_list()
                self._image_model_cache[provider] = models
                return models
            except Exception:
                return ['Fail: model list unavailable']
        else:
            return ['Fail: no model list found']

    def current_model_list(self) -> list:
        """获取当前生成器的模型列表"""
        if self.generator:
            return self.generator.get_model_list()
        return []

    def update_models(self):
        """更新所有图片模型列表"""
        self._image_model_cache = {}

        for name in self.SUPPORTED_PROVIDERS:
            if name not in self.generators:
                api_key = self._get_api_key(name)
                self.generators[name] = self.SUPPORTED_PROVIDERS[name](
                    api_key,
                    self.application_path,
                    save_folder='pics'
                )
                self.generators[name].pull_success.connect(self.pull_success.emit)
                self.generators[name].failure.connect(self.failure.emit)

            try:
                self.generators[name].update_model_list()
                self._image_model_cache[name] = self.generators[name].get_model_list()
            except Exception as e:
                self.failure.emit(name, f"模型更新失败: {str(e)}")
