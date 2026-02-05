import importlib
import pkgutil
import inspect
from . import provider_patchs
from common.info_module import LOGMANAGER

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
                module_name = f"service.chat_completion.provider_patchs.{name}"
                importlib.import_module(module_name)
                count += 1
            except Exception as e:
                LOGMANAGER.log(
                    f"补丁模块 {name} 加载错误 "+str(e), 
                    level="error", 
                    exc_info=True
                )


    
    def patch(self, params, provider_type, config_context):
        """
        核心补丁应用逻辑
        策略：精准匹配 -> 启发式匹配 -> OpenAI兜底
        """
        # 1. 预处理：如果没有 provider_type，直接跳到兜底
        if not provider_type:
            provider_type = "openai_compatible"

        input_key = provider_type.lower()
        target_handler = None
        match_method = "none"

        # ---------------------------------------------------
        # Step 1: 精准匹配 (Exact Match) - 优先级最高
        # ---------------------------------------------------
        if input_key in _REGISTRY:
            target_handler = _REGISTRY[input_key]
            match_method = "exact"

        # ---------------------------------------------------
        # Step 2: 启发式匹配 (Heuristic Match) - 模糊查找
        # ---------------------------------------------------
        # 只有精准匹配失败时才执行
        if not target_handler:
            # 遍历注册表，看 registered_key 是否包含在 input_key 中
            # 例如 input="hk-deepseek-v3", registered="deepseek" -> 命中
            for reg_key, handler in _REGISTRY.items():
                if reg_key in input_key:
                    print('reg_key in input_key')
                    target_handler = handler
                    match_method = f"heuristic({reg_key})"
                    break 

        # ---------------------------------------------------
        # Step 3: 兜底回退 (Fallback) - OpenAI Compatible
        # ---------------------------------------------------
        if not target_handler:
            print('not target_handler')
            target_handler = _REGISTRY.get("openai_compatible")
            match_method = "fallback"

            # 如果连 openai_compatible 都没注册，那就彻底没办法了
            if not target_handler:
                return params

        # ---------------------------------------------------
        # Step 4: 执行补丁
        # ---------------------------------------------------
        if target_handler:
            try:
                # 注入 Log Manager
                if 'LOGMANAGER' in globals():
                    config_context['log_manager'] = LOGMANAGER

                if inspect.isclass(target_handler):
                    return target_handler().patch(params, config_context)
                elif callable(target_handler):
                    return target_handler(params, config_context)

            except Exception as e:
                # 捕获插件运行时的锅，警告并返回原参数
                err_msg = f"应用补丁失败 ({provider_type} -> {match_method}): {str(e)}"
                if 'LOGMANAGER' in globals():
                    LOGMANAGER.log(err_msg, level="error", exc_info=True)
                return params

        return params

    @ property
    def patch_list(self) -> list[str]:
        """
        所有已注册的补丁关键词列表
        """
        return sorted(list(_REGISTRY.keys()))

