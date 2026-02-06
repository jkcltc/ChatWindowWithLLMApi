import json
from pathlib import Path
import random

import requests, urllib
import urllib.parse
import threading
from typing import Optional, Dict, List, Tuple, Any
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from config import APP_RUNTIME,APP_SETTINGS, ConfigManager

class ModelListUpdater:
    _lock = threading.Lock()

    @staticmethod
    def _correct_url(url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.rstrip('/')

        if not path.endswith('/models') and not path.endswith('/api/tags'):
            path += '/models'

        return urllib.parse.urlunparse((
            parsed.scheme or 'https',
            parsed.netloc,
            path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))


    @staticmethod
    def is_ollama_alive(url='http://localhost:11434/'):
        try:
            corrected_url = urllib.parse.urljoin(url, 'api/tags')
            response = requests.get(corrected_url, timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False


    @staticmethod
    def get_model_list(platform_config: dict) -> List[str]:
        """
        platform_config: {"url": "...", "key": "..."}
        """
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {platform_config["key"]}'
        }

        try:
            response = requests.get(platform_config["url"], headers=headers)
            response.raise_for_status()

            data = response.json()

            if 'data' in data:
                return [model['id'] for model in data['data']]
            else:
                print(f"返回数据中缺少'data'字段: {data}")
                return []

        except requests.exceptions.RequestException as e:
            print(f"请求失败: {e}")
            return []
        except Exception:
            print("返回的不是有效JSON格式")
            return []


    @staticmethod
    def update() -> Dict[str, List[str]]:
        ollama_alive = ModelListUpdater.is_ollama_alive()
        print(f"Ollama服务状态: {'存活' if ollama_alive else '未启动'}")
        return ModelListUpdater.update_model_map(update_ollama=ollama_alive)


    @staticmethod
    def update_model_map(update_ollama=False) -> Dict[str, List[str]]:
        available_models = {}

        # >>> 直接从 APP_SETTINGS 拿配置 <<<
        providers = APP_SETTINGS.api.providers
        if not providers:
            print("无有效API配置，跳过更新")
            return available_models

        # 构建 api_configs: {name: {"url": ..., "key": ...}}
        api_configs = {}
        for name, config in providers.items():
            if config.key:
                api_configs[name] = {
                    "url": config.url,
                    "key": config.key
                }

        if not update_ollama and "ollama" in api_configs:
            del api_configs["ollama"]
            print("跳过ollama更新")

        threads = []
        results = []
        results_lock = threading.Lock()  # 加个锁，别让多线程打架

        for platform, config in api_configs.items():
            corrected_config = {
                "url": ModelListUpdater._correct_url(config["url"]),
                "key": config["key"]
            }

            def thread_func(plat, cfg):
                try:
                    models = ModelListUpdater.get_model_list(cfg)
                    if models:
                        models.sort()
                        with results_lock:
                            results.append((plat, models))
                        print(f"[{plat}] 获取到 {len(models)} 个模型")
                except Exception as e:
                    print(f"[{plat}] 更新失败: {str(e)}")

            thread = threading.Thread(target=thread_func, args=(platform, corrected_config))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        for plat, models in results:
            available_models[plat] = models

        return available_models

class APIConfigDialogUpdateModelThread(QThread):
    started_signal = pyqtSignal()
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.finished_signal.connect(self.deleteLater)


    def run(self) -> None:
        try:
            self.started_signal.emit()
            # >>> 直接用全局单例 <<<
            available_models = ModelListUpdater.update()
            self.finished_signal.emit(available_models)
        except Exception as e:
            self.error_signal.emit(str(e))

