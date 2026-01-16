
import os,sys


import configparser
import pytest
from pathlib import Path
from typing import Optional, Dict

from utils.setting import APP_SETTINGS, APP_RUNTIME
from utils.setting.data import ProviderConfig


class IniConfigAdapter:
    """
    INI 配置适配器
    把 api_config.ini 的内容注入到 APP_SETTINGS.api.providers
    """

    DEFAULT_INI_PATHS = [
        "api_config.ini",
        "utils/api_config.ini",
    ]

    @classmethod
    def find_ini_file(cls) -> Optional[Path]:
        """
        自动查找 api_config.ini 文件
        按优先级搜索多个可能的位置
        """
        search_paths = list(cls.DEFAULT_INI_PATHS)

        # 加上 application_path 下的路径
        if APP_RUNTIME.paths.application_path:
            search_paths.append(
                os.path.join(APP_RUNTIME.paths.application_path, "api_config.ini")
            )

        for path_str in search_paths:
            path = Path(path_str)
            if path.exists():
                return path

        return None

    @classmethod
    def load_from_ini(cls, ini_path: Optional[str] = None, overwrite: bool = True) -> Dict[str, dict]:
        """
        从 ini 文件加载配置并注入到 APP_SETTINGS

        :param ini_path: ini 文件路径，None 则自动查找
        :param overwrite: 是否覆盖已有配置（False 则只填充空值）
        :return: 加载的配置字典 {provider: {"url": ..., "key": ...}}
        """
        # 查找 ini 文件
        if ini_path:
            path = Path(ini_path)
        else:
            path = cls.find_ini_file()

        if not path or not path.exists():
            print(f"[IniAdapter] 找不到 api_config.ini")
            return {}

        print(f"[IniAdapter] 从 {path} 加载配置...")

        # 解析 ini
        config = configparser.ConfigParser()
        config.read(path, encoding='utf-8')

        loaded = {}
        for section in config.sections():
            try:
                url = config.get(section, "url", fallback="").strip()
                key = config.get(section, "key", fallback="").strip()

                loaded[section] = {"url": url, "key": key}

                # 注入到 APP_SETTINGS
                cls._inject_provider(section, url, key, overwrite)

                print(f"[IniAdapter] ✓ {section}: {url[:30]}..." if url else f"[IniAdapter] ✓ {section}: (空URL)")

            except Exception as e:
                print(f"[IniAdapter] ✗ {section} 解析失败: {e}")

        return loaded

    @classmethod
    def _inject_provider(cls, name: str, url: str, key: str, overwrite: bool):
        """
        将单个 provider 注入到 APP_SETTINGS
        """
        if name in APP_SETTINGS.api.providers:
            provider = APP_SETTINGS.api.providers[name]
            if overwrite:
                provider.url = url
                provider.key = key
            else:
                # 只填充空值
                if not provider.url:
                    provider.url = url
                if not provider.key:
                    provider.key = key
        else:
            # 新增 provider
            APP_SETTINGS.api.providers[name] = ProviderConfig(
                url=url,
                key=key,
                models=[]
            )

    @classmethod
    def export_to_ini(cls, ini_path: str = "api_config_backup.ini"):
        """
        反向操作：把 APP_SETTINGS 导出到 ini 文件（备份用）
        """
        config = configparser.ConfigParser()

        for name, provider in APP_SETTINGS.api.providers.items():
            config[name] = {
                "url": provider.url,
                "key": provider.key,
            }

        with open(ini_path, 'w', encoding='utf-8') as f:
            config.write(f)

        print(f"[IniAdapter] 已导出到 {ini_path}")
    
def init_settings_from_ini(ini_path: Optional[str] = None) -> Dict[str, dict]:
    """
    一键初始化：从 ini 加载配置到 APP_SETTINGS

    用法:
        from utils.setting.ini_adapter import init_settings_from_ini
        init_settings_from_ini()  # 自动查找 ini
        init_settings_from_ini("path/to/config.ini")  # 指定路径
    """
    return IniConfigAdapter.load_from_ini(ini_path)

#init_settings_from_ini()

#from CWLA_main import start
#start()