import importlib
import pkgutil
import inspect
from utils.tools import provider_patchs
from utils.info_module import LOGMANAGER

# 现在的注册表
_REGISTRY = {}

def register_provider(provider_keywords):
    def decorator(cls_or_func):
        keys = [provider_keywords] if isinstance(provider_keywords, str) else provider_keywords
        for k in keys:
            _REGISTRY[k.lower()] = cls_or_func
        return cls_or_func
    return decorator

class GlobalPatcher:
    _instance = None
    _loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GlobalPatcher, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._loaded:
            self._load_plugins()
            self.__class__._loaded = True

    def _load_plugins(self):

        count = 0
        for finder, name, ispkg in pkgutil.iter_modules(provider_patchs.__path__):
            try:
                module_name = f"utils.tools.provider_patchs.{name}"
                importlib.import_module(module_name)
                count += 1
            except Exception as e:
                LOGMANAGER.log(
                    f"补丁模块 {name} 加载错误 "+str(e), 
                    level="error", 
                    exc_info=True
                )


    def patch(self, params, provider_url, config_context):
        if not provider_url:
            return params

        provider_key = provider_url.lower()
        target_handler = None

        for key, handler in _REGISTRY.items():
            if key in provider_key:
                target_handler = handler
                break

        if target_handler:
            try:
                config_context['log_manager'] = LOGMANAGER

                if inspect.isclass(target_handler):
                    return target_handler().patch(params, config_context)
                elif callable(target_handler):
                    return target_handler(params, config_context)

            except Exception as e:
                # 捕获插件运行时的锅，警告
                LOGMANAGER.log(
                    f"处理供应商 {provider_key} 补丁时发生异常 "+str(e), 
                    level="error", 
                    exc_info=True
                )
                return params

        return params

