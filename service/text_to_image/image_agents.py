from psygnal import Signal
import threading

from core.utils.dispatcher import MainThreadDispatcher
from .providers import BaiduAgent, NovitaAgent, SiliconFlowAgent
from config import APP_SETTINGS, APP_RUNTIME


class ImageAgent:
    pull_success = Signal(str)  # path to image
    failure = Signal(str, str)

    # 支持的图片生成供应商
    SUPPORTED_PROVIDERS = {
        'novita': NovitaAgent,
        'siliconflow': SiliconFlowAgent,
        'baidu': BaiduAgent
    }

    def __init__(self):
        self.generator_name = None
        self.generator = None
        self.generators = {}

        # >>> 缓存只保留图片模型的，和文本模型分开 <<<
        self._image_model_cache = {}
        # 天哪 是老api
        self.generator_dict = self.SUPPORTED_PROVIDERS

        # 主线程回调包装
        self._main_pull_success = MainThreadDispatcher.run_in_main(self.pull_success.emit)
        self._main_failure = MainThreadDispatcher.run_in_main(self.failure.emit)

    @property
    def application_path(self):
        return APP_RUNTIME.paths.application_path

    def _get_api_key(self, provider: str) -> str:
        """从全局配置获取 API Key"""
        if provider in APP_SETTINGS.api.providers:
            return APP_SETTINGS.api.providers[provider].key
        return ""

    def _disconnect_generator(self, generator) -> None:
        try:
            generator.pull_success.disconnect()
        except TypeError:
            pass
        try:
            generator.failure.disconnect()
        except TypeError:
            pass

    def _connect_generator(self, generator) -> None:
        generator.pull_success.connect(self._main_pull_success)
        generator.failure.connect(self._main_failure)

    def set_generator(self, name: str):
        """设置当前使用的图片生成器"""
        self.generator_name = name

        # 清空之前的生成器连接
        if self.generator:
            self._disconnect_generator(self.generator)

        if name in self.SUPPORTED_PROVIDERS:
            api_key = self._get_api_key(name)
            self.generator = self.SUPPORTED_PROVIDERS[name](
                api_key,
                self.application_path,
                save_folder='data/pics'
            )
            self._connect_generator(self.generator)
        else:
            self._main_failure(name, "Provider not supported")
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
                    save_folder='data/pics'
                )
                self._connect_generator(self.generators[name])

            try:
                self.generators[name].update_model_list()
                self._image_model_cache[name] = self.generators[name].get_model_list()
            except Exception as e:
                self._main_failure(name, f"模型更新失败: {str(e)}")

    def update_models_async(self, callback=None):
        """异步更新所有图片模型列表，完成后回调"""
        def _worker():
            self.update_models()
            if callback:
                MainThreadDispatcher.run_in_main(callback)(self._image_model_cache)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return thread
