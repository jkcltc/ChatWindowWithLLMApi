import os, json
from pydantic import ValidationError
from common.info_module import LOGMANAGER

class ConfigManager:
    """
    服务于全局单例对象。
    """

    @staticmethod
    def load_settings(singleton_obj, filename: str = 'config.json'):
        """
        读取配置文件，并将数据原地注入到传入的单例对象中。
        确保内存地址不变，全局引用不断连。

        :param singleton_obj: 全局的 APP_SETTINGS 实例
        :param filename: 配置文件路径
        """
        if not os.path.exists(filename):
            LOGMANAGER.warning(f"Config file '{filename}' not found. Using default internal values.")
            return

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            singleton_obj.update(data)

            LOGMANAGER.info(f"Global configuration updated from '{filename}'.")

        except json.JSONDecodeError:
            LOGMANAGER.error(f"JSON format error in '{filename}'. Settings not updated.")
        except Exception as e:
            LOGMANAGER.error(f"Failed to load settings: {e}")


    @staticmethod
    def save_settings(singleton_obj, filename: str = 'data/config.json'):
        """
        保存单例对象的状态到文件。
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json_data = singleton_obj.model_dump(mode='json', exclude_none=False)
                json.dump(json_data, f, ensure_ascii=False, indent=4)

            #LOGMANAGER.success(f"Configuration saved to '{filename}'.")

        except Exception as e:
            LOGMANAGER.error(f"Critical Error saving config: {e}")