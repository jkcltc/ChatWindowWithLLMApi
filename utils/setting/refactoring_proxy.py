import traceback
from utils.setting.data import APP_SETTINGS

class _ModelMapProxy:
    """对model_map的patch，以防哪里没改到连续崩溃"""

    def _log_caller(self, action: str):
        """打印谁在调用"""
        stack = traceback.extract_stack()
        # -3 是因为：当前函数 -> __getitem__ -> 实际调用处
        if len(stack) >= 3:
            caller = stack[-3]
            print(f"[MODEL_MAP] {action} | {caller.filename}:{caller.lineno} | {caller.name}() | {caller.line}")

    def __getitem__(self, key):
        self._log_caller(f"读取 [{key}]")
        return APP_SETTINGS.api.model_map[key]

    def __setitem__(self, key, value):
        self._log_caller(f"写入 [{key}] = {value}")
        if key in APP_SETTINGS.api.providers:
            APP_SETTINGS.api.providers[key].models = value
        else:
            APP_SETTINGS.api.providers[key] = {
                "url": "",
                "key": "",
                "models": value
            }

    def __contains__(self, key):
        self._log_caller(f"检查 [{key}] in")
        return key in APP_SETTINGS.api.model_map

    def __iter__(self):
        self._log_caller("遍历 keys")
        return iter(APP_SETTINGS.api.model_map)

    def keys(self):
        self._log_caller("调用 .keys()")
        return APP_SETTINGS.api.model_map.keys()

    def values(self):
        self._log_caller("调用 .values()")
        return APP_SETTINGS.api.model_map.values()

    def items(self):
        self._log_caller("调用 .items()")
        return APP_SETTINGS.api.model_map.items()

    def get(self, key, default=None):
        self._log_caller(f"调用 .get({key})")
        return APP_SETTINGS.api.model_map.get(key, default)
    

MODEL_MAP = _ModelMapProxy()