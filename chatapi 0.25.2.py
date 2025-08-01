import time
start_time_stamp=time.time()
print(f'Chatapi Main window init timer start, time cost:{time.time()-start_time_stamp:.2f}s')
import concurrent.futures
import configparser
import copy
import ctypes
from collections import deque
import json
import os
import re
import sys
import threading
import difflib
import random
from typing import Any, Dict, List, Tuple,Optional
import urllib
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message="libpng warning: iCCP: known incorrect sRGB profile")

#基础类初始化
from utils.tools.init_functions import *

print(f'Chatapi Main window iner import finished, time cost:{time.time()-start_time_stamp:.2f}s')

install_packages()

#第三方类初始化
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtSvg import *
import requests
import openai

print(f'Chatapi Main window 3rd party lib import finished, time cost:{time.time()-start_time_stamp:.2f}s')

#自定义类初始化
from utils.custom_widget import *
from utils.system_prompt_updater import SystemPromptUI
from utils.settings import *
from utils.model_map_manager import ModelMapManager,ModelListUpdater,APIConfigWidget
from utils.theme_manager import ThemeSelector
from utils.function_manager import *
from utils.concurrentor import ConvergenceDialogueOptiProcessor
from utils.preset_data import *
from utils.usage_analysis import TokenAnalysisWidget
from utils.chat_history_manager import *
from utils.online_rag import *
from utils.avatar import AvatarCreatorWindow
from utils.background_generate import BackgroundAgent

print(f'Chatapi Main window custom lib import finished, time cost:{time.time()-start_time_stamp:.2f}s')

#自定义插件初始化
try:
    pass
except ImportError:
    print("GptToCad模块导入失败，CAD功能不可用。")

try:
    from mods.chatapi_tts import TTSAgent
except ImportError as e:
    print("本地tts模块导入失败，TTS功能不可用。",e)

try :
    from mods.status_monitor import StatusMonitorWindow,StatusMonitorInstruction
except ImportError as e:
    print("本地AI状态模块导入失败，状态监控功能不可用。",e)

try:
    from mods.story_creator import StoryCreatorGlobalVar,MainStoryCreaterInstruction
except ImportError as e:
    print('主线生成器未挂载')

print(f'Chatapi Main window mod lib import finished, time cost:{time.time()-start_time_stamp:.2f}s')

#路径初始化
if getattr(sys, 'frozen', False):
    # 打包后的程序
    application_path = os.path.dirname(sys.executable)
    temp_path = sys._MEIPASS
else:
    # 普通 Python 脚本
    application_path = os.path.dirname(os.path.abspath(__file__))

# 常量定义
API_CONFIG_FILE = "api_config.ini"
if not os.path.exists("api_config.ini"):
    with open("api_config.ini", "w") as f:
        f.write('')

DEFAULT_APIS = {
    "baidu": {
        "url": "https://qianfan.baidubce.com/v2",
        "key": "unknown"
    },
    "deepseek": {
        "url": "https://api.deepseek.com/v1",
        "key": "unknown"
    },
    "siliconflow": {
        "url": "https://api.siliconflow.cn/v1",
        "key": "unknown"
    },
    "tencent": {
        "url": "https://api.lkeap.cloud.tencent.com/v1",
        "key": "unknown"
    },
    "novita":{
        "url": "https://api.novita.ai/v3",
        "key": "unknown"
    }
}
MODEL_MAP = ModelMapManager().get_model_map()
#同步模型
def _create_default_config():
    """创建默认配置文件并返回默认API配置"""
    config = configparser.ConfigParser()
    for api_name, api_config in DEFAULT_APIS.items():
        config[api_name] = api_config
    
    try:
        with open(API_CONFIG_FILE, "w") as configfile:
            config.write(configfile)
    except IOError as e:
        QMessageBox.critical(None, "配置错误", f"无法创建配置文件：{str(e)}")
        return {}
    
    return {k: [v["url"], v["key"]] for k, v in DEFAULT_APIS.items()}

def _read_existing_config():
    """读取已存在的配置文件"""
    config = configparser.ConfigParser()
    api_data = {}
    
    try:
        if not config.read(API_CONFIG_FILE,encoding='utf-8'):
            raise FileNotFoundError
        
        for api_name in config.sections():
            if config.has_section(api_name):
                url = config.get(api_name, "url", fallback="")
                key = config.get(api_name, "key", fallback="")
                api_data[api_name] = [url, key]
                DEFAULT_APIS[api_name]={'url':url,
                                        'key':key
                                        }       
            else:
                api_data[api_name] = [DEFAULT_APIS[api_name]["url"],[DEFAULT_APIS[api_name]["key"]]]
        return api_data
    except (configparser.Error, FileNotFoundError) as e:
        return _create_default_config()

def api_init():
    """
    初始化API配置
    返回格式：{"api_name": [url, key], ...}
    """
    if not os.path.exists(API_CONFIG_FILE):
        return _create_default_config()
    return _read_existing_config()

#缩进图片
if not os.path.exists('background.jpg'):
    with open('background.jpg', 'wb') as f:
        f.write(think_img)
# 全局变量
temp_path = None
api = api_init()
user_input = ''
# 初始化聊天历史
pause_flag = False  # 暂停标志变量，默认为 False（未暂停）

#tps处理
class CharSpeedAnalyzer:
    def __init__(self):
        self.history = deque()  # 存储(time, char_count)的队列
        self.current_rate = 0.0
        self.peak_rate = 0.0     # 速率峰值（绝对值最大）

    def process_input(self, input_str):
        current_time = time.time()
        current_char_count = len(input_str)

        # 移除三秒前的旧数据
        cutoff_time = current_time - 3
        while self.history and self.history[0][0] < cutoff_time:
            self.history.popleft()

        # 添加新数据
        self.history.append((current_time, current_char_count))

        # 计算三秒窗口内的平均速率
        if len(self.history) >= 2:
            oldest = self.history[0]
            newest = self.history[-1]
            total_time = newest[0] - oldest[0]
            total_chars = newest[1] - oldest[1]
            self.current_rate = total_chars / total_time if total_time > 0 else 0.0
        else:
            self.current_rate = 0.0

        # 计算三秒窗口内的速率峰值（取绝对值）
        self.peak_rate = 0.0
        if len(self.history) >= 2:
            max_speed = 0.0
            for i in range(1, len(self.history)):
                prev = self.history[i-1]
                curr = self.history[i]
                delta_time = curr[0] - prev[0]
                
                if delta_time > 0:
                    speed = abs((curr[1] - prev[1]) / delta_time)
                    if speed > max_speed:
                        max_speed = speed
            self.peak_rate = max_speed

    def get_current_rate(self):
        return self.current_rate

    def get_peak_rate(self):
        return self.peak_rate

#强制降重
class RepeatProcessor:
    def __init__(self, main_class):
        self.main = main_class  # 持有主类的引用

    def find_last_repeats(self):
        """处理重复内容的核心方法"""
        # 还原之前的修改
        if self.main.difflib_modified_flag:
            self._restore_original_settings()
            self.main.difflib_modified_flag = False

        # 处理重复内容逻辑
        assistants = self._get_assistant_messages()
        clean_output = []
        
        if len(assistants) >= 4:
            last_four = assistants[-4:]
            has_high_similarity = self._check_similarity(last_four)
            
            if has_high_similarity:
                self._apply_similarity_settings()

            repeats = self._find_repeated_substrings(last_four)
            clean_output = self._clean_repeats(repeats)

        return clean_output

    def _restore_original_settings(self):
        """恢复原始配置"""
        self.main.max_message_rounds = self.main.original_max_message_rounds
        self.main.long_chat_placement = self.main.original_long_chat_placement
        self.main.long_chat_improve_var = self.main.original_long_chat_improve_var
        self.main.original_max_message_rounds = None
        self.main.original_long_chat_placement = None
        self.main.original_long_chat_improve_var = None

    def _get_assistant_messages(self):
        """获取助手消息"""
        return [msg['content'] for msg in self.main.chathistory if msg['role'] == 'assistant']

    def _check_similarity(self, last_four):
        """检查消息相似度"""
        similarity_threshold = 0.4
        has_high_similarity = False
        
        for i in range(len(last_four)):
            for j in range(i+1, len(last_four)):
                ratio = difflib.SequenceMatcher(None, last_four[i], last_four[j]).ratio()
                print(f'当前相似度 {ratio}')
                if ratio >= similarity_threshold:
                    print('过高相似度，激进降重触发')
                    return True
        return False

    def _apply_similarity_settings(self):
        """应用相似度过高时的配置"""
        if not self.main.difflib_modified_flag:
            self.main.original_max_message_rounds = self.main.max_message_rounds
            self.main.original_long_chat_placement = self.main.long_chat_placement
            self.main.original_long_chat_improve_var = self.main.long_chat_improve_var
            self.main.max_message_rounds = 3
            self.main.long_chat_placement = "对话第一位"
            self.main.difflib_modified_flag = True

    def _find_repeated_substrings(self, last_four):
        """查找重复子串"""
        repeats = set()
        for i in range(len(last_four)):
            for j in range(i + 1, len(last_four)):
                s_prev = last_four[i]
                s_current = last_four[j]
                self._add_repeats(s_prev, s_current, repeats)
        return sorted(repeats, key=lambda x: (-len(x), x))

    def _add_repeats(self, s1, s2, repeats):
        """添加发现的重复项"""
        len_s1 = len(s1)
        for idx in range(len_s1):
            max_len = len_s1 - idx
            for l in range(max_len, 0, -1):
                substr = s1[idx:idx+l]
                if substr in s2:
                    repeats.add(substr)
                    break

    def _clean_repeats(self, repeats):
        """清洗重复项结果"""
        symbol_to_remove = [',','.','"',"'",'，','。','！','？','...','——','：','~']
        clean_output = []
        repeats.reverse()
        
        for item1 in repeats:
            if self._is_unique_substring(item1, repeats) and len(item1) > 3:
                cleaned = self._remove_symbols(item1, symbol_to_remove)
                clean_output.append(cleaned)
        return clean_output

    def _is_unique_substring(self, item, repeats):
        """检查是否唯一子串"""
        return not any(item in item2 and item != item2 for item2 in repeats)

    def _remove_symbols(self, text, symbols):
        """移除指定符号"""
        for symbol in symbols:
            text = text.replace(symbol, '')
        return text

#随机分发模型请求
class Ui_random_model_selecter(object):
    def setupUi(self, random_model_selecter):
        random_model_selecter.setObjectName("random_model_selecter")
        random_model_selecter.resize(408, 305)
        self.gridLayout_5 = QGridLayout(random_model_selecter)
        self.gridLayout_5.setObjectName("gridLayout_5")
        self.groupBox = QGroupBox(random_model_selecter)
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groupBox.sizePolicy().hasHeightForWidth())
        self.groupBox.setSizePolicy(sizePolicy)
        self.groupBox.setObjectName("groupBox")
        self.gridLayout_4 = QGridLayout(self.groupBox)
        self.gridLayout_4.setObjectName("gridLayout_4")
        self.order_radio = QRadioButton(self.groupBox)
        self.order_radio.setChecked(True)
        self.order_radio.setObjectName("order_radio")
        self.gridLayout_4.addWidget(self.order_radio, 0, 0, 1, 1)
        self.random_radio = QRadioButton(self.groupBox)
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.random_radio.sizePolicy().hasHeightForWidth())
        self.random_radio.setSizePolicy(sizePolicy)
        self.random_radio.setObjectName("random_radio")
        self.gridLayout_4.addWidget(self.random_radio, 1, 0, 1, 1)
        self.gridLayout_5.addWidget(self.groupBox, 1, 0, 1, 1)
        self.groupBox_add_model = QGroupBox(random_model_selecter)
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groupBox_add_model.sizePolicy().hasHeightForWidth())
        self.groupBox_add_model.setSizePolicy(sizePolicy)
        self.groupBox_add_model.setObjectName("groupBox_add_model")
        self.gridLayout_2 = QGridLayout(self.groupBox_add_model)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.groupBox_model_config = QGroupBox(self.groupBox_add_model)
        self.groupBox_model_config.setObjectName("groupBox_model_config")
        self.gridLayout = QGridLayout(self.groupBox_model_config)
        self.gridLayout.setObjectName("gridLayout")
        self.model_name_label = QLabel(self.groupBox_model_config)
        self.model_name_label.setObjectName("model_name_label")
        self.gridLayout.addWidget(self.model_name_label, 2, 0, 1, 1)
        self.model_name = QComboBox(self.groupBox_model_config)
        self.model_name.setObjectName("model_name")
        self.gridLayout.addWidget(self.model_name, 3, 0, 1, 1)
        self.model_provider_label = QLabel(self.groupBox_model_config)
        self.model_provider_label.setObjectName("model_provider_label")
        self.gridLayout.addWidget(self.model_provider_label, 0, 0, 1, 1)
        self.model_provider = QComboBox(self.groupBox_model_config)
        self.model_provider.setObjectName("model_provider")
        self.gridLayout.addWidget(self.model_provider, 1, 0, 1, 1)
        self.gridLayout_2.addWidget(self.groupBox_model_config, 0, 0, 1, 1)
        self.add_model_to_list = QPushButton(self.groupBox_add_model)
        self.add_model_to_list.setObjectName("add_model_to_list")
        self.gridLayout_2.addWidget(self.add_model_to_list, 1, 0, 1, 1)
        self.gridLayout_5.addWidget(self.groupBox_add_model, 0, 0, 1, 1)
        self.label = QLabel(random_model_selecter)
        self.label.setText("")
        self.label.setObjectName("label")
        self.gridLayout_5.addWidget(self.label, 3, 1, 1, 1)
        self.confirm_button = QPushButton(random_model_selecter)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.confirm_button.sizePolicy().hasHeightForWidth())
        self.confirm_button.setSizePolicy(sizePolicy)
        self.confirm_button.setObjectName("confirm_button")
        self.gridLayout_5.addWidget(self.confirm_button, 3, 2, 1, 1)
        self.groupBox_view_model = QGroupBox(random_model_selecter)
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(2)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.groupBox_view_model.sizePolicy().hasHeightForWidth())
        self.groupBox_view_model.setSizePolicy(sizePolicy)
        self.groupBox_view_model.setObjectName("groupBox_view_model")
        self.gridLayout_3 = QGridLayout(self.groupBox_view_model)
        self.gridLayout_3.setObjectName("gridLayout_3")
        self.random_model_list_viewer = QListView(self.groupBox_view_model)
        self.random_model_list_viewer.setObjectName("random_model_list_viewer")
        self.gridLayout_3.addWidget(self.random_model_list_viewer, 0, 0, 1, 1)
        self.remove_model = QPushButton(self.groupBox_view_model)
        self.remove_model.setObjectName("remove_model")
        self.gridLayout_3.addWidget(self.remove_model, 1, 0, 1, 1)
        self.gridLayout_5.addWidget(self.groupBox_view_model, 0, 1, 2, 2)

        self.retranslateUi(random_model_selecter)
        QMetaObject.connectSlotsByName(random_model_selecter)

    def retranslateUi(self, random_model_selecter):
        _translate = QCoreApplication.translate
        random_model_selecter.setWindowTitle(_translate("random_model_selecter", "设置轮换/随机模型"))
        self.groupBox.setTitle(_translate("random_model_selecter", "使用模型"))
        self.order_radio.setText(_translate("random_model_selecter", "顺序输出"))
        self.random_radio.setText(_translate("random_model_selecter", "随机选择"))
        self.groupBox_add_model.setTitle(_translate("random_model_selecter", "添加模型"))
        self.groupBox_model_config.setTitle(_translate("random_model_selecter", ""))
        self.model_name_label.setText(_translate("random_model_selecter", "名称"))
        self.model_provider_label.setText(_translate("random_model_selecter", "提供商"))
        self.add_model_to_list.setText(_translate("random_model_selecter", "添加"))
        self.confirm_button.setText(_translate("random_model_selecter", "完成"))
        self.groupBox_view_model.setTitle(_translate("random_model_selecter", "模型库-使用的模型将在其中选择"))
        self.remove_model.setText(_translate("random_model_selecter", "移除选中项"))

class RandomModelSelecter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_random_model_selecter()
        self.ui.setupUi(self)
        self.setGeometry(100, 100, 600, 350)
        # 初始化数据
        self.model_map = MODEL_MAP
        self.current_models = []  # 存储已添加的模型信息
        self.last_check=0
        
        # 初始化UI组件
        self.init_providers()
        self.init_connections()
        self.init_list_view()
        
        # 初始更新模型列表
        self.update_model_names()

    def init_providers(self):
        """初始化模型提供商下拉框"""
        self.ui.model_provider.addItems(self.model_map.keys())

    def init_connections(self):
        """建立信号槽连接"""
        # 提供商变化时更新模型名称
        self.ui.model_provider.currentTextChanged.connect(self.update_model_names)
        # 添加模型按钮
        self.ui.add_model_to_list.clicked.connect(self.add_model_to_list)
        # 移除模型按钮
        self.ui.remove_model.clicked.connect(self.remove_selected_model)
        # 确认按钮
        self.ui.confirm_button.clicked.connect(self.hide)

    def init_list_view(self):
        """初始化列表视图模型"""
        self.list_model = QStandardItemModel()
        self.ui.random_model_list_viewer.setModel(self.list_model)
        self.ui.random_model_list_viewer.setSelectionMode(QListView.SingleSelection)

    def update_model_names(self):
        """更新模型名称下拉框"""
        current_provider = self.ui.model_provider.currentText()
        models = self.model_map.get(current_provider, [])
        
        self.ui.model_name.clear()
        if models:
            self.ui.model_name.addItems(models)
            self.ui.model_name.setCurrentIndex(0)

    def add_model_to_list(self):
        """添加当前选择的模型到列表"""
        self.last_check=0
        provider = self.ui.model_provider.currentText()
        model_name = self.ui.model_name.currentText()
        
        # 防止重复添加
        if (provider, model_name) in self.current_models:
            QMessageBox.warning(self, "警告", "该模型已存在于列表中！")
            return
        
        # 创建列表项
        item_text = f"{provider} - {model_name}"
        item = QStandardItem(item_text)
        item.setData({"provider": provider, "model": model_name})
        
        self.list_model.appendRow(item)
        self.current_models.append((provider, model_name))

    def remove_selected_model(self):
        """移除选中的模型"""
        selected = self.ui.random_model_list_viewer.selectedIndexes()
        if not selected:
            return
        
        for index in selected:
            row = index.row()
            # 从数据存储中移除
            del self.current_models[row]
            # 从列表模型中移除
            self.list_model.removeRow(row)

    def collect_selected_models(self):
        """收集最终选择的模型信息"""
        # 结果已实时存储在self.current_models中
        if self.ui.order_radio.isChecked():
            self.last_check+=1
            return_model= self.current_models[self.last_check%len(self.current_models)]

        else:
            return_model=random.choice(self.current_models)
        print("Selected models:", return_model)
        return return_model

    def get_selected_models(self):
        """获取最终选择的模型列表"""
        return self.current_models

#配置管理器
class ConfigManager:
    @staticmethod
    def init_settings(obj, filename='chatapi.ini', exclude=None):
        """
        初始化对象属性 from INI文件
        :param obj: 需要初始化属性的对象实例
        :param filename: 配置文件路径
        :param exclude: 需要排除的属性名列表（不导入这些属性）
        """
        config = configparser.ConfigParser()
        exclude_set = set(exclude) if exclude is not None else set()

        if os.path.exists(filename):
            try:
                config.read(filename)
            except:
                config.read(filename,encoding='utf=8')
            for section in config.sections():
                for option in config[section]:
                    if option in exclude_set:  # 跳过被排除的属性
                        continue
                    try:
                        value = config.getboolean(section, option)
                    except ValueError:
                        try:
                            value = config.getfloat(section, option)
                            try:
                                if int(value) == value:
                                    value = int(value)
                            except:
                                pass
                        except ValueError:
                            value = config.get(section, option)
                    setattr(obj, option, value)

    @staticmethod
    def config_save(obj, filename='chatapi.ini', section="others"):
        """
        保存对象属性到INI文件
        :param obj: 需要保存属性的对象实例
        :param filename: 配置文件路径
        :param section: 配置项分组名称
        """
        config = configparser.ConfigParser()
        config[section] = {}

        for key, value in vars(obj).items():
            if key.startswith("_"):
                continue
            try:
                if isinstance(value, bool):
                    config[section][key] = "true" if value else "false"
                elif isinstance(value, (int, float, str)):
                    config[section][key] = str(value)
            except Exception as e:
                print(f"Error saving {key}: {e}")

        with open(filename, "w", encoding="utf-8") as f:
            config.write(f)

#字符串处理工具
class StrTools:

    def _for_replace(text, replace_from, replace_to):
        """批量替换字符串，处理长度不匹配的情况"""
        replace_from_list = replace_from.split(';')
        replace_to_list = replace_to.split(';')
        
        # 调整 replace_to_list 的长度以匹配 replace_from_list
        replace_from_len = len(replace_from_list)
        # 截取 replace_to_list 的前 replace_from_len 个元素，不足部分补空字符串
        adjusted_replace_to = replace_to_list[:replace_from_len]  # 截断或保留全部
        # 补足空字符串直到长度等于 replace_from_len
        adjusted_replace_to += [''] * (replace_from_len - len(adjusted_replace_to))
        
        # 执行替换
        for i in range(replace_from_len):
            text = text.replace(replace_from_list[i], adjusted_replace_to[i])
        return text
    
    def _re_replace(text, replace_from, replace_to):
        """
        使用正则表达式替换文本中的内容。
        
        参数:
        - text: 原始字符串
        - replace_from: 由分号(";")分隔的正则表达式字符串
        - replace_to: 由分号(";")分隔的替换字符串
        
        返回:
        - 替换后的字符串
        """
        # 将 replace_from 和 replace_to 按分号分割成列表
        replace_from_list = replace_from.split(';')
        replace_to_list = replace_to.split(';')
        
        # 遍历 replace_from_list，根据规则替换
        for i, pattern in enumerate(replace_from_list):
            # 获取对应的替换字符串，如果 replace_to_list 长度不足，则使用空字符串
            replacement = replace_to_list[i] if i < len(replace_to_list) else ''
            # 使用 re.sub 进行替换
            text = re.sub(pattern, replacement, text)
        
        return text


    @staticmethod
    def vast_replace(text, replace_from, replace_to):
        """
        批量替换字符串，支持正则表达式和普通字符串替换。
        - text: 原始字符串,如果以 're:' 开头，则使用正则表达式替换
        - replace_from: 由分号(";")分隔的替换源字符串
        - replace_to: 由分号(";")分隔的替换目标字符串

        - 返回: 替换后的字符串
        """
        if replace_from.startswith('re:#'):
            # 如果以 're:#' 开头，则使用正则表达式替换
            text = StrTools._re_replace(text, replace_from[4:], replace_to)
        else:
            # 否则使用普通字符串替换
            text = StrTools._for_replace(text, replace_from, replace_to)
        
        return text
    
    @staticmethod
    def special_block_handler(obj,content,                      #incoming content
                                  signal,                       #function to call
                                  request_id,
                                  starter='<think>', 
                                  ender='</think>',
                                  extra_params=None,             #extra params to fullfil
                                  ):
        """处理自定义块内容"""
        if starter in content :
            content = content.split(starter)[1]
            if ender in content:
                return {"starter":True,"ender":True}
            if extra_params:
                if hasattr(obj, extra_params):
                    setattr(obj, extra_params, content)
            signal(request_id,content)
            return {"starter":True,"ender":False}
        return {"starter":False,"ender":False}

    @staticmethod
    def debug_chathistory(dic_chathistory,action='easy'):
        """调试聊天记录"""
        actual_length = 0

        for i, message in enumerate(dic_chathistory):
            if action!='easy':
                print(f"对话 {i}:")
                print(f"Role: {message['role']}")
                print("-" * 20)
                print(f"Content: {message['content']}")
                print("-" * 20)
            
                # 新增工具调用打印逻辑
                if message['role'] == 'assistant' and 'tool_calls' in message:
                    print("工具调用列表：")
                    for j, tool_call in enumerate(message['tool_calls']):
                        func_info = tool_call.get('function', {})
                        name = func_info.get('name', '未知工具')
                        args = func_info.get('arguments', {})
                        print(f"  工具 {j+1}: {name}")
                        print(f"  参数: {args}",type(args))
                        print("-" * 20)
                    actual_length += len(args)
                
                if message['content']:
                    actual_length += len(message['content'])
        
        print(f"实际长度: {actual_length}")
        print(f"实际对话轮数: {len(dic_chathistory)}")
        print(f"系统提示长度: {len(dic_chathistory[0]['content'])}")
        print("-" * 20)
        
        return {
            "actual_length": actual_length,
            "actual_rounds": len(dic_chathistory),
            "total_length": len(dic_chathistory),
            "system_prompt_length": len(dic_chathistory[0]['content'])
        }

    @staticmethod
    def remove_var(text):
        pattern = r'变量组开始.*?变量组结束'
        match = re.search(pattern, text, flags=re.DOTALL)
        if match:
            return text.replace(match.group(0),'')
        return text

    @staticmethod
    def combined_remove_var_vast_replace(obj,content=None):
        if content:
            actual_response=content
        else:
            actual_response = obj.full_response
        if obj.autoreplace_var:
            actual_response = StrTools.vast_replace(actual_response,obj.autoreplace_from,obj.autoreplace_to)
        if obj.mod_configer.status_monitor_enable_box.isChecked():
            actual_response = StrTools.remove_var(actual_response)
        return actual_response

#发送消息前处理器
class MessagePreprocessor:
    def __init__(self, god_class):
        self.god = god_class  # 保存对原类的引用
        self.stream=True

    def prepare_message(self,tools=False):
        """预处理消息并构建API参数"""
        start=time.perf_counter()
        better_round = self._calculate_better_round()
        better_message = self._handle_system_messages(better_round)
        message = self._fix_chat_history(better_message)
        message = self._handle_web_search_results(message)
        message = self._process_special_styles(message)
        message = self._handle_long_chat_placement(message)
        message = self._handle_user_and_char(message)
        message = self._handle_mod_functions(message)
        message = self._purge_message(message)
        params = self._build_request_params(message,stream=self.stream,tools=tools)
        print(f'发送长度: {len(str(message))}')
        print(f'处理时间:{(time.perf_counter()-start)*1000:.2f}ms')
        return message, params

    def _calculate_better_round(self):
        """计算合适的消息轮数"""
        history = self.god.chathistory
        if (len(str(history[-(self._fix_max_rounds()-1):])) - len(str(history[0]))) < 1000:
            return self._fix_max_rounds(False, 2*self._fix_max_rounds())
        return self._fix_max_rounds() - 1

    def _fix_max_rounds(self, max_round_bool=True, max_round=None):
        if max_round_bool:
            return min(self.god.max_message_rounds,len(self.god.chathistory))
        else:
            return min(max_round,len(self.god.chathistory))

    def _handle_system_messages(self, better_round):
        """处理系统消息"""
        history = self.god.chathistory
        if history[-(better_round-1):][0]["role"] == "system":
            better_round += 1
        return [history[0]] + history[-(better_round-1):]

    def _purge_message(self,messages):
        new_message=[]
        not_needed=['info','reasoning_content']
        for item in messages:
            temp_dict={}
            for key,value in item.items():
                if not key in not_needed:
                    temp_dict[key]=value
            new_message+=[temp_dict]
        return new_message

    def _process_special_styles(self, better_message):
        """处理特殊样式文本"""
        if (self.god.chathistory[-1]["role"] == "user" and self.god.temp_style != '') \
            or self.god.enforce_lower_repeat_text != '':
            message = [copy.deepcopy(msg) for msg in better_message]
            append_text = f'【{self.god.temp_style}{self.god.enforce_lower_repeat_text}】'
            message[-1]["content"] = append_text + message[-1]["content"]
        else:
            message = better_message
        return message

    def _handle_web_search_results(self, message):
        """处理网络搜索结果"""
        if self.god.web_search_enabled:
            self.god.web_searcher.wait_for_search_completion()
            message = [copy.deepcopy(msg) for msg in message]
            if self.god.web_searcher.rag_checkbox.isChecked():
                results = self.god.web_searcher.rag_result
            else:
                results = self.god.web_searcher.tool.format_results()
            message[-1]["content"] += "\n[system]搜索引擎提供的结果:\n" + results
        return message
   
    def _fix_chat_history(self, message):
        """
        修复被截断的聊天记录，保证工具调用的完整性
        """
        # 仅当第二条消息不是用户时触发修复（第一条是system）
        if len(message) > 1 and message[1]['role'] != 'user':  
            full_history = self.god.chathistory
            current_length = len(message)
            cutten_len = len(full_history) - current_length
            
            if cutten_len > 0:
                # 反向遍历缺失的消息
                for item in reversed(full_history[:cutten_len+1]):
                    if item['role'] != 'user':
                        message.insert(1, item)
                    if item['role'] == 'user':
                        message.insert(1, item)
                        break
        return message

    def _clean_consecutive_messages(self, message):
        """清理连续的同角色消息"""
        cleaned = []
        for msg in message:
            if cleaned and msg['role'] == cleaned[-1]['role']:
                cleaned[-1]['content'] += "\n" + msg['content']
            else:
                cleaned.append(msg)
        return cleaned

    def _handle_long_chat_placement(self, message):
        """处理长对话位置"""
        if self.god.long_chat_placement == "对话第一位":
            if len(message) >= 2 and "**已发生事件和当前人物形象**" in message[0]["content"]:
                try:
                    header, history_part = message[0]["content"].split(
                        "**已发生事件和当前人物形象**", 1)
                    message = [copy.deepcopy(msg) for msg in message]
                    message[0]["content"] = header.strip()
                    if history_part.strip():
                        message[1]["content"] = f"{message[1]['content']}\n{history_part.strip()}"
                except ValueError:
                    pass
        return message

    def _handle_user_and_char(self,message):
        message_copy = [dict(item) for item in message]
        for item in message_copy:
            if '{{user}}' in item['content']:
                item['content']=item['content'].replace('{{user}}',self.god.name_user)
            if '{{char}}' in item["content"]:
                item['content']=item['content'].replace('{{char}}',self.god.name_ai)
        return message_copy

    def _handle_mod_functions(self,message):
        message=self._handle_status_manager(message)
        message=self._handle_story_creator(message)
        return message
    
    #mod functions
    def _handle_status_manager(self, message):
        if not "mods.status_monitor" in sys.modules:
            return message
        if not self.god.mod_configer.status_monitor_enable_box.isChecked():
            return message
        
        message_copy = [dict(item) for item in message]
        
        text = message_copy[-1]['content']
        status_text = self.god.mod_configer.status_monitor.get_simplified_variables()
        use_ai_func = self.god.mod_configer.status_monitor.get_ai_variables(use_str=True)
        text = status_text + use_ai_func + text
        message_copy[-1]['content'] = text
        return message_copy
    
    def _handle_story_creator(self,message):
        if not "mods.story_creator" in sys.modules:
            print('no mods.story_creator')
            return message
        if not self.god.mod_configer.enable_story_insert.isChecked():
            return message
        message_copy=self.god.mod_configer.story_creator.process_income_chat_history(message)
        return message_copy

    def _build_request_params(self, message, stream=True,tools=False):
        """构建请求参数（含Function Call支持）"""
        params = {
            'model': self.god.model_combobox.currentText(),
            'messages': message,
            'stream': stream
        }
        
        # 添加现有参数
        if self.god.top_p_enable:
            params['top_p'] = float(self.god.top_p)
        if self.god.temperature_enable:
            params['temperature'] = float(self.god.temperature)
        if self.god.presence_penalty_enable:
            params['presence_penalty'] = float(self.god.presence_penalty)
        
        if hasattr(self.god, 'function_chooser') and self.god.function_chooser:
            selected_names = self.god.function_chooser.get_selected_functions()
        
        if selected_names :#and not tools:
            function_definitions = []
            manager = self.god.function_chooser.function_manager
            
            for func_name in selected_names:
                func_info = manager.get_function(func_name)
                if not func_info:  # 如果函数不存在，跳过
                    continue
                
                # 确保必要的字段存在，否则提供默认值
                function_definitions.append({
                    "type": "function",
                    "function": {
                    'name': func_name,
                    'description': func_info.get('description', 'No description provided'),
                    'parameters': func_info.get('parameters', {})  # 默认空字典
                }})
            
            if function_definitions:
                params['tools'] = function_definitions
        print(params)
        return params

#mod管理器
class ModConfiger(QTabWidget):
    def __init__(self):
        self.init_ui()
    
    def init_ui(self):
        super().__init__()
        self.setWindowTitle("Mod Configer")

        screen_geometry = QApplication.primaryScreen().availableGeometry()
        
        width = int(screen_geometry.width() * 0.6)
        height = int(screen_geometry.height() * 0.6)
        
        left = (screen_geometry.width() - width) //4
        top = (screen_geometry.height() - height) // 4
        
        self.setGeometry(left, top, width, height)
        # Create tabs
        self.addtabs()

    def addtabs(self):
        self.add_status_monitor()
        self.add_tts_server()
        self.add_story_creator()

    def handle_new_message(self,message,chathistory):
        self.status_monitor_handle_new_message(message)

    def add_status_monitor(self):
        self.status_monitor_manager = QWidget()
        status_monitor_layout = QGridLayout()
        self.status_monitor_manager.setLayout(status_monitor_layout)
        self.addTab(self.status_monitor_manager, "角色扮演状态栏")

        self.status_monitor_enable_box=QCheckBox("启用挂载")
        status_monitor_layout.addWidget(self.status_monitor_enable_box, 2, 0, 1, 1)
        self.status_monitor_enable_box.setToolTip("模块可以使用")
        if not "mods.status_monitor" in sys.modules:
            self.status_monitor_enable_box.setText('未安装')
            self.status_monitor_enable_box.setEnabled(False)
            self.status_monitor_enable_box.setToolTip("模块未安装")
            return
        
        self.status_monitor = StatusMonitorWindow()

        self.status_label = QLabel("角色扮演状态栏")
        status_monitor_layout.addWidget(self.status_label, 0, 0, 1, 1)
        self.status_label_info = QLabel("AI状态栏是一个mod，用于给AI提供状态信息，可以引导AI的行为。\n需要模型有较强的理解能力。\n预计启用后token使用量增加≈30-50")
        status_monitor_layout.addWidget(self.status_label_info, 1, 0, 1, 2)
        self.status_label_info.setWordWrap(True)
        self.start_status_monitor_button = QPushButton("启动状态栏")
        self.start_status_monitor_button.clicked.connect(lambda : self.status_monitor.show())
        status_monitor_layout.addWidget(self.start_status_monitor_button, 2, 1, 1, 1)
        #挂载MOD设置
        status_monitor_layout.addWidget(StatusMonitorInstruction.mod_configer())

        status_monitor_layout.setRowStretch(0,0)
        status_monitor_layout.setRowStretch(1,0)
        status_monitor_layout.setRowStretch(2,0)
        status_monitor_layout.setRowStretch(3,1)

    def add_story_creator(self):
        self.story_creator_manager=QWidget()
        self.creator_manager_layout=QGridLayout()
        self.story_creator_manager.setLayout(self.creator_manager_layout)
        self.addTab(self.story_creator_manager, "主线创建器")
        if not "mods.story_creator" in sys.modules:
            self.creator_manager_layout.addWidget(QLabel("主线生成器模块未挂载"),0,0,1,1)
            return
        self.enable_story_insert=QCheckBox("启用主线剧情挂载")
        self.creator_manager_layout.addWidget(self.enable_story_insert,0,0,1,1)
        self.main_story_creator_placeholder=GradientLabel('正在等待模型库更新...')
        self.creator_manager_layout.addWidget(self.main_story_creator_placeholder,1,0,1,1)
        
    def finish_story_creator_init(self):
        self.main_story_creator_placeholder.hide()
        StoryCreatorGlobalVar.DEFAULT_APIS=DEFAULT_APIS
        StoryCreatorGlobalVar.MODEL_MAP=MODEL_MAP
        self.story_creator=MainStoryCreaterInstruction.mod_configer()
        self.creator_manager_layout.addWidget(self.story_creator,1,0,1,1)

    def status_monitor_handle_new_message(self,message):
        if type(message)==dict:
            message=message[-1]["content"]
        if not "mods.status_monitor" in sys.modules:
            return
        if self.status_monitor.get_ai_variables()!={}:
            self.status_monitor.update_ai_variables(message)
        self.status_monitor.perform_cycle_step()
            
    def add_tts_server(self):
        if not "mods.chatapi_tts" in sys.modules:
            return
        self.tts_server = QWidget()
        self.addTab(self.tts_server,'语音识别')
        return

    def run_close_event(self):
        if "mods.story_creator" in sys.modules and hasattr(self,"story_creator"):
            self.story_creator.save_settings('utils')

#主类
class MainWindow(QMainWindow):
    update_response_signal = pyqtSignal(int,str)
    ai_response_signal= pyqtSignal(int,str)
    think_response_signal= pyqtSignal(int,str)
    back_animation_finished = pyqtSignal()
    update_background_signal= pyqtSignal(str)

    def setupUi(self):
        self.theme_selector = ThemeSelector()
        self.theme_selector.apply_saved_theme(init_path=None)

    def __init__(self):
        super().__init__()
        self.setupUi()
        self.setWindowTitle("早上好！夜之城！")
        self.setWindowIcon(self.render_svg_to_icon(MAIN_ICON))
        self.tokenpers=CharSpeedAnalyzer()
        self.repeat_processor=RepeatProcessor(self)
        self.ordered_model=RandomModelSelecter()

        screen_geometry = QApplication.primaryScreen().availableGeometry()
        
        width = int(screen_geometry.width() * 0.8)
        height = int(screen_geometry.height() * 0.8)
        
        left = (screen_geometry.width() - width) // 2
        top = (screen_geometry.height() - height) // 2
        
        self.setGeometry(left, top, width, height)
        self.api=api_init()
        
        # 初始化参数
        self.init_self_params()

        #初始化响应管理器
        self.init_response_manager()

        #function call
        self.init_function_call()

        self.init_concurrenter()

        #从存档载入设置并覆盖
        ConfigManager.init_settings(self, exclude=['application_path','temp_style','full_response','think_response'])

        # 创建主布局
        self.main_layout = QGridLayout()
        central_widget = QFrame()
        central_widget.setLayout(self.main_layout)
        self.setCentralWidget(central_widget)

        #背景
        self.init_back_ground_label(self.background_image_path)

        model_label = QLabel("选择模型:")
        self.model_combobox = QComboBox()
        self.model_combobox.addItems(MODEL_MAP.keys())
        self.model_combobox.setCurrentIndex(0)  # 默认值

        api_label = QLabel("API 提供商:")
        self.api_var = QComboBox()
        self.api_var.addItems(MODEL_MAP.keys())
        self.api_var.currentTextChanged.connect(self.update_model_combobox)
        self.api_var.setCurrentText(next(iter(api.keys())))
        initial_api = self.api_var.currentText()
        self.update_model_combobox(initial_api)

        #轮换模型
        self.use_muti_model=QCheckBox("使用轮换模型")
        self.use_muti_model.toggled.connect(lambda checked: (
            self.ordered_model.show() if checked else self.ordered_model.hide(),
            self.api_var.setEnabled(not checked),
            self.model_combobox.setEnabled(not checked)
        ))
        self.use_muti_model.setToolTip("用于TPM合并扩增/AI回复去重")

        #汇流优化
        self.use_concurrent_model=QCheckBox("使用汇流优化")
        self.use_concurrent_model.setToolTip("用于提高生成质量\n注意！！极高token消耗量！！")
        self.use_concurrent_model.toggled.connect(lambda checked: self.show_concurrent_model(show=checked))

        #两模式互斥
        self.use_muti_model.toggled.connect(lambda c: self.use_concurrent_model.setChecked(False) if c else None)
        self.use_concurrent_model.toggled.connect(lambda c: self.use_muti_model.setChecked(False) if c else None)


        #优化功能触发进度
        self.opti_frame=QGroupBox("触发优化")
        self.opti_frame_layout = QGridLayout()
        self.opti_frame.setLayout(self.opti_frame_layout)
        self.Background_trigger_bar = QProgressBar(self)
        self.opti_frame_layout.addWidget(self.Background_trigger_bar,0,0,1,7)
 
        self.chat_opti_trigger_bar = QProgressBar(self)
        self.opti_frame_layout.addWidget(self.chat_opti_trigger_bar,1,0,1,7)

        self.cancel_trigger_background_update=QPushButton("×")
        self.cancel_trigger_background_update.clicked.connect(
            lambda: (setattr(
                self, 'new_background_rounds', 0), 
                self.update_opti_bar())
                )

        self.cancel_trigger_chat_opti=QPushButton("×")
        self.cancel_trigger_chat_opti.clicked.connect(
            lambda: (
                setattr(self, 'new_chat_rounds', 0), 
                self.update_opti_bar())
                )

        self.opti_frame_layout.addWidget(self.cancel_trigger_background_update, 0,  8,  1,  1)
        self.opti_frame_layout.addWidget(self.cancel_trigger_chat_opti,         1,  8,  1,  1)
        self.opti_frame.hide()

        self.stat_tab_widget = QTabWidget()
        self.stat_tab_widget.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Minimum)
        api_page = QWidget()
        api_page_layout = QGridLayout(api_page)

        api_page_layout.addWidget(api_label                 ,0,0,1,1)
        api_page_layout.addWidget(self.api_var              ,0,1,1,1)
        api_page_layout.addWidget(model_label               ,1,0,1,1)
        api_page_layout.addWidget(self.model_combobox       ,1,1,1,1)
        api_page_layout.addWidget(self.use_muti_model       ,2,0,1,1)
        api_page_layout.addWidget(self.use_concurrent_model ,2,1,1,1)

        opti_page = QWidget()
        opti_page_layout = QVBoxLayout(opti_page)
        opti_page_layout.addWidget(self.opti_frame)
        self.stat_tab_widget.addTab(api_page, "模型选择")
        self.stat_tab_widget.addTab(opti_page, "优化监控")

        #tts页面初始化
        self.add_tts_page()
        self.init_mod_configer_page()



        # 用户输入文本框
        user_input_label = QLabel("用户输入：")
        temp_style_edit = QLineEdit()
        # 临时风格
        temp_style_edit.setPlaceholderText("指定临时风格")
        temp_style_edit.textChanged.connect(lambda text: setattr(self, 'temp_style', text or ''))

        self.user_input_text = QTextEdit()
        self.main_layout.addWidget(temp_style_edit,2,1,1,1)
        self.main_layout.addWidget(user_input_label, 2, 0, 1, 1)
        self.main_layout.addWidget(self.user_input_text, 3, 0, 1, 2)

        self.init_chat_history_bubbles()

        # AI 回复文本框
        ai_response_label = QLabel("AI 回复：")
        self.ai_response_text = ChatapiTextBrowser()
        self.ai_response_text.anchorClicked.connect(lambda url: os.startfile(url.toString()))
        self.ai_response_text.setOpenExternalLinks(False)

        #强制去重
        self.enforce_lower_repeat=QCheckBox("强制去重")
        self.enforce_lower_repeat.setChecked(self.enforce_lower_repeat_var)
        self.enforce_lower_repeat.stateChanged.connect(
            lambda state: setattr(self, 'enforce_lower_repeat_var', bool(state))
        )

        self.main_layout.addWidget(ai_response_label, 5, 0, 1, 1)
        self.main_layout.addWidget(self.enforce_lower_repeat, 5, 1, 1, 1)
        self.main_layout.addWidget(self.ai_response_text, 6, 0, 1, 2)
        
        control_frame = QGroupBox("控制")  # 直接在构造函数中设置标题
        # 发送按钮
        self.send_button = QPushButton("发送 Ctrl+Enter")
        self.send_button.clicked.connect(self.send_message)

        self.control_frame_layout = QGridLayout()
        control_frame.setLayout(self.control_frame_layout)

        self.pause_button = QPushButton("暂停")
        self.pause_button.clicked.connect(lambda: 
                                          (setattr(self, 'pause_flag', not self.pause_flag), 
                                            self.send_button.setEnabled(True))[1]
                                        )
        self.pause_button.clicked.connect(lambda _:self.chat_history_bubbles.streaming_scroll(False))


        self.clear_button = QPushButton("清空")
        self.clear_button.clicked.connect(self.clear_history)

        self.resend_button= QPushButton("重新回答")
        self.resend_button.clicked.connect(self.resend_message_last)

        self.edit_question_button=QPushButton("修改问题")
        self.edit_question_button.clicked.connect(self.edit_user_last_question)

        self.edit_message_button=QPushButton("原始记录")
        self.edit_message_button.clicked.connect(self.edit_chathistory)

        self.web_search_button=SearchButton("启用联网搜索")
        self.web_search_button.setChecked(self.web_search_enabled)
        self.web_search_button.toggled.connect(self.handel_web_search_button_toggled)

        separators = [QFrame() for _ in range(3)]
        for sep in separators:
            sep.setFrameShape(QFrame.VLine)
            sep.setFrameShadow(QFrame.Sunken)
        self.control_frame_layout.addWidget(self.send_button,           0, 0,  1, 14)
        self.control_frame_layout.addWidget(self.pause_button,          1, 0,  2, 2)
        self.control_frame_layout.addWidget(self.clear_button,          1, 2,  2, 2)
        self.control_frame_layout.addWidget(separators[0],              1, 4,  2, 1)
        self.control_frame_layout.addWidget(self.resend_button,         1, 5,  2, 2)
        self.control_frame_layout.addWidget(separators[1],              1, 7,  2, 1)
        self.control_frame_layout.addWidget(self.edit_question_button,  1, 8,  2, 2)
        self.control_frame_layout.addWidget(self.edit_message_button,   1, 10, 2, 2)
        self.control_frame_layout.addWidget(separators[2],              1, 12, 2, 1)
        self.control_frame_layout.addWidget(self.web_search_button,     1, 13, 2, 1)

        self.main_layout.addWidget(control_frame, 4, 0, 1, 2)
    
        #AI回复左上角控件组
        
        sub_height=int(self.height()*0.04)
        total_height=int(sub_height*2.25)
        sub_width=int(self.height()*0.04)
        total_width=int(sub_width*1.5)
        margin=int(sub_height*0.1)

        ai_control_widget=QFrame()
        #ai_control_widget.setFixedSize(total_width,total_height)
        ai_control_layout=QGridLayout()
        ai_control_layout.setContentsMargins(margin,margin,margin,margin)
        ai_control_widget.setLayout(ai_control_layout)
        #思考内容角标
        think_info_pixmap = QPixmap()
        think_info_pixmap.loadFromData(self.think_img)

        self.think_info=QPushButton()
        self.think_info.clicked.connect(self.extend_think_text_box)
        self.think_info.setIcon(QIcon(think_info_pixmap))
        self.think_info.setFixedSize(sub_width,sub_height)
        self.think_info.setIconSize(self.think_info.size()*0.8)

        open_image_icon=QPixmap()
        open_image_icon.loadFromData(image_icon)
        self.open_image_button=QPushButton()
        self.open_image_button.setIcon(QIcon(open_image_icon))
        self.open_image_button.setFixedSize(sub_width,sub_height)
        self.open_image_button.setIconSize(open_image_icon.size()*0.12)
        self.open_image_button.setToolTip('打开背景图')
        self.open_image_button.clicked.connect(self.open_background_pic)

        ai_control_layout.addWidget(self.think_info,0,0,1,1)
        ai_control_layout.addWidget(self.open_image_button,1,0,1,1)

        self.main_layout.addWidget(ai_control_widget, 6, 1, 1, 1,Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)


        #思考内容文本框
        self.think_text_box=QTextBrowser()
        self.ai_think_label=QLabel("AI思考链")
        
        self.think_text_box.hide()
        
        self.search_result_button=SwitchButton(texta='搜索结果 ',textb=' 搜索结果')
        self.search_result_label=QLabel("搜索结果")
        self.search_result_button.hide()
        self.search_result_button.clicked.connect(self.handle_search_result_button_toggle)
        self.main_layout.addWidget(self.search_result_button,6,1,1,1,Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        #历史记录 显示框
        self.past_chat_frame = QGroupBox()
        self.past_chat_frame_layout = QGridLayout()
        self.past_chat_frame.setLayout(self.past_chat_frame_layout)

        self.past_chat_list = QListWidget()
        self.past_chat_list.setSelectionMode(QAbstractItemView.SingleSelection)  # 强制单选模式
        self.past_chat_list.itemClicked.connect(self.load_from_past)
        self.past_chat_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.past_chat_list.customContextMenuRequested.connect(self.past_chats_menu)
        
        self.reload_chat_list=QPushButton("🗘")
        self.reload_chat_list.clicked.connect(self.grab_past_chats)
        self.reload_chat_list.setToolTip("刷新（在打开本页面时会自动刷新)")
        self.reload_chat_list.setStyleSheet("""
    QPushButton {
        font-size: 18px;
        max-width: 20px;
        max-height: 20px;
        padding: 0px 0px;
    }
""")
        
        self.del_item_chat_list=QPushButton('🗑')
        self.del_item_chat_list.clicked.connect(self.delete_selected_history)
        self.del_item_chat_list.setToolTip("删除")
        self.del_item_chat_list.setStyleSheet("""
    QPushButton {
        font-size: 18px;
        max-width: 20px;
        max-height: 20px;
        padding: 0px 0px;
    }
""")

        self.load_stories_chat_list=QPushButton('📊')
        self.load_stories_chat_list.clicked.connect(self.analysis_past_chat)
        self.load_stories_chat_list.setToolTip("分析用量")
        self.load_stories_chat_list.setStyleSheet("""
    QPushButton {
        font-size: 18px;
        max-width: 20px;
        max-height: 20px;
        padding: 0px 0px;
    }
""")

        self.load_sys_pmt_chat_list=QPushButton('🌐')
        self.load_sys_pmt_chat_list.clicked.connect(self.load_sys_pmt_from_past_record)
        self.load_sys_pmt_chat_list.setToolTip("导入system prompt")
        self.load_sys_pmt_chat_list.setStyleSheet("""
    QPushButton {
        font-size: 18px;
        max-width: 20px;
        max-height: 20px;
        padding: 0px 0px;
    }
""")

        self.load_from_past_chat_list=QPushButton('✔')
        self.load_from_past_chat_list.clicked.connect(self.load_from_past)
        self.load_from_past_chat_list.setToolTip("载入")
        self.load_from_past_chat_list.setStyleSheet("""
    QPushButton {
        font-size: 18px;
        max-width: 20px;
        max-height: 20px;
        padding: 0px 0px;
    }
""")

        hislabel=QLabel("历史记录")
        hislabel.setMaximumHeight(20)

        #完整/极简切换
        self.hide_extra_items=SwitchButton(texta="完整    ",textb="    极简")
        self.hide_extra_items.clicked.connect(self.handle_hide_extra_items_toggle)

        self.past_chat_frame_layout.addWidget(self.stat_tab_widget,         0,0,1,5)
        self.past_chat_frame_layout.addWidget(hislabel,                     1,0,1,4)
        self.past_chat_frame_layout.addWidget(self.past_chat_list,          2,1,8,4)
        self.past_chat_frame_layout.addWidget(self.reload_chat_list,        2,0,1,1)
        self.past_chat_frame_layout.addWidget(self.load_from_past_chat_list,3,0,1,1)
        self.past_chat_frame_layout.addWidget(self.del_item_chat_list,      4,0,1,1)
        self.past_chat_frame_layout.addWidget(self.load_sys_pmt_chat_list,  5,0,1,1)
        self.past_chat_frame_layout.addWidget(self.load_stories_chat_list,  6,0,1,1)
        self.past_chat_frame_layout.addWidget(self.hide_extra_items,        10,1,1,1)
        self.past_chat_frame.setParent(self)
        self.past_chat_frame.hide()

        # 创建 TreeView
        self.tree_view = QTreeWidget()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.itemClicked.connect(self.on_tree_item_clicked)  # 点击事件
        self.tree_view.setGeometry(-int(self.width()*0.3), 0, int(self.width()*0.3), int(self.height()))
        self.tree_view.setParent(self)
        self.tree_view.hide()

        # 填充 TreeView
        self.populate_tree_view()

        # 设置行和列的权重
        self.main_layout.setRowStretch(0, 0)
        self.main_layout.setRowStretch(1, 0)
        self.main_layout.setRowStretch(3, 1)
        self.main_layout.setRowStretch(6, 1)
        self.main_layout.setRowStretch(2, 0)
        self.main_layout.setColumnStretch(0, 1)
        self.main_layout.setColumnStretch(1, 1)
        self.main_layout.setColumnStretch(2, 1)
        self.main_layout.setColumnStretch(3, 1)


        pixmap = QPixmap()
        pixmap.loadFromData(self.setting_img)
        self.toggle_tree_button = QPushButton()
        self.toggle_tree_button.clicked.connect(self.toggle_tree_view)
        self.toggle_tree_button.setGeometry(0, self.height() - int(self.height() * 0.06), int(self.height() * 0.06), int(self.height() * 0.06))
        self.toggle_tree_button.setParent(self)
        self.toggle_tree_button.raise_()  # 确保按钮在最上层
        self.toggle_tree_button.setIcon(QIcon(pixmap))
        self.toggle_tree_button.setIconSize(pixmap.size())
        self.toggle_tree_button.resizeEvent = self.on_button_resize
        self.toggle_tree_button.setStyleSheet(
            MainWindowPresetVars.toggle_tree_button_stylesheet
        )


        # 设置快捷键
        self.send_message_var = True
        self.autoslide_var = True
        self.send_message_var=True
        self.send_message_shortcut= QShortcut(QKeySequence(), self)
        self.shortcut1 = QShortcut(QKeySequence(), self)
        self.shortcut2 = QShortcut(QKeySequence(), self)
        self.hotkey_sysrule= QShortcut(QKeySequence(), self)
        self.shortcut1.activated.connect(self.toggle_tree_view)
        self.shortcut2.activated.connect(self.toggle_tree_view)
        self.send_message_shortcut.activated.connect(self.send_message)
        self.sysrule=self.init_sysrule()
        self.creat_new_chathistory()
        self.chathistory_detail=[]
        self.pause_flag = False
        self.update_response_signal.connect(self.receive_message)
        self.ai_response_signal.connect(self.update_ai_response_text)
        self.update_background_signal.connect(self.update_background)#可以弃用了
        self.think_response_signal.connect(self.update_think_response_text)
        self.thread_event = threading.Event()
        self.installEventFilter(self)
        self.read_hotkey_config()
        self.bind_enter_key()
        self.update_opti_bar()

        #UI状态恢复
        self.recover_ui_status()
        #UI创建后
        self.init_post_ui_creation()
        print(f'Chatapi Main window init finished, time cost:{time.time()-start_time_stamp:.2f}s')

    def init_self_params(self):
        self.setting_img = setting_img
        self.think_img = think_img
        self.application_path = application_path
        self.history_path=os.path.join(self.application_path,'history')
        self.temp_style=''
        self.enforce_lower_repeat_var=False
        self.enforce_lower_repeat_text=''
        self.novita_model='foddaxlPhotorealism_v45_122788.safetensors'
        self.web_searcher=WebSearchSettingWindows(MODEL_MAP,DEFAULT_APIS)

        # 状态控制标志
        self.stream_receive = True
        self.firstrun_do_not_load = True
        self.long_chat_improve_var = True
        self.enable_lci_system_prompt=True
        self.hotkey_sysrule_var = True
        self.back_ground_update_var = True
        self.lock_background=False
        self.web_search_enabled=False
        self.difflib_modified_flag = False

        # 聊天会话管理
        self.past_chats = {}
        self.max_message_rounds = 50
        self.new_chat_rounds = 0
        self.last_summary = ''
        self.full_response = ''
        self.saved_api_provider = ''
        self.saved_model_name = ''  

        # 长度限制设置
        self.max_total_length = 8000
        self.max_segment_length = 8000
        self.long_chat_hint=''
        self.long_chat_improve_api_provider=None
        self.long_chat_improve_model=None
        self.long_chat_placement=''

        # 背景处理相关
        self.max_backgound_lenth = 1000  
        self.new_background_rounds = 0
        self.max_background_rounds = 15
        self.background_style='现实'
        self.back_ground_summary_model='deepseek-reasoner'
        self.back_ground_summary_provider='deepseek'
        self.back_ground_image_provider='novita'
        self.back_ground_image_model='foddaxlPhotorealism_v45_122788.safetensors'#默认初始值
        self.background_image_path='background.jpg'

        #对话状态
        self.top_p_enable=True
        self.top_p=0.8
        self.temperature_enable=True
        self.temperature=0.7
        self.presence_penalty_enable=True
        self.presence_penalty=1

        # 文件路径
        self.returned_file_path = ''

        # API密钥
        self.novita_api_key=""

        #自动替换
        self.autoreplace_var = False
        self.autoreplace_from = ''
        self.autoreplace_to = ''

        #俩人名字
        self.name_user="用户"
        self.name_ai=""

        #俩人头像
        self.avatar_user=''#path to user avatar.jpg
        self.avatar_ai=''#path to ai avatar.jpg

        #对话储存点
        self.think_response=''
        self.full_response=''

        #TTS
        self.tts_enabled=False
        self.tts_provider='不使用TTS'

    def init_response_manager(self):
        # AI响应更新控制
        self.ai_last_update_time = 0
        self.ai_update_timer = QTimer()
        self.ai_update_timer.setSingleShot(True)

        # 思考过程更新控制
        self.think_last_update_time = 0
        self.think_update_timer = QTimer()
        self.think_update_timer.setSingleShot(True)

        self.last_chat_info={}

    def init_mod_configer_page(self):
        self.mod_configer=ModConfiger()

    def init_function_call(self):
        self.function_manager = FunctionManager()
        self.function_chooser = FunctionSelectorUI(self.function_manager)

    def init_post_ui_creation(self):
        self.mod_configer.finish_story_creator_init()
        pass
        #self.api_window = APIConfigWidget(application_path=self.application_path)
        #self.api_window.initializationCompleted.connect(self._handle_api_init)
        #self.api_window.configUpdated.connect(self._handle_api_init)
        
    def init_chat_history_bubbles(self):
        # 聊天历史文本框
        self.chat_history_label = QLabel("聊天历史")
        self.display_full_chat_history=QPushButton("完整记录")
        self.display_full_chat_history.clicked.connect(self.display_full_chat_history_window)
        self.chat_history_text = ChatapiTextBrowser()
        self.chat_history_text.anchorClicked.connect(lambda url: os.startfile(url.toString()))
        self.chat_history_text.setOpenExternalLinks(False)

        #0.25.1 更新
        #聊天历史气泡
        self.bubble_background=QTextBrowser()
        self.main_layout.addWidget(self.bubble_background, 3, 2, 4, 3)
        self.chat_history_bubbles = ChatHistoryWidget()
        self.main_layout.addWidget(self.chat_history_bubbles, 3, 2, 4, 3)
        self.main_layout.addWidget(self.display_full_chat_history, 2, 4, 1, 1)
        self.main_layout.addWidget(self.chat_history_label, 2, 2, 1, 1)

        #气泡信号绑定
        self.chat_history_bubbles.regenerateRequested.connect(self.resend_message)
        self.chat_history_bubbles.editFinished.connect(self.edit_chathistory_by_index)
        self.chat_history_bubbles.RequestAvatarChange.connect(self.show_avatar_window)
        
    def init_concurrenter(self):
        self.concurrent_model=ConvergenceDialogueOptiProcessor()
        self.concurrent_model.concurrentor_content.connect(self.concurrentor_content_receive)
        self.concurrent_model.concurrentor_reasoning.connect(self.concurrentor_reasoning_receive)
        self.concurrent_model.concurrentor_finish.connect(self.concurrentor_finish_receive)

    def init_sysrule(self):
        # 定义文件路径
        file_path = os.path.join(self.application_path,'utils','system_prompt_presets','当前对话.json')
        
        # 检查文件是否存在
        if os.path.exists(file_path):
            # 读取JSON文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 获取content字段的值
            self.sysrule = config_data["content"]
        else:
            # 创建目录（如果不存在）
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 创建默认配置数据
            default_content = "你是一个有用的AI助手"
            new_config = {
                "name": "当前对话",
                "content": default_content,
                "post_history": ""
            }
            
            # 写入新文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, ensure_ascii=False, indent=2)
            
            # 设置系统规则
            self.sysrule = default_content
        
        # 返回当前系统规则
        return self.sysrule

    def add_tts_page(self):
        if not "mods.chatapi_tts" in sys.modules:
            return
        self.tts_handler=TTSAgent(application_path=self.application_path)
        if hasattr(self,'tts_enabled'):
            self.tts_handler.tts_enabled=self.tts_enabled
        if hasattr(self,'tts_provider') and self.tts_provider!='不使用TTS':
            self.tts_handler.generator_selector.setCurrentText(self.tts_provider)
        self.tts_handler.tts_state.connect(
            lambda state,provider:setattr(self,'tts_enabled',state) or setattr(self,'tts_provider',provider)
            )
        self.stat_tab_widget.addTab(self.tts_handler, "语音生成")

    def show_mod_configer(self):
        self.mod_configer.show()

    def recover_ui_status(self):
        """
        恢复API提供商和模型选择的UI状态（如果有保存的值）。
        如果存在已保存的值，则设置对应下拉框的当前选项。
        同时连接下拉框的currentTextChanged信号，在用户更改选择时更新保存的值。
        """
        if hasattr(self, 'saved_api_provider'):
            index = self.api_var.findText(self.saved_api_provider)
            if index >= 0:
                self.api_var.setCurrentIndex(index)
        
        if hasattr(self, 'saved_model_name'):
            index = self.model_combobox.findText(self.saved_model_name)
            if index >= 0:
                self.model_combobox.setCurrentIndex(index)
        
        self.api_var.currentTextChanged.connect(lambda text: setattr(self, 'saved_api_provider', text))
        self.model_combobox.currentTextChanged.connect(lambda text: setattr(self, 'saved_model_name', text))

    #svg图标渲染器
    def render_svg_to_icon(self, svg_data):
        svg_byte_array = QByteArray(svg_data)
        svg_renderer = QSvgRenderer(svg_byte_array)
        
        icon = QIcon()
        # 常见图标尺寸列表
        sizes = [16, 24, 32, 48, 64, 96, 128]
        
        for size in sizes:
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            
            painter = QPainter(pixmap)
            svg_renderer.render(painter)
            painter.end()
            
            icon.addPixmap(pixmap)
        
        return icon

    #Ai思考框收起/打开
    def extend_think_text_box(self):
        if not self.think_text_box.isVisible():
            self.ai_think_label.setVisible(True)
            self.think_text_box.setVisible(True)
            if self.search_result_button.isChecked():
                self.main_layout.addWidget(self.web_searcher.search_results_widget,3, 2, 2, 1)
                self.main_layout.addWidget(self.ai_think_label, 5, 2, 1,1)
                self.main_layout.addWidget(self.think_text_box, 6, 2, 2,1)#,Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
            else:
                self.main_layout.addWidget(self.ai_think_label, 2, 2, 1,1)
                self.main_layout.addWidget(self.think_text_box, 3, 2, 4,1)
                self.main_layout.addWidget(self.chat_history_label, 2, 3, 1, 1)
                self.main_layout.addWidget(self.chat_history_bubbles, 3, 3, 4, 3)
            if self.hide_extra_items.isChecked() and(not self.search_result_button.isChecked()):
                self.main_layout.setColumnStretch(2, 2)
                WindowAnimator.animate_resize(self, QSize(self.width(),self.height()), QSize(int(self.width()*2),self.height()))
            self.think_text_box.repaint()
        else:
            self.think_text_box.hide()
            self.ai_think_label.hide()
            if not self.search_result_button.isChecked():
                self.main_layout.addWidget(self.chat_history_label, 2, 2, 1, 1)
                self.main_layout.addWidget(self.chat_history_bubbles, 3, 2, 4, 3)
            else:
                self.main_layout.addWidget(self.web_searcher.search_results_widget,3, 2, 4, 1)
            if self.hide_extra_items.isChecked() and(not self.search_result_button.isChecked()):
                self.main_layout.setColumnStretch(2, 0)
                WindowAnimator.animate_resize(self, QSize(self.width(),self.height()), QSize(int(self.width()/2),self.height()))

    #设置按钮：大小自适应
    def on_button_resize(self, event):
        # 获取按钮的当前大小
        super().resizeEvent(event)
        button_size = self.toggle_tree_button.size()
        # 设置图标大小为按钮大小
        self.toggle_tree_button.setIconSize(button_size*0.8)
        # 调用父类的 resizeEvent
        
        self.toggle_tree_button.setGeometry(
            0, self.height() - int(self.height() * 0.06), 
            int(self.height() * 0.06), int(self.height() * 0.06)
        )

    #设置按钮：自动贴边：重写窗口缩放
    def resizeEvent(self, event):
        super().resizeEvent(event)  # 调用父类的resizeEvent，确保正常处理窗口大小变化
        # 动态调整按钮位置和大小
        self.toggle_tree_button.setGeometry(
            0, self.height() - int(self.height() * 0.06), 
            int(self.height() * 0.06), int(self.height() * 0.06)
        )
        self.past_chat_frame.setGeometry(self.width()-self.past_chat_frame.width(), 0, int(self.width() * 0.3), int(self.height()))
        self.tree_view.setGeometry(0, 0, int(self.width() * 0.3), int(self.height()))
    def changeEvent(self, event):
        try:
            self.past_chat_frame.setGeometry(self.width()-self.past_chat_frame.width(), 0, int(self.width() * 0.3), int(self.height()))
            self.tree_view.setGeometry(0, 0, int(self.width() * 0.3), int(self.height()))
        except Exception as e:
            if not 'past_chat_frame' in str(e):
                print('changeEvent failed, Error code:',e)
        super().changeEvent(event)

    #设置界面：函数库
    def populate_tree_view(self):
        # 数据结构
        data = [
            {"上级名称": "系统", "按钮变量名": "self.api_import_button", "提示语": "API/模型库设置", "执行函数": "self.open_api_window"},
            {"上级名称": "系统", "按钮变量名": "self.system_prompt_button", "提示语": "System Prompt 设定 Ctrl+E", "执行函数": "self.open_system_prompt"},
            {"上级名称": "系统", "按钮变量名": "self.start_mod_configer", "提示语": "MOD管理器", "执行函数": "self.show_mod_configer"},
            {"上级名称": "记录", "按钮变量名": "self.save_button", "提示语": "保存记录", "执行函数": "self.save_chathistory"},
            {"上级名称": "记录", "按钮变量名": "self.load_button", "提示语": "导入记录", "执行函数": "self.load_chathistory"},
            {"上级名称": "记录", "按钮变量名": "self.edit_button", "提示语": "修改当前聊天", "执行函数": "self.edit_chathistory"},
            {"上级名称": "记录", "按钮变量名": "self.analysis_window_button", "提示语": "对话分析", "执行函数": "self.show_analysis_window"},
            {"上级名称": "对话", "按钮变量名": "self.chat_lenth", "提示语": "对话设置", "执行函数": "self.open_max_send_lenth_window"},
            {"上级名称": "对话", "按钮变量名": "self.enforce_chat_opti", "提示语": "强制触发长对话优化", "执行函数": "self.long_chat_improve"},
            {"上级名称": "对话", "按钮变量名": "self.trigger_function_call_window", "提示语": "函数调用", "执行函数": "self.show_function_call_window"},
            {"上级名称": "背景", "按钮变量名": "self.background_setting", "提示语": "背景设置", "执行函数": "self.background_settings_window"},
            {"上级名称": "背景", "按钮变量名": "self.setting_trigger_background_update", "提示语": "触发背景更新（跟随聊天）", "执行函数": "self.call_background_update"},
            {"上级名称": "背景", "按钮变量名": "self.customed_background_update", "提示语": "生成自定义背景（正在重构）", "执行函数": "self.show_pic_creater"},
            {"上级名称": "设置", "按钮变量名": "", "提示语": "主题", "执行函数": "self.show_theme_settings"},
            {"上级名称": "设置", "按钮变量名": "self.set_button", "提示语": "快捷键", "执行函数": "self.open_settings_window"},
            {"上级名称": "设置", "按钮变量名": "self.web_search_setting", "提示语": "联网搜索", "执行函数": "self.open_web_search_setting_window"}
        ]

        # 创建根节点
        parent_nodes = {}
        for item in data:
            parent_name = item["上级名称"]
            if parent_name not in parent_nodes:
                parent_item = QTreeWidgetItem([parent_name])
                self.tree_view.addTopLevelItem(parent_item)
                parent_nodes[parent_name] = parent_item

        # 创建子节点
        for item in data:
            parent_name = item["上级名称"]
            parent_item = parent_nodes[parent_name]
            child_item = QTreeWidgetItem([item["提示语"]])
            child_item.setData(0, Qt.UserRole, item["执行函数"])  # 将执行函数存储在用户数据中
            parent_item.addChild(child_item)
        self.tree_view.expandAll()

    #设置界面：响应点击
    def on_tree_item_clicked(self, item, column):
        # 获取用户数据（执行函数名）
        function_name = item.data(column, Qt.UserRole)
        if function_name:
            # 动态调用对应的函数
            func = getattr(self, function_name.split('.')[-1])
            if callable(func):
                func()

    #设置界面：展开/收起 带动画绑定
    def toggle_tree_view(self):
        # 切换 TreeView 的显示状态
        if self.tree_view.isHidden() :
            self.past_chat_frame.setGeometry(self.width(), 0, int(self.width() * 0.3), int(self.height()))
            self.past_chat_frame.show()
            self.past_chat_frame_animation = QPropertyAnimation(self.past_chat_frame, b"geometry")
            self.past_chat_frame_animation.setDuration(300)
            self.past_chat_frame_animation.setEasingCurve(QEasingCurve.InOutQuad)
            self.past_chat_frame_animation.setStartValue(QRect(self.width(), 0, self.past_chat_frame.width(), self.height()))
            self.past_chat_frame_animation.setEndValue(QRect(self.width()-self.past_chat_frame.width(), 0, self.past_chat_frame.width(), self.height()))
            self.past_chat_frame.raise_()

            # 显示 TreeView
            self.tree_view.show()
            self.tree_view.setGeometry(-int(self.width() * 0.3), 0, int(self.width() * 0.3), int(self.height()))
            self.tree_view.raise_()  # 确保 TreeView 在最上层

            # 创建 TreeView 的动画
            self.tree_animation = QPropertyAnimation(self.tree_view, b"geometry")
            self.tree_animation.setDuration(300)
            self.tree_animation.setEasingCurve(QEasingCurve.InOutQuad)
            self.tree_animation.setStartValue(QRect(-self.tree_view.width(), 0, self.tree_view.width(), self.height()))
            self.tree_animation.setEndValue(QRect(0, 0, self.tree_view.width(), self.height()))

            # 创建 toggle_tree_button 的动画
            self.button_animation = QPropertyAnimation(self.toggle_tree_button, b"geometry")
            self.button_animation.setDuration(300)
            self.button_animation.setEasingCurve(QEasingCurve.InOutQuad)
            self.button_animation.setStartValue(self.toggle_tree_button.geometry())
            self.button_animation.setEndValue(QRect(self.tree_view.width(), self.toggle_tree_button.y(), self.toggle_tree_button.width(), self.toggle_tree_button.height()))

            # 同时启动两个动画
            self.tree_animation.start()
            self.button_animation.start()
            self.past_chat_frame_animation.start()
            self.grab_past_chats()
        else:
            self.past_chat_frame_animation = QPropertyAnimation(self.past_chat_frame, b"geometry")
            self.past_chat_frame_animation.setDuration(300)
            self.past_chat_frame_animation.setEasingCurve(QEasingCurve.InOutQuad)
            self.past_chat_frame_animation.setStartValue(QRect(self.width()-self.past_chat_frame.width(), 0, self.past_chat_frame.width(), self.height()))
            self.past_chat_frame_animation.setEndValue(QRect(self.width(), 0, self.past_chat_frame.width(), self.height()))
            self.past_chat_frame_animation.finished.connect(self.past_chat_frame.hide)

            # 隐藏 TreeView
            self.tree_animation = QPropertyAnimation(self.tree_view, b"geometry")
            self.tree_animation.setDuration(300)
            self.tree_animation.setEasingCurve(QEasingCurve.InOutQuad)
            self.tree_animation.setStartValue(QRect(0, 0, self.tree_view.width(), self.height()))
            self.tree_animation.setEndValue(QRect(-self.tree_view.width(), 0, self.tree_view.width(), self.height()))
            self.tree_animation.finished.connect(self.tree_view.hide)

            # 创建 toggle_tree_button 的动画
            self.button_animation = QPropertyAnimation(self.toggle_tree_button, b"geometry")
            self.button_animation.setDuration(300)
            self.button_animation.setEasingCurve(QEasingCurve.InOutQuad)
            self.button_animation.setStartValue(self.toggle_tree_button.geometry())
            self.button_animation.setEndValue(QRect(0, self.toggle_tree_button.y(), self.toggle_tree_button.width(), self.toggle_tree_button.height()))

            # 同时启动两个动画
            self.tree_animation.start()
            self.button_animation.start()
            self.past_chat_frame_animation.start()

    #设置界面：点击外部收起
    def eventFilter(self, obj, event):
      if event.type() == QEvent.MouseButtonPress:
          if self.tree_view.isVisible():
              # 将全局坐标转换为树视图的局部坐标
              local_pos = self.tree_view.mapFromGlobal(event.globalPos())
              if not self.tree_view.rect().contains(local_pos):
                  self.toggle_tree_view()
      return super().eventFilter(obj, event)

    def show_function_call_window(self):
        self.function_chooser.show()

    #api来源：更改提供商
    def update_model_combobox(self, selected_api):
        self.model_combobox.clear()
        
        # 获取对应API的模型列表
        available_models = MODEL_MAP.get(selected_api, [])
        
        # 添加模型并设置默认选项
        if available_models:
            self.model_combobox.addItems(available_models)
            self.model_combobox.setCurrentIndex(0)
        else:
            self.model_combobox.addItem("无可用模型")

    #超长文本显示优化
    def display_full_chat_history_window(self):
        self.history_text_view = ChatHistoryTextView(
        self.chathistory, 
        self.name_user, 
        self.name_ai
    )
        
        self.history_text_view.show()
        self.history_text_view.raise_()

    #流式处理的末端方法
    def update_chat_history(self, clear=True, new_msg=None,msg_id=''):
        # 清空界面元素
        if clear and not new_msg:
            self.user_input_text.clear()

        buffer = []
        append = buffer.append
        total_len = 0
        max_length = 18000
        truncated = False  # 截断标志
        if self.name_ai=='':
            role_ai=self.model_combobox.currentText()
        else:
            role_ai=self.name_ai
        
        if self.name_user=='':
            role_user='user'
        else:
            role_user=self.name_user

        if not new_msg:
            self.chat_history_bubbles.streaming_scroll(False)
            self.chat_history_bubbles.set_role_nickname('assistant', role_ai)
            self.chat_history_bubbles.set_role_nickname('user', role_user)
            self.chat_history_bubbles.set_chat_history(self.chathistory)
            try:
                self.tts_handler.send_tts_request(
                    self.name_ai,
                    self.full_response,
                    force_remain=True
                )
            except Exception as e:
                print('tts_handler.send_tts_request',e)

        else:
            self.chat_history_bubbles.streaming_scroll(True)
            self.chat_history_bubbles.update_bubble(msg_id=msg_id,content=self.full_response,streaming='streaming')

        # 条件保存（仅在内容变化时）
        if clear or buffer:
            if not new_msg:
                self.autosave_save_chathistory()

    #预处理用户输入，并创建发送信息的线程
    def send_message_toapi(self):
        user_input = self.user_input_text.toPlainText()
        if user_input == "/bye":
            self.close()
            return
        self.chathistory.append(
            {
                'role': 'user', 
                'content': user_input,
                'info':{
                    "id":random.randint(100000,999999),
                    'time':time.strftime("%Y-%m-%d %H:%M:%S")
                    }
            }
        )
        self.update_chat_history()
        if self.stream_receive:
            self.response=None
            self.previous_response = None
            self.temp_full_response = ''
            if self.use_concurrent_model.isChecked():
                self.send_message_thread_stream()
            else:
                thread1 = threading.Thread(target=self.send_message_thread_stream)
                thread1.start()
        else:
            try:
                threading.Thread(target=self.send_message_thread).start()
            except Exception as e:
                print(e)

    #更新AI回复
    def update_ai_response_text(self,request_id,content):
        self._handle_update(
            response_length=len(self.full_response),
            timer=self.ai_update_timer,
            update_method=self.perform_ai_actual_update,
            last_update_attr='ai_last_update_time',
            delay_threshold=5000,
            delays=(300, 600),
            request_id=request_id
        )

    #更新AI思考链
    def update_think_response_text(self,request_id,content):
        self._handle_update(
            response_length=len(self.think_response),
            timer=self.think_update_timer,
            update_method=self.perform_think_actual_update,
            last_update_attr='think_last_update_time',
            delay_threshold=5000,
            delays=(300, 600),
            request_id=request_id
        )

    #更新AI辅助函数
    def _handle_update(self, response_length, timer, update_method, last_update_attr, delay_threshold, delays,request_id):
        current_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
        fast_delay, slow_delay = delays
        delay = slow_delay if response_length > delay_threshold else fast_delay
        
        # 获取对应的最后更新时间
        last_update_time = getattr(self, last_update_attr)
        elapsed = current_time - last_update_time

        if elapsed >= delay:
            # 立即执行更新
            update_method(request_id)
        else:
            # 设置延迟更新
            remaining = delay - elapsed
            if timer.isActive():
                timer.stop()
            timer.start(remaining)

    #实施更新
    def perform_ai_actual_update(self,request_id):
        # 更新界面和滚动条
        actual_response = StrTools.combined_remove_var_vast_replace(self)

        self.ai_response_text.setMarkdown(actual_response)
        self.update_chat_history(new_msg=actual_response,msg_id=request_id)
        self.ai_response_text.verticalScrollBar().setValue(
            self.ai_response_text.verticalScrollBar().maximum()
        )

        #0.25.1 气泡
        #self.chat_history_bubbles.update_bubble(msg_id=request_id,content=self.full_response,streaming='streaming')
        try:
            self.tts_handler.send_tts_request(
                self.name_ai,
                self.full_response
            )
        except Exception as e:
            print('tts_handler.send_tts_request',e)

        # 更新时间戳
        self.ai_last_update_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
        self.tokenpers.process_input(self.think_response+self.full_response)
        self.enforce_lower_repeat.setText("强制去重   "+f"tps: {self.tokenpers.get_current_rate():.2f}|peak: {self.tokenpers.get_peak_rate():.2f}")

    def perform_think_actual_update(self,request_id):

        # 更新界面和滚动条
        self.think_text_box.setMarkdown(self.think_response.replace(r'\n','\n'))
        response_lenth=len(self.think_response)
        self.ai_response_text.setText("正在思考...\n"+
                                          '\n已思考字数：'+str(response_lenth)
                                          )
        self.think_text_box.verticalScrollBar().setValue(
            self.think_text_box.verticalScrollBar().maximum()
        )
        #0.25.1 气泡思考栏
        self.chat_history_bubbles.streaming_scroll(True)
        self.chat_history_bubbles.update_bubble(msg_id=request_id,reasoning_content=self.think_response,streaming='streaming')
        
        # 更新时间戳
        self.think_last_update_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
        self.tokenpers.process_input(self.think_response+self.full_response)
        self.enforce_lower_repeat.setText("强制去重   "+f"tps: {self.tokenpers.get_current_rate():.2f}|peak: {self.tokenpers.get_peak_rate():.2f}")

    #接受信息，信息后处理
    def receive_message(self,request_id,content):
        try:
            if self.pause_flag:
                if self.chathistory and self.chathistory[-1]['role'] == 'user':
                    self.chathistory.pop()
                return
            
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
            if content.startswith("\n\n"):
                content = content[2:]
            content = content.replace('</think>', '')
    
            content = StrTools.combined_remove_var_vast_replace(self,content=content)
            #处理无源信息
            if self.last_chat_info=={}:
                self.last_chat_info={
                    'id':request_id,
                    'WARNING':'not a normal message',
                    'time':time.strftime("%Y-%m-%d %H:%M:%S")
                }
            last_message={
                'role': 'assistant', 
                'content': content,
                'info':self.last_chat_info,
                }
            if getattr(self,'thinked'):
                last_message['reasoning_content']=self.think_response
            self.chathistory.append(last_message)

            # 发出信号，通知主线程更新界面
            responce_text=StrTools.combined_remove_var_vast_replace(self)
            self.ai_response_text.setMarkdown(responce_text)
            self.mod_configer.handle_new_message(self.full_response,self.chathistory)
        except Exception as e:
            print(e)
            self.update_response_signal.emit(request_id,f"Error: {str(e)}")
        finally:
            self.send_button.setEnabled(True)
            self.update_chat_history()

    #流式接收线程
    def send_message_thread_stream(self):
        # 预处理消息和参数
        try:
            preprocessor = MessagePreprocessor(self)  # 创建预处理器实例
            message, params = preprocessor.prepare_message()
        except Exception as e:
            self.return_message = f"Error in preparing message: {e}"
            self.update_response_signal.emit(100000,self.return_message)
            return
        if self.use_concurrent_model.isChecked():
            self.concurrent_model.start_workflow(params)
            return

        # 发送请求并处理响应
        try:
            self.send_request(params)
        except Exception as e:
            self.return_message = f"Error in sending request: {e}"
            self.update_response_signal.emit(100000,self.return_message)

    def send_request(self, params):# 0.25.4 等待重构
        """发送请求并处理流式响应"""
        # 处理常规响应内容
        def handle_response(content,temp_response):
            if hasattr(content, "content") and content.content:
                special_block_handler_result=StrTools.special_block_handler(self,
                                    temp_response,
                                    self.think_response_signal.emit,
                                    request_id,
                                    starter='<think>', ender='</think>',
                                    extra_params='think_response'
                                    )
                if special_block_handler_result["starter"] and special_block_handler_result["ender"]:#如果思考链结束
                    self.full_response+= content.content
                    self.full_response.replace('</think>\n\n', '')
                    self.thinked=True
                    self.ai_response_signal.emit(request_id,self.full_response)
                elif not (special_block_handler_result["starter"]):#如果没有思考链
                    self.full_response += content.content
                    self.ai_response_signal.emit(request_id,self.full_response)

            # 处理思考链内容
            if hasattr(content, "reasoning_content") and content.reasoning_content:
                self.thinked=True
                self.think_response += content.reasoning_content
                self.think_response_signal.emit(request_id,self.think_response)

        def to_serializable(obj):
            """递归将对象转换为可序列化的基本类型（字典/列表/基本类型）"""
            if isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            
            if isinstance(obj, dict):
                return {k: to_serializable(v) for k, v in obj.items()}
            
            if isinstance(obj, list):
                return [to_serializable(item) for item in obj]
            
            if hasattr(obj, '__dict__'):
                # 处理普通对象
                return to_serializable(vars(obj))
            
            if hasattr(obj, 'model_dump'):
                # 处理Pydantic v2模型
                return to_serializable(obj.model_dump())
            
            if hasattr(obj, 'dict'):
                # 处理Pydantic v1模型
                return to_serializable(obj.dict())
            
            # 其他不可识别类型
            return str(obj)
        
        def update_info():
            if event.usage:
                # 递归转换所有嵌套结构
                usage_dict = to_serializable(event.usage)
                if isinstance(usage_dict, dict):
                    pass
                else:
                    # 如果转换后不是字典（如某些API返回的列表结构）
                    usage_dict = {'usage_data': usage_dict}
            else:
                usage_dict = {}
            
            self.last_chat_info = {
                **usage_dict,
                "model": event.model,
                "id":request_id,
                'time':time.strftime("%Y-%m-%d %H:%M:%S")
            }
            return self.last_chat_info
        def update_info_none_stream(response):
            try:
                if response.usage:
                    # 递归转换所有嵌套结构
                    usage_dict = to_serializable(response.usage)
                    if isinstance(usage_dict, dict):
                        pass
                    else:
                        # 如果转换后不是字典（如某些API返回的列表结构）
                        usage_dict = {'usage_data': usage_dict}
                else:
                    usage_dict = {}
                
                self.last_chat_info = {
                    **usage_dict,
                    "model": response.model,
                    "id":request_id,
                    'time':time.strftime("%Y-%m-%d %H:%M:%S")
                }
                return self.last_chat_info
            except:
                return {}

        StrTools.debug_chathistory(params['messages'])
        request_id=random.randint(100000,999999)
        self.thinked=False
        api_provider = self.api_var.currentText()
        client = openai.Client(
            api_key=self.api[api_provider][1],
            base_url=self.api[api_provider][0]
        )
        self.response = client.chat.completions.create(**params)
        self.full_response = ""
        self.think_response = "### AI 思考链\n---\n"
        temp_response = ""
        chatting_tool_call = None

        try:
            content= self.response.choices[0].message
            temp_response += content.content
            handle_response(content,temp_response)
            update_info_none_stream(self.response)
            print(f'\n返回长度：{len(self.full_response)}\n思考链长度: {len(self.think_response)}')
            self.update_response_signal.emit(request_id,self.full_response)
            return
        except Exception as e:
            print('已进入流式状态')

        for event in self.response:
            if self.pause_flag:
                print('暂停接收')
                return

            if not hasattr(event, "choices") or not event.choices:
                continue

            content = getattr(event.choices[0], "delta", None)
            if not content:
                continue
            
            if hasattr(content, "content") and content.content:
                temp_response += content.content
            handle_response(content,temp_response)

            if hasattr(content, "tool_calls") and content.tool_calls:
                temp_fcalls = content.tool_calls
                if not chatting_tool_call:
                    chatting_tool_call={
                "id": temp_fcalls[0].id,
                "type": "function",
                "function": {"name": "", "arguments": ""}
            }
                for function_call in temp_fcalls:
                    returned_function_call = getattr(function_call, "function", '')
                    returned_name=getattr(returned_function_call, "name", "")
                    if returned_name:
                        chatting_tool_call["function"]["name"] += returned_name
                    returned_arguments=getattr(returned_function_call, "arguments", "")
                    if returned_arguments:
                        chatting_tool_call["function"]["arguments"] += returned_arguments
                        self.think_response += returned_arguments
                        self.think_response_signal.emit(request_id,self.think_response)
        if chatting_tool_call and chatting_tool_call["function"]["arguments"]:
            try:
                try:
                    arguments = json.loads(chatting_tool_call["function"]["arguments"])  # 验证 JSON 是否合法
                    if isinstance(arguments,str):
                        print('kimi的字符串load结果又来了\n')
                        import ast
                        arguments = ast.literal_eval(chatting_tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    print("函数参数 JSON 解析失败:", chatting_tool_call["function"]["arguments"],
                          '\n尝试python原生导入')
                    try:
                        import ast
                        arguments = ast.literal_eval(chatting_tool_call["function"]["arguments"])
                    except Exception as e:
                        arguments=chatting_tool_call["function"]["arguments"]
                        print('python原生导入也不行','函数调用的时候再救')
                except Exception as e:
                    print(f'狗日的救不回来：{e}','函数调用的时候再救')

                full_function_call = {
                    "id": chatting_tool_call["id"],
                    "type": chatting_tool_call["type"],
                    "function": {
                        "name": chatting_tool_call["function"]["name"],
                        "arguments": arguments
                    }
                }
                tool_result = self.function_manager.call_function(full_function_call)
                full_function_call = {
                    "id": chatting_tool_call["id"],
                    "type": chatting_tool_call["type"],
                    "function": {
                        "name": chatting_tool_call["function"]["name"],
                        "arguments": chatting_tool_call["function"]["arguments"]#json.dumps(arguments, ensure_ascii=False)
                    }
                }
                if not isinstance(tool_result, str):
                    tool_result = json.dumps(tool_result, ensure_ascii=False)
                self.chathistory.append({"role":"assistant",
                                         "content":self.full_response,
                                         'tool_calls':[full_function_call],
                                         'reasoning_content':self.think_response,
                                         'info':update_info()})
                self.chathistory.append({"role":"tool",
                                         "tool_call_id":chatting_tool_call["id"],
                                         "content":tool_result,
                                         'info':full_function_call})
                
                preprocessor = MessagePreprocessor(self)  # 创建预处理器实例
                message, params = preprocessor.prepare_message(tools=True)
                StrTools.debug_chathistory(message)
                self.send_request(params)
                #self.update_chat_history()
                return
            except Exception as e:
                print('Failed function calling:',type(e),e)
                self.return_message = f"Failed function calling: {e}"
                self.update_response_signal.emit(100000,self.return_message)
                
            
        
        
        update_info()

        print(f'\n返回长度：{len(self.full_response)}\n思考链长度: {len(self.think_response)}')
        self.update_response_signal.emit(request_id,self.full_response)

    #完整接受线程
    def send_message_thread(self):
        # 预处理消息和参数
        try:
            preprocessor = MessagePreprocessor(self)  # 创建预处理器实例
            preprocessor.stream=False
            message, params = preprocessor.prepare_message()
            print(message)
        except Exception as e:
            self.return_message = f"Error in preparing message: {e}"
            self.update_response_signal.emit(100000,self.return_message)
            return

        # 发送请求并处理响应
        try:
            self.send_request(params)
        except Exception as e:
            self.return_message = f"Error in sending request: {e}"
            self.update_response_signal.emit(100000,self.return_message)

    #检查当前消息数是否是否触发最大对话数
    def fix_max_message_rounds(self,max_round_bool=True,max_round=0):
        if max_round_bool:
            return min(self.max_message_rounds,len(self.chathistory))
        else:
            return min(max_round,len(self.chathistory))

    #发送消息前的预处理，防止报错,触发长文本优化,触发联网搜索
    def sending_rule(self):           
        user_input = self.user_input_text.toPlainText()
        print('已获取输入：',user_input)
        if self.chathistory[-1]['role'] == "user":
            # 创建一个自定义的 QMessageBox
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('确认操作')
            msg_box.setText('确定连发两条吗？')
            
            # 添加自定义按钮
            btn_yes = msg_box.addButton('确定', QMessageBox.YesRole)
            btn_no = msg_box.addButton('取消', QMessageBox.NoRole)
            btn_edit = msg_box.addButton('编辑聊天记录', QMessageBox.ActionRole)
            
            # 显示消息框并获取用户的选择
            msg_box.exec_()
            
            # 根据用户点击的按钮执行操作
            if msg_box.clickedButton() == btn_yes:
                # 正常继续
                pass
            elif msg_box.clickedButton() == btn_no:
                # 如果否定：return False
                return False
            elif msg_box.clickedButton() == btn_edit:
                # 如果“编辑聊天记录”：跳转self.edit_chathistory()
                self.edit_chathistory()
                return False
        elif user_input == '':
            # 弹出窗口：确定发送空消息？
            reply = QMessageBox.question(self, '确认操作', '确定发送空消息？',
                                        QMessageBox.Yes | QMessageBox.No,
                                        QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.user_input_text.setText('_')
                # 正常继续
            elif reply == QMessageBox.No:
                # 如果否定：return False
                return False
        if self.long_chat_improve_var:
            try:
                self.new_chat_rounds+=2
                full_chat_lenth=len(str(self.chathistory))
                message_lenth_bool=(len(self.chathistory)>self.max_message_rounds or full_chat_lenth>self.max_total_length)
                newchat_rounds_bool=self.new_chat_rounds>self.max_message_rounds
                newchat_lenth_bool=len(str(self.chathistory[-self.new_chat_rounds:]))>self.max_segment_length
                long_chat_improve_bool=message_lenth_bool and newchat_rounds_bool or newchat_lenth_bool

                print('长对话优化日志：',
                    '\n当前对话次数:',len(self.chathistory)-1,
                    '\n当前对话长度（包含system prompt）:',full_chat_lenth,
                    '\n当前新对话轮次:',self.new_chat_rounds,'/',self.max_message_rounds,
                    '\n新对话长度:',len(str(self.chathistory[-self.new_chat_rounds:])),
                    '\n触发条件:',
                    '\n总对话轮数达标:'
                    '\n对话长度达达到',self.max_total_length,":", message_lenth_bool,
                    '\n新对话轮次超过限制:', newchat_rounds_bool,
                    '\n新对话长度超过限制:', newchat_lenth_bool,
                    '\n触发长对话优化:',long_chat_improve_bool
                    )
                
                if long_chat_improve_bool:
                    self.new_chat_rounds=0
                    print('条件达到,长文本优化已触发')
                    self.long_chat_improve()
            except Exception as e:
                print("long chat improvement failed, Error code:",e)
        if not self.back_ground_update_var:
            print('背景更新日志:没启动')
        if self.back_ground_update_var:
            try:
                self.new_background_rounds+=2
                full_chat_lenth=len(str(self.chathistory))
                message_lenth_bool=(len(self.chathistory)>self.max_background_rounds or full_chat_lenth>self.max_backgound_lenth)
                newchat_rounds_bool=self.new_background_rounds>self.max_background_rounds
                long_chat_improve_bool=message_lenth_bool and newchat_rounds_bool
                print('背景更新日志：',
                    '\n当前对话次数:',len(self.chathistory)-1,
                    '\n当前对话长度（包含system prompt）:',full_chat_lenth,
                    '\n当前新对话轮次:',self.new_background_rounds,'/',self.max_background_rounds,
                    '\n新对话长度:',(len(str(self.chathistory[-self.new_background_rounds:]))-len(str(self.chathistory[0]))),
                    '\n触发条件:',
                    '\n总对话轮数达标:',
                    '\n对话长度达达到',self.max_backgound_lenth,":", message_lenth_bool,
                    '\n新对话轮次超过限制:', newchat_rounds_bool,
                    '\n触发背景更新:',long_chat_improve_bool
                    )
                if long_chat_improve_bool:
                    self.new_background_rounds=0
                    
                    print('条件达到,背景更新已触发')
                    self.call_background_update()
                
            except Exception as e:
                print("long chat improvement failed, Error code:",e)
            except Exception as e:
                print("long chat improvement failed, Error code:",e)
        if self.enforce_lower_repeat_var:
            self.enforce_lower_repeat_text=''
            repeat_list=self.repeat_processor.find_last_repeats()
            if len(repeat_list)>0:
                for i in repeat_list:
                    self.enforce_lower_repeat_text+=i+'"或"'
                self.enforce_lower_repeat_text='避免回复词汇"'+self.enforce_lower_repeat_text[:-2]
                print("降重触发:",self.enforce_lower_repeat_text)
        else:
            self.enforce_lower_repeat_text=''
        if self.web_search_enabled:
            if self.web_searcher.rag_checkbox.isChecked():
                api_provider = self.web_searcher.rag_provider_combo.currentText()
                api_key=self.api[api_provider][1]
                self.web_searcher.perform_search(user_input,api_key)
            else:
                self.web_searcher.perform_search(user_input)
        self.update_opti_bar()
        return True

    #“发送”按钮触发，开始消息预处理和UI更新
    def send_message(self):
        if self.pause_flag:
            self.pause_flag = not self.pause_flag
        if self.send_button.isEnabled() and self.sending_rule():
            if self.use_muti_model.isChecked():
                provider,modelname=self.ordered_model.collect_selected_models()
                if provider and modelname:
                    self.api_var.setCurrentText(provider)
                    self.model_combobox.setCurrentText(modelname)
            self.send_button.setEnabled(False)
            self.ai_response_text.setText("已发送，等待回复...")
            self.send_message_toapi()

    #尝试连接，未使用
    def try_parse_url(self, url):
        try:
            response = requests.head(url, timeout=5)
            if response.status_code == 200:
                return True
            else:
                return False
        except requests.RequestException as e:
            return False

    #api导入窗口
    def open_api_window(self):
        if not hasattr(self,'self.api_window'):
            self.api_window = APIConfigWidget(application_path=self.application_path)
            self.api_window.configUpdated.connect(self._handle_api_init)
        self.api_window.show()
        self.api_window.raise_()

    def _handle_api_init(self, config_data: dict={}) -> None:
        """处理配置更新信号"""
        print(f'Chatapi Main window model update finished, time cost:{time.time()-start_time_stamp:.2f}s')
        global MODEL_MAP
        if not config_data=={}:
            self.api = {
                name: (data["url"], data["key"])
                for name, data in config_data.items()
            }
        MODEL_MAP={}
        for key,value in config_data.items():
            if value['models']:
                MODEL_MAP[key]=value['models']
        pervious_api_var=self.api_var.currentText()
        pervious_model=self.model_combobox.currentText()
        self.api_var.clear()
        self.api_var.addItems(MODEL_MAP.keys())
        self.model_combobox.clear()
        self.model_combobox.addItems(MODEL_MAP[self.api_var.currentText()])
        if pervious_api_var in MODEL_MAP.keys():
            self.api_var.setCurrentText(pervious_api_var)
        if pervious_model in MODEL_MAP[self.api_var.currentText()]:
            self.model_combobox.setCurrentText(pervious_model)

    #清除聊天记录
    def clear_history(self):
        self.autosave_save_chathistory()
        self.creat_new_chathistory()
        self.chat_history_bubbles.clear()
        self.ai_response_text.clear()
        self.new_chat_rounds=0
        self.new_background_rounds=0
        self.last_summary=''
        self.update_opti_bar()
        self.update_chat_history()

    #打开系统提示设置窗口
    def open_system_prompt(self, show_at_call=True):
        def update_system_prompt(prompt):
            if self.chathistory and self.chathistory[0]['role'] == "system":
                self.chathistory[0]['content'] = prompt
            else:
                self.creat_new_chathistory()
            self.sysrule=prompt
        def get_system_prompt():
            if len(self.chathistory)>1:
                if self.chathistory and self.chathistory[0]['role'] == "system":
                    return self.chathistory[0]['content']
            else:
                return self.sysrule
        # 创建子窗口
        if not hasattr(self,"system_prompt_override_window"):
            self.system_prompt_override_window = SystemPromptUI(folder_path='utils/system_prompt_presets')
            self.system_prompt_override_window.update_system_prompt.connect(update_system_prompt)
            self.system_prompt_override_window.name_user_edit.textChanged.connect(lambda text:self.handle_name_changed('user',text))
            self.system_prompt_override_window.name_ai_edit.textChanged.connect(lambda text:self.handle_name_changed('assistant',text))
        if show_at_call:
            self.system_prompt_override_window.show()
        if self.system_prompt_override_window.isVisible():
            self.system_prompt_override_window.raise_()
            self.system_prompt_override_window.activateWindow()
        self.system_prompt_override_window.load_income_prompt(get_system_prompt(),name=self.chathistory[0]['info']['name'])


    #打开设置，快捷键
    def open_settings_window(self):
        self.settings_window = QDialog(self)
        self.settings_window.setWindowTitle("设置")
        self.settings_window.resize(300, 80)  # 设置子窗口大小

        layout = QVBoxLayout()
        self.settings_window.setLayout(layout)

        send_message_bu = QCheckBox("Ctrl+Enter键发送消息")
        send_message_bu.setChecked(self.send_message_var)  # 默认选中

        autoslide_bu = QCheckBox("Tab/Ctrl+Q推出设置")
        autoslide_bu.setChecked(self.autoslide_var)  # 默认选中

        hotkey_sysrule_bu = QCheckBox("Ctrl+E打开system prompt")
        hotkey_sysrule_bu.setChecked(self.hotkey_sysrule_var)  # 默认选中

        layout.addWidget(send_message_bu)
        layout.addWidget(autoslide_bu)
        layout.addWidget(hotkey_sysrule_bu)

        confirm_bu=QPushButton("确认")
        layout.addWidget(confirm_bu)

        def confirm_settings():
            self.send_message_var = send_message_bu.isChecked()
            self.autoslide_var=autoslide_bu.isChecked()
            self.hotkey_sysrule_var=hotkey_sysrule_bu.isChecked()
            self.bind_enter_key()
            self.settings_window.close()

        confirm_bu.clicked.connect(confirm_settings)
        self.settings_window.exec_()

    #绑定快捷键
    def bind_enter_key(self):
        """根据设置绑定或解绑 Enter 键"""

        QShortcut(QKeySequence("F11"), self).activated.connect(
            lambda: self.showFullScreen() if not self.isFullScreen() else self.showNormal()
        )

        QShortcut(QKeySequence(Qt.CTRL + Qt.Key_N), self).activated.connect(self.clear_history)

        QShortcut(QKeySequence(Qt.CTRL + Qt.Key_O), self).activated.connect(self.load_chathistory)

        QShortcut(QKeySequence(Qt.CTRL + Qt.Key_S), self).activated.connect(self.save_chathistory)

        QShortcut(QKeySequence(Qt.CTRL + Qt.Key_M), self).activated.connect(self.show_mod_configer)

        QShortcut(QKeySequence(Qt.CTRL + Qt.Key_T), self).activated.connect(self.show_theme_settings)

        QShortcut(QKeySequence(Qt.CTRL + Qt.Key_D), self).activated.connect(self.open_max_send_lenth_window)

        QShortcut(QKeySequence(Qt.CTRL + Qt.Key_B), self).activated.connect(self.background_settings_window)

        if self.send_message_var:
            self.send_message_shortcut=QShortcut(QKeySequence(), self)
            self.send_message_shortcut.setKey(QKeySequence(Qt.CTRL + Qt.Key_Return))
            self.send_message_shortcut.activated.connect(self.send_message)
            self.send_message_var=True
        elif self.send_message_shortcut:
            self.send_message_shortcut.setKey(QKeySequence())
        
        if self.autoslide_var:
            self.shortcut1 = QShortcut(QKeySequence(), self)
            self.shortcut1.setKey(QKeySequence(Qt.Key_Tab))
            self.shortcut1.activated.connect(self.toggle_tree_view)
            self.shortcut2 = QShortcut(QKeySequence(), self)
            self.shortcut2.setKey(QKeySequence(Qt.CTRL+Qt.Key_Q))
            self.shortcut2.activated.connect(self.toggle_tree_view)
            self.autoslide_var=True
        elif self.shortcut1:
            self.shortcut1.setKey(QKeySequence())
            self.shortcut2.setKey(QKeySequence())

        
        if self.hotkey_sysrule_var:
            self.hotkey_sysrule= QShortcut(QKeySequence(), self)
            self.hotkey_sysrule.setKey(QKeySequence(Qt.CTRL+Qt.Key_E))
            self.hotkey_sysrule.activated.connect(self.open_system_prompt)
            self.hotkey_sysrule_var=True
        elif self.hotkey_sysrule:
            self.hotkey_sysrule.setKey(QKeySequence())

    #Enter发送信息
    def autosend_message(self, event):
        """自定义按键事件处理"""
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.send_message()
        else:
            # 调用原始的 keyPressEvent 处理其他按键
            QTextEdit.keyPressEvent(self.user_input_text, event)

    #获取ai说的最后一句
    def get_last_assistant_content(self):
        # 从后向前遍历聊天历史
        for chat in reversed(self.chathistory):
            if chat.get('role') == 'assistant':  # 检查 role 是否为 'assistant'
                return chat.get('content')  # 返回对应的 content 值
        return None  # 如果没有找到 role 为 'assistant' 的记录，返回 None

    #打开模式设置
    def open_module_window(self):
        pass
    
    #保存聊天
    def save_chathistory(self, filename=None):
        if not filename:
            # 弹出文件保存窗口
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存聊天记录", "", "JSON files (*.json);;All files (*)"
            )
        else:
            unsupported_chars = ["\n",'<', '>', ':', '"', '/', '\\', '|', '?', '*','{','}',',','.','，','。',' ','!','！',' ']
            for char in unsupported_chars:
                filename = filename.replace(char, '')
            if not filename.endswith('.json'):
                filename += '.json'
            file_path = os.path.join(self.history_path, filename)

        if file_path:  # 检查 file_path 是否有效
            try:
                with open(file_path, "w", encoding="utf-8") as file:
                    json.dump(self.chathistory, file, ensure_ascii=False, indent=4)
                print("聊天记录已保存到", file_path)
            except Exception as e:
                print(self.chathistory)
                QMessageBox.critical(self, "保存失败", f"保存聊天记录时发生错误：{e}")
        else:
            QMessageBox.warning(self, "取消保存", "未选择保存路径，聊天记录未保存。")

    #自动保存
    def autosave_save_chathistory(self):
        filename=False
        for chat in self.chathistory:
            if chat["role"]=="user":  
                if len(chat["content"])>10:
                    filename=chat["content"][:10]      
                else:
                    filename=chat["content"]
                unsupported_chars = ["\n",'<', '>', ':', '"', '/', '\\', '|', '?', '*','{','}',',','.','，','。',' ','!','！']
                for char in unsupported_chars:
                    filename = filename.replace(char, '')
                filename = filename.rstrip(' .')
                break
        if filename:
            filename=time.strftime("[%Y-%m-%d]", time.localtime())+filename
            self.save_chathistory(filename=filename)

    #载入记录
    def load_chathistory(self,filename=None):
        # 弹出文件选择窗口
        if filename:
            file_path=filename
        else:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "导入聊天记录", "", "JSON files (*.json);;All files (*)"
            )
        load_start_time=time.perf_counter()
        if file_path:
            with open(file_path, "r", encoding="utf-8") as file:
                self.chathistory = json.load(file)
            self.chathistory=ChatHistoryTools.patch_history_0_25_1(self.chathistory,
                                                                   names={
                                                                       'user':self.name_user,
                                                                       'assistant':self.name_ai
                                                                       },
                                                                    avatar={
                                                                       'user':'',
                                                                       'assistant':''
                                                                       }
                                                                    )
            self.update_chat_history()  # 更新聊天历史显示
            print("聊天记录已导入，当前聊天记录：", file_path,
                  '\n对话长度',len(self.chathistory),
                  '\n识别长度',len(self.chathistory[-1]['content']))
            #覆盖两人名字
            self.name_user=self.chathistory[0]['info']['name']['user'     ]
            self.name_ai  =self.chathistory[0]['info']['name']['assistant']

            self.new_chat_rounds=min(self.max_message_rounds,len(self.chathistory))
            self.new_background_rounds=min(self.max_background_rounds,len(self.chathistory))
            self.last_summary=''
            self.update_opti_bar()
            self.update_avatar_to_chat_bubbles()
            self.update_name_to_chatbubbles()
        print(f'处理时间:{(time.perf_counter()-load_start_time)*1000:.2f}ms')

    #编辑记录
    def edit_chathistory(self):
        editor = ChatHistoryEditor(self.chathistory, self)
        editor.editCompleted.connect(lambda new_history: setattr(self, 'chathistory', new_history))
        editor.editCompleted.connect(self.update_chat_history)
        editor.exec_()

    def edit_chathistory_by_index(self,id,text):
        index=ChatHistoryTools.locate_chat_index(self.chathistory,id)
        self.chathistory[index]['content']=text

    #修改问题
    def edit_user_last_question(self):
        # 从后往前遍历聊天历史
        self.handel_call_back_to_lci_bgu()
        if self.chathistory[-1]["role"]=="user":
            self.user_input_text.setText(self.chathistory[-1]["content"])
            self.chathistory.pop()
        elif self.chathistory[-1]["role"]=="assistant" or self.chathistory[-1]["role"]=="tool":#处理工具调用时被用户截断
            while self.chathistory[-1]["role"]!="user":
                self.chathistory.pop()
            self.user_input_text.setText(self.chathistory[-1]["content"])
            self.chathistory.pop()
        else:
            QMessageBox.warning(self,'重传无效','至少需要发送过一次消息')
        self.update_chat_history(clear= False)

    #重生成消息，直接创建最后一条
    def resend_message_last(self):
        self.resend_message()
    
    def resend_message(self,request_id=''):
        self.handel_call_back_to_lci_bgu()
        if request_id:
            index=ChatHistoryTools.locate_chat_index(self.chathistory,request_id)
            self.chathistory=self.chathistory[:index+1]

        if self.chathistory[-1]["role"]=="user":
            self.user_input_text.setText(self.chathistory[-1]["content"])
            self.chathistory.pop()
            self.send_message()
        elif self.chathistory[-1]["role"]=="assistant":
            while self.chathistory[-1]["role"]!="user":
                self.chathistory.pop()
            self.user_input_text.setText(self.chathistory[-1]["content"])
            self.chathistory.pop()
            self.send_message()
        elif self.user_input_text.toPlainText():
            self.send_message()
        else:
            QMessageBox.warning(self,'重传无效','至少需要发送过一次消息')

    #流式设置
    def open_send_method_window(self):
        self.send_method_window=SendMethodWindow()
        # 显示子窗口
        self.send_method_window.show()

    #重写关闭事件，添加自动保存聊天记录和设置
    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            self.autosave_save_chathistory()  # 调用自动保存聊天历史的方法
        except Exception as e:
            print("autosave_save_chathistory fail",e)
        try:
            self.save_hotkey_config()
        except Exception as e:
            print("save_hotkey_config",e)
        ConfigManager.config_save(self)
        ModelMapManager().save_model_map(MODEL_MAP)
        self.mod_configer.run_close_event()
        # 确保执行父类关闭操作
        super().closeEvent(event)
        event.accept()  # 确保窗口可以正常关闭

    #保存快捷键设置
    def save_hotkey_config(self):
        # 创建配置文件对象
        config = configparser.ConfigParser()
        # 添加一个section
        config.add_section('HotkeyConfig')
        # 设置变量值
        config.set('HotkeyConfig', 'send_message_var', str(self.send_message_var))
        config.set('HotkeyConfig', 'autoslide_var', str(self.autoslide_var))
        config.set('HotkeyConfig', 'hotkey_sysrule_var', str(self.hotkey_sysrule_var))
        # 写入文件
        with open('hot_key.ini', 'w', encoding='utf-8') as configfile:
            config.write(configfile)

    #读取快捷键ini
    def read_hotkey_config(self):
        # 创建配置文件对象
        config = configparser.ConfigParser()
        # 读取文件
        config.read('hot_key.ini')
        # 读取变量值
        try:
            if 'HotkeyConfig' in config:
                self.send_message_var = config.getboolean('HotkeyConfig', 'send_message_var')
                self.autoslide_var = config.getboolean('HotkeyConfig', 'autoslide_var')
                self.hotkey_sysrule_var=config.getboolean('HotkeyConfig', 'hotkey_sysrule_var')
                print("配置已从 hot_key.ini 文件中读取。")
            else:
                print("配置文件中没有找到 HotkeyConfig 部分。")
        except Exception as e:
            print(e)

    #获取历史记录
    def grab_past_chats(self):
        # 获取当前文件夹下所有.json文件
        self.past_chats=self.load_past_chats(self.history_path)

        # 将文件名添加到QComboBox中
        self.past_chat_list.clear()
        file_names=sorted(list(self.past_chats.keys()),reverse=True)
        for file_name in file_names:
            self.past_chat_list.addItem(file_name)

    def load_past_chats(self,application_path: str) -> Dict[str, str]:
        """并行获取并验证历史聊天记录"""
        # 共享数据结构与线程锁
        past_chats = {}
        lock = threading.Lock()
        if not os.path.exists(application_path):
            os.mkdir(application_path)
        
        def get_json_files() -> List[str]:
            """获取最新的50个JSON文件"""
            files = [f for f in os.listdir(application_path) if f.endswith('.json')]
            return sorted(
                files,
                key=lambda x: os.path.getmtime(os.path.join(application_path, x)),
                reverse=True
            )[:50]

        def process_result(file_name: str, valid: bool, message: str = ""):
            """线程安全的结果处理"""
            with lock:
                if valid:
                    past_chats[file_name] = os.path.join(application_path, file_name)
                else:
                    error_msg = f"Skipped {file_name}: {message}" if message else f"Skipped invalid file: {file_name}"
                    print(error_msg)

        def validate_chat_file(file_name: str) -> Tuple[bool, str]:
            """验证单个聊天文件"""
            file_path = os.path.join(application_path, file_name)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    if not validate_json_structure(json.load(f)):
                        return False, "Invalid data structure"
                    return True, ""
            except json.JSONDecodeError:
                return False, "Invalid JSON format"
            except Exception as e:
                return False, str(e)

        def validate_json_structure(data) -> bool:
            """验证JSON数据结构，支持工具调用格式"""
            if not isinstance(data, list):
                return False

            for item in data:
                # 检查是否为字典类型
                if not isinstance(item, dict):
                    return False

                role = item.get("role")
                # 检查角色有效性
                if role not in {"user", "system", "assistant", "tool"}:
                    return False

                # 根据不同角色验证字段
                if role in ("user", "system"):
                    # 必须包含content字段且为字符串
                    if "content" not in item or not isinstance(item["content"], str):
                        return False

                elif role == "assistant":
                    # 至少包含content或tool_calls中的一个
                    has_content = "content" in item
                    has_tool_calls = "tool_calls" in item
                    if not (has_content or has_tool_calls):
                        return False

                    # 检查content类型（允许字符串或null）
                    if has_content and not isinstance(item["content"], (str, type(None))):
                        return False

                    # 检查tool_calls是否为列表
                    if has_tool_calls and not isinstance(item["tool_calls"], list):
                        return False

                elif role == "tool":
                    # 必须包含tool_call_id和content字段
                    if "tool_call_id" not in item or "content" not in item:
                        return False
                    # content必须为字符串
                    if not isinstance(item["content"], str):
                        return False

            return True

        # 主处理流程
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(validate_chat_file, fn): fn
                for fn in get_json_files()
            }

            for future in concurrent.futures.as_completed(futures):
                file_name = futures[future]
                try:
                    valid, message = future.result()
                    process_result(file_name, valid, message)
                except Exception as e:
                    with lock:
                        print(f"Error processing {file_name}: {str(e)}")

        return past_chats
    
    #从历史记录载入聊天
    def load_from_past(self, index):
        self.autosave_save_chathistory()
        
        # 基础安全校验
        if not self.past_chat_list.currentItem():
            print("No item selected")
            return

        # 获取当前选中的列表项
        selected_item = self.past_chat_list.currentItem()
        
        # 直接读取存储的完整路径
        try:
            file_path = os.path.join(self.history_path,selected_item.text())

            
            self.load_chathistory(filename=file_path)
        except AttributeError as e:
            print(f"数据读取失败: {str(e)}")

    #长文本优化：启动线程
    def long_chat_improve(self):
        self.new_chat_rounds=0
        self.update_opti_bar()
        try:
            print("长文本优化：线程启动")
            threading.Thread(target=self.long_chat_improve_thread).start()
        except Exception as e:
            print(e)

    #长文本优化：总结进程
    def long_chat_improve_thread(self):
        self.last_summary=''
        self.lci_cleaned_system_prompt=''
        summary_prompt=LongChatImprovePersetVars.summary_prompt
        user_summary=LongChatImprovePersetVars.user_summary
        if self.long_chat_hint!='':
            user_summary+=LongChatImprovePersetVars.long_chat_hint_prefix+str(self.long_chat_hint)
        if self.chathistory[0]["role"]=="system":
            try:
                self.last_summary=(self.chathistory[0]["content"].split(LongChatImprovePersetVars.before_last_summary))[1]
                self.lci_cleaned_system_prompt=(self.chathistory[0]["content"].split(LongChatImprovePersetVars.before_last_summary))[0]
            except Exception as e:
                self.last_summary=''
            last_full_story=LongChatImprovePersetVars.before_last_summary+\
                            self.last_summary+\
                            LongChatImprovePersetVars.after_last_summary+\
                            ChatHistoryTools.to_readable_str(self.chathistory[-self.max_message_rounds:])#,{'user':self.name_user,'assistant':self.name_ai,})
        else:
            last_full_story=ChatHistoryTools.to_readable_str(self.chathistory[-self.max_message_rounds:])
            if self.lci_cleaned_system_prompt and getattr(self,'enable_lci_system_prompt',None):
                last_full_story=self.lci_cleaned_system_prompt+last_full_story
                

        last_full_story=user_summary+last_full_story
        messages=[
            {"role":"system","content":summary_prompt},
            {"role":"user","content":last_full_story}
        ]
        if self.long_chat_improve_api_provider:
            api_provider=self.long_chat_improve_api_provider
            print('自定义长对话优化API提供商：',api_provider)
        else:
            api_provider = self.api_var.currentText()
            print('默认对话优化API提供商：',api_provider)
        if self.long_chat_improve_model:
            model=self.long_chat_improve_model
            print('自定义长对话优化模型：',model)
        else:
            model = self.model_combobox.currentText()
            print('默认长对话优化模型：',model)
        client = openai.Client(
            api_key=self.api[api_provider][1],  # 替换为实际的 API 密钥
            base_url=self.api[api_provider][0]  # 替换为实际的 API 基础 URL
        )
        try:
            print("长文本优化：迭代1发送。\n发送内容长度:",len(last_full_story))
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                #temperature=0
            )
            return_story = completion.choices[0].message.content
            print("长文本优化：迭代1完成。\n返回长度:",len(return_story),'\n返回内容：',return_story)
            if self.last_summary=='':
                print("self.last_summary==''")
            if self.last_summary!='':
                last_full_story=LongChatImprovePersetVars.summary_merge_prompt+self.last_summary+LongChatImprovePersetVars.summary_merge_prompt_and+return_story
                print("长文本优化：迭代2开始。\n发送长度:",len(last_full_story),"=",len(self.last_summary),'+',len(return_story))
                messages=[
                {"role":"system","content":summary_prompt},
                {"role":"user","content":last_full_story}
                ]
                completion = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    #temperature=0
                )
                return_story = completion.choices[0].message.content    
                print("长文本优化：迭代2完成。\n返回长度:",len(return_story),'\n返回内容：',return_story)
            try:
                if self.chathistory[0]["role"]=="system":
                    pervious_sysrule = self.chathistory[0]["content"].split(LongChatImprovePersetVars.before_last_summary)[0]
                else:
                    pervious_sysrule=self.sysrule.split(LongChatImprovePersetVars.before_last_summary)[0]
            except Exception as e:
                if self.chathistory[0]["role"]=="system":
                    pervious_sysrule = self.chathistory[0]["content"]
                else:
                    pervious_sysrule=self.sysrule
                print("pervious_sysrule failure, Error code:",e,'\nCurrent "pervious_sysrule":',pervious_sysrule)
            # 替换系统背景
            
            self.sysrule=pervious_sysrule+'\n'+LongChatImprovePersetVars.before_last_summary+return_story
            self.chathistory[0]={"role":"system","content":self.sysrule,'info':{'id':999999}}
            self.last_summary=return_story
            print('长对话处理一次,历史记录第一位更新为：',self.chathistory[0]["content"])
            self.autosave_save_chathistory()
        except Exception as e:
            # 如果线程中发生异常，也通过信号通知主线程
            self.update_response_signal.emit(random.randint(10000,99999),f"Error: {str(e)}")
            print('长对话优化报错，Error code:',e)

    #对话设置，主设置，全局设置
    def open_max_send_lenth_window(self):
        config = {
            'max_message_rounds': self.max_message_rounds,
            'long_chat_improve_var': self.long_chat_improve_var,
            'long_chat_placement': self.long_chat_placement,
            'MODEL_MAP': MODEL_MAP,
            'long_chat_improve_api_provider': self.long_chat_improve_api_provider,
            'long_chat_improve_model': self.long_chat_improve_model,
            'top_p_enable': self.top_p_enable,
            'temperature_enable': self.temperature_enable,
            'presence_penalty_enable': self.presence_penalty_enable,
            'top_p': self.top_p,
            'temperature': self.temperature,
            'presence_penalty': self.presence_penalty,
            'long_chat_hint': self.long_chat_hint,
            'autoreplace_var': self.autoreplace_var,
            'autoreplace_from': self.autoreplace_from,
            'autoreplace_to': self.autoreplace_to,
            'name_user': self.name_user,
            'name_ai': self.name_ai,
            'enable_lci_system_prompt':self.enable_lci_system_prompt,
        }
        if not hasattr(self,"main_setting_window"):
            self.main_setting_window=MainSettingWindow(config=config)
            self._connect_signal_mcsw_window()
        #自动模型库更新完成后需要更新模型盒子
        self.main_setting_window.config=config
        self.main_setting_window.update_api_provider_combo()
        self.main_setting_window.show()
        self.main_setting_window.raise_()

    def _connect_signal_mcsw_window(self):
        if hasattr(self, "main_setting_window"):
            # 最大对话轮数
            self.main_setting_window.max_rounds_changed.connect(
                lambda value: setattr(self, 'max_message_rounds', value))
            # 长对话优化设置
            self.main_setting_window.long_chat_improve_changed.connect(
                lambda state: setattr(self, 'long_chat_improve_var', state))
            self.main_setting_window.include_system_prompt_changed.connect(
                lambda state: setattr(self, 'enable_lci_system_prompt', state))
            self.main_setting_window.long_chat_placement_changed.connect(
                lambda text: setattr(self, 'long_chat_placement', text))
            self.main_setting_window.long_chat_api_provider_changed.connect(
                lambda text: setattr(self, 'long_chat_improve_api_provider', text))
            self.main_setting_window.long_chat_model_changed.connect(
                lambda text: setattr(self, 'long_chat_improve_model', text))
            
            # 参数设置
            self.main_setting_window.top_p_changed.connect(
                lambda value: setattr(self, 'top_p', value))
            self.main_setting_window.temperature_changed.connect(
                lambda value: setattr(self, 'temperature', value))
            self.main_setting_window.presence_penalty_changed.connect(
                lambda value: setattr(self, 'presence_penalty', value))
            self.main_setting_window.top_p_enable_changed.connect(
                lambda state: setattr(self, 'top_p_enable', state))
            self.main_setting_window.temperature_enable_changed.connect(
                lambda state: setattr(self, 'temperature_enable', state))
            self.main_setting_window.presence_penalty_enable_changed.connect(
                lambda state: setattr(self, 'presence_penalty_enable', state))
            self.main_setting_window.stream_receive_changed.connect(
                lambda state: setattr(self, 'stream_receive', state))

            # 自定义提示
            self.main_setting_window.custom_hint_changed.connect(
                lambda text: setattr(self, 'long_chat_hint', text))
            
            # 自动替换
            self.main_setting_window.autoreplace_changed.connect(
                lambda state: setattr(self, 'autoreplace_var', state))
            self.main_setting_window.autoreplace_from_changed.connect(
                lambda text: setattr(self, 'autoreplace_from', text))
            self.main_setting_window.autoreplace_to_changed.connect(
                lambda text: setattr(self, 'autoreplace_to', text))
            
            # 代称设置
            self.main_setting_window.user_name_changed.connect(
                lambda text:self.handle_name_changed('user',text))
            self.main_setting_window.assistant_name_changed.connect(
                lambda text:self.handle_name_changed('assistant',text))
            
            self.main_setting_window.long_chat_improve_changed.connect(
                self.update_opti_bar
            )

    #名称更新
    def handle_name_changed(self,role,name):
        if role=='user':
            self.name_user=name
        elif role=='assistant':
            self.name_ai=name
        self.init_name_to_history()
        self.update_name_to_chatbubbles()
    #历史对话
    def past_chats_menu(self, position):
        target_item = self.past_chat_list.itemAt(position)
        if not target_item:
            return

        context_menu = QMenu(self.past_chat_list)

        load_history = context_menu.addAction("载入")
        load_history.triggered.connect(
            lambda: self.load_chathistory(filename=os.path.basename(self.past_chat_list.currentItem().text()))
        )

        delete_action = context_menu.addAction("删除")
        delete_action.triggered.connect(
            lambda: self.delete_selected_history()
        )

        import_action = context_menu.addAction("导入system prompt")
        import_action.setToolTip('从过去的中获取系统提示文本并覆盖掉\n当前对话中的系统提示。')
        import_action.triggered.connect(
            lambda: self.load_sys_pmt_from_past_record()
        )

        world_view_action = context_menu.addAction("分析")
        world_view_action.setToolTip('打开分析窗口')
        world_view_action.triggered.connect(
            lambda: self.analysis_past_chat()
        )


        context_menu.exec_(self.past_chat_list.viewport().mapToGlobal(position))

    #删除记录
    def delete_selected_history(self):
        """删除选中的历史记录及其对应文件"""
        # 获取当前选中的列表项
        item = self.past_chat_list.currentItem()
        if not item:
            QMessageBox.information(self, "提示", "请先选择要删除的记录")
            return

        # 安全获取文件名（防止路径注入）
        filename = os.path.basename(item.text())  # 过滤非法路径字符
        file_path = os.path.join(self.history_path, filename)

        try:
            # 尝试删除文件
            if os.path.exists(file_path):
                os.remove(file_path)
            else:
                QMessageBox.warning("错误",
                                    "文件不存在")
        except PermissionError:
            QMessageBox.critical(self, "错误", "没有文件删除权限")
            return
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除失败：{str(e)}")
            return

        # 从界面移除项
        row = self.past_chat_list.row(item)
        self.past_chat_list.takeItem(row)


    #读取过去system prompt
    def load_sys_pmt_from_past_record(self):
        # 获取当前选中的聊天记录项
        item = self.past_chat_list.currentItem()
        
        # 确保有选中的项
        if not item:
            print("No item selected.")
            return
        
        # 获取文件名并过滤非法路径字符
        filename = os.path.basename(item.text())
        
        # 构建完整的文件路径
        file_path = os.path.join(self.history_path, filename)
        
        # 确保文件存在
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return
        
        # 确保文件扩展名是 .json
        if not filename.endswith('.json'):
            print(f"Invalid file type: {filename}")
            return
        
        try:
            # 打开并读取 JSON 文件
            with open(file_path, 'r', encoding='utf-8') as file:
                past_chathistory = json.load(file)
                # 确保 chathistory 是一个列表嵌套字典的结构
                if not isinstance(self.chathistory, list) or not all(isinstance(item, dict) for item in self.chathistory):
                    print("Invalid JSON structure: Expected a list of dictionaries.")
                    return
                else:
                    self.chathistory[0]=past_chathistory[0]
                    self.sysrule=past_chathistory[0]["content"]
                    print('导入system prompt完成。\n导入长度：',len(self.chathistory[0]["content"]))

        except json.JSONDecodeError:
            print(f"Failed to decode JSON from file: {file_path}")
            self.chathistory = []
        except Exception as e:
            print(f"An error occurred: {e}")
            self.chathistory = []

    def analysis_past_chat(self):
        item = self.past_chat_list.currentItem()
        if not item:
            print("No item selected.")
            return
        filename = os.path.basename(item.text())
        
        # 构建完整的文件路径
        file_path = os.path.join(self.history_path, filename)
        self.show_analysis_window(file_path)

    #背景更新：触发线程
    def call_background_update(self):
        self._setup_bsw()
        self.background_agent.generate(
        summary_api_provider=self.back_ground_summary_provider,
        summary_model=self.back_ground_summary_model,
        image_api_provider=self.back_ground_image_provider,
        image_model=self.back_ground_image_model,
        chathistory=self.chathistory,
        background_style=self.background_style,
    )
        

    #背景更新：触发UI更新
    def update_background(self,file_path):
        self.background_image_path=os.path.join(self.application_path,file_path)
        print('update_background',file_path)
        if not file_path\
        or not os.path.isfile(self.background_image_path):
            QMessageBox.critical(
                None,
                '背景更新',
                '获取的图像路径无效',
                QMessageBox.Ok
            )

        self.switchImage(self.background_image_path)

    def _setup_bsw(self):
        do_init=False
        if not hasattr(self,'background_agent'):
            do_init=True
        elif self.background_agent.model_map!=MODEL_MAP or\
            self.background_agent.default_apis!=DEFAULT_APIS:
            do_init=True
        if do_init:
            self.background_agent=BackgroundAgent(
                    DEFAULT_APIS,#用于填入BackGroundWorker
                    MODEL_MAP,#用于填充总结模型库
                    application_path=application_path,
                )
            self.bind_background_signals()

    #背景更新：设置窗口
    def background_settings_window(self):
        """创建并显示设置子窗口，用于更新配置变量"""
        self._setup_bsw()
        params={
            'max_background_rounds':self.max_background_rounds,#更新间隔/轮次
            'max_backgound_lenth':self.max_backgound_lenth,#参考长度
            'back_ground_update_var':self.back_ground_update_var,#是否启用自动更新
            'lock_background':self.lock_background,
            'current_model':(self.back_ground_summary_provider,#提示词模型
                            self.back_ground_summary_model),
            'current_image_model':(self.back_ground_image_provider,#图像模型
                                self.back_ground_image_model),
            'background_style':self.background_style,
            'background_image_path':self.background_image_path,#当前背景图路径
        }
        self.background_agent.setup_setting_window(params)
        self.background_agent.show()
        self.background_agent.raise_()
        
    
    def bind_background_signals(self):
        # 断开所有已存在的信号连接
        if hasattr(self, '_bg_signal_connections'):
            for disconnect_func in self._bg_signal_connections:
                disconnect_func()
            self._bg_signal_connections.clear()
        else:
            self._bg_signal_connections = []

        # 重新连接所有信号并保存断开方法
        def add_connection(signal, slot):
            connection = signal.connect(slot)
            self._bg_signal_connections.append(lambda: signal.disconnect(connection))

        # 使用辅助函数添加连接
        add_connection(
            self.background_agent.setting_window.modelProviderChanged,
            lambda p: setattr(self, 'back_ground_summary_provider', p)
        )
        add_connection(
            self.background_agent.setting_window.modelChanged,
            lambda m: setattr(self, 'back_ground_summary_model', m)
        )
        add_connection(
            self.background_agent.setting_window.imageProviderChanged,
            lambda p: setattr(self, 'back_ground_image_provider', p)
        )
        add_connection(
            self.background_agent.setting_window.imageModelChanged,
            lambda m: setattr(self, 'back_ground_image_model', m)
        )
        add_connection(
            self.background_agent.setting_window.updateSettingChanged,
            lambda e: setattr(self, 'back_ground_update_var', e)
        )
        add_connection(
            self.background_agent.setting_window.updateSettingChanged,
            self.update_opti_bar
        )
        add_connection(
            self.background_agent.setting_window.updateIntervalChanged,
            lambda i: setattr(self, 'max_background_rounds', i)
        )
        add_connection(
            self.background_agent.setting_window.historyLengthChanged,
            lambda l: setattr(self, 'max_backgound_lenth', l)
        )
        add_connection(
            self.background_agent.setting_window.styleChanged,
            lambda s: setattr(self, 'background_style', s)
        )
        add_connection(
            self.background_agent.setting_window.backgroundImageChanged,
            lambda path: self.update_background(path) if path else self.update_background('background.jpg')
        )
        add_connection(
            self.background_agent.setting_window.lockBackground,
            lambda b: setattr(self, 'lock_background', b)
        )
        add_connection(
            self.background_agent.poll_success,
            lambda path: [self.update_background(path) or print(f'背景生成返回了路径，返回了{path}')] if path else [self.update_background('background.jpg'), print(f'背景生成没返回路径，返回了{path}')]
        )
   
    #背景生成器
    def show_pic_creater(self):
        pass

        #打开背景图片    
    def open_background_pic(self):
        os.startfile(os.path.join(self.application_path,self.background_image_path))

    #背景控件初始化
    def init_back_ground_label(self,path):
        # 先加载原始图片
        self.original_pixmap = QPixmap(path)

        # 实例化标签并传递原始图片
        self.target_label = AspectLabel(self.original_pixmap, self)

        # 视觉效果配置
        self.opacity_effect = QGraphicsOpacityEffect()
        self.opacity_effect.setOpacity(0.5)
        self.target_label.setGraphicsEffect(self.opacity_effect)
        
        # 布局配置
        self.main_layout.addWidget(self.target_label, 0, 0, 10, 10)


 
    #图片更换动画
    def _start_animation(self, new_pixmap):
        self.anim_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim_out.setDuration(300)
        self.anim_out.setStartValue(0.5)
        self.anim_out.setEndValue(0.0)
        self.anim_out.setEasingCurve(QEasingCurve.InOutQuad)
        self.anim_out.finished.connect(lambda: self._apply_image(new_pixmap))
        self.anim_out.start()
    def _apply_image(self, pixmap):
        self.target_label.update_icon(pixmap)
        self.anim_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim_in.setDuration(300)
        self.anim_in.setStartValue(0.0)
        self.anim_in.setEndValue(0.5)
        self.anim_in.setEasingCurve(QEasingCurve.InOutQuad)
        self.anim_in.finished.connect(self.back_animation_finished.emit)
        self.anim_in.start()
 
    #更换图片
    def switchImage(self, new_image_path):
        new_pixmap = QPixmap(new_image_path)
        self._start_animation(new_pixmap)


    #更新触发进度条
    def update_opti_bar(self,_=None):
        try:
            self.chat_opti_trigger_bar.setVisible(self.long_chat_improve_var)
            self.chat_opti_trigger_bar.setValue(self.new_chat_rounds)
            self.chat_opti_trigger_bar.setMaximum(self.max_message_rounds)
            self.Background_trigger_bar.setVisible(self.back_ground_update_var)
            self.Background_trigger_bar.setValue(self.new_background_rounds)
            self.Background_trigger_bar.setMaximum(self.max_background_rounds)
            self.cancel_trigger_background_update.setVisible(self.back_ground_update_var)
            self.cancel_trigger_chat_opti.setVisible(self.long_chat_improve_var)
            if self.new_chat_rounds>=self.max_message_rounds:
                self.chat_opti_trigger_bar.setFormat(f'对话优化: 即将触发')
            else:
                self.chat_opti_trigger_bar.setFormat(f'对话优化: {self.new_chat_rounds}/{self.max_message_rounds}')
            if self.new_background_rounds>=self.max_background_rounds:
                self.Background_trigger_bar.setFormat(f'背景更新: 即将触发')
            else:
                self.Background_trigger_bar.setFormat(f'背景更新: {self.new_background_rounds}/{self.max_background_rounds}')
            self.opti_frame.setVisible(self.long_chat_improve_var or self.back_ground_update_var)
        except Exception as e:
            print("Setting up process bar,ignore if first set up:",e)

    #联网搜索结果窗口
    def handle_search_result_button_toggle(self):
        if not hasattr(self, 'web_searcher'):
            self.web_searcher=WebSearchSettingWindows(MODEL_MAP,DEFAULT_APIS)
        if self.search_result_button.isChecked():
            self.web_searcher.search_results_widget.show()
            self.search_result_label.show()
            self.main_layout.addWidget(self.display_full_chat_history, 2, 4, 1, 1)
            self.main_layout.addWidget(self.chat_history_label, 2, 3, 1, 1)
            self.main_layout.addWidget(self.chat_history_bubbles, 3, 3, 4, 3)
            self.main_layout.addWidget(self.search_result_label, 2, 2, 1, 1)
            if self.think_text_box.isVisible():
                self.main_layout.addWidget(self.web_searcher.search_results_widget,3, 2, 2, 1)
                self.main_layout.addWidget(self.ai_think_label, 5, 2, 1,1)
                self.main_layout.addWidget(self.think_text_box, 6, 2, 2,1)
            else:
                self.main_layout.addWidget(self.web_searcher.search_results_widget,3, 2, 4, 1)
                self.main_layout.setColumnStretch(0, 1)
            if self.hide_extra_items.isChecked():
                self.main_layout.setColumnStretch(2, 2)
                WindowAnimator.animate_resize(self, QSize(self.width(),self.height()), QSize(int(self.width()*2),self.height()))

        else:
            self.web_searcher.search_results_widget.hide()
            self.search_result_label.hide()
            if self.think_text_box.isVisible():
                self.main_layout.addWidget(self.ai_think_label, 2, 2, 1,1)
                self.main_layout.addWidget(self.think_text_box, 3, 2, 4,1)
            else:
                self.main_layout.addWidget(self.display_full_chat_history, 2, 4, 1, 1)
                self.main_layout.addWidget(self.chat_history_label, 2, 2, 1, 1)
                self.main_layout.addWidget(self.chat_history_bubbles, 3, 2, 4, 3)
            if self.hide_extra_items.isChecked():
                self.main_layout.setColumnStretch(2, 0)
                WindowAnimator.animate_resize(self, QSize(self.width(),self.height()), QSize(int(self.width()/2),self.height()))

    #联网搜索设置窗口
    def open_web_search_setting_window(self):
        self.web_searcher.search_settings_widget.show()

    #极简界面
    def handle_hide_extra_items_toggle(self):
        if self.hide_extra_items.isChecked():
            self.chat_history_label .hide()
            self.chat_history_bubbles  .hide()
            self.bubble_background  .hide()
            self.main_layout.setColumnStretch(0, 1)
            self.main_layout.setColumnStretch(1, 1)
            self.main_layout.setColumnStretch(2, 0)
            self.main_layout.setColumnStretch(3, 0)
            WindowAnimator.animate_resize(self, QSize(self.width(),self.height()), QSize(int(self.height()/2),self.height()-100))
        else:
            self.chat_history_label     .show()
            self.chat_history_bubbles   .show()
            self.bubble_background      .show()
            self.main_layout.setColumnStretch(0, 1)
            self.main_layout.setColumnStretch(1, 1)
            self.main_layout.setColumnStretch(2, 1)
            self.main_layout.setColumnStretch(3, 1)
            WindowAnimator.animate_resize(self, QSize(self.width(),self.height()), QSize(int(self.height()*1.7),self.height()+100))

    def handel_web_search_button_toggled(self,checked):
        self.web_search_enabled = checked
        if self.web_search_enabled:
            self.search_result_button.show()
        else:
            self.search_result_button.setChecked(False)
            self.handle_search_result_button_toggle()
            self.search_result_button.hide()
            self.web_searcher.search_results_widget.hide()
            self.search_result_label.hide()

    #长对话/背景更新启用时的消息回退
    def handel_call_back_to_lci_bgu(self):
        '''长对话/背景更新启用时的消息回退'''
        handlers = [
            (self.long_chat_improve_var, 'new_chat_rounds'),
            (self.back_ground_update_var, 'new_background_rounds'),
        ]
        
        for condition, attr in handlers:
            if condition:
                current = getattr(self, attr)
                setattr(self, attr, max(0, current - 2))
        self.update_opti_bar()
        
    def show_theme_settings(self):
        self.theme_selector.hide()
        self.theme_selector.show()

    def show_concurrent_model(self,show=False):
        if not getattr(self,"concurrent_model",None):
            self.concurrent_model=ConvergenceDialogueOptiProcessor()
        if show:
            self.concurrent_model.show()
        else:
            self.concurrent_model.hide()

    def show_analysis_window(self,data=None):
        if not data:
            data=self.chathistory
        if not hasattr(self,'token_analyzer'):
            self.token_analyzer=TokenAnalysisWidget()
        self.token_analyzer.show()
        self.token_analyzer.raise_()
        self.token_analyzer.activateWindow()
        self.token_analyzer.set_data(data)

    # 0.24.4 模型并发信号
    def concurrentor_content_receive(self,msg_id,content):
        self.full_response=content
        self.update_ai_response_text(msg_id,content)

    def concurrentor_reasoning_receive(self,msg_id,content):
        self.think_response=content
        self.thinked=True
        self.update_think_response_text(msg_id,content)

    def concurrentor_finish_receive(self,msg_id,content):
        self.last_chat_info = self.concurrent_model.get_concurrentor_info()
        self.full_response=content
        self.receive_message(msg_id,content)

    # 0.25.1 avatar
    # 显示头像窗口
    def show_avatar_window(self,msg_id,name):
        do_init=False
        if (not hasattr(self,'avatar_creator')):
            do_init=True
        elif self.avatar_creator.avatar_info['user']!=self.name_user or\
        self.avatar_creator.avatar_info['assistant']:
            do_init=True
        avatar_info={'user':{'name':self.name_user,'image':self.avatar_user},
                    'assistant':{'name':self.name_ai,'image':self.avatar_ai},
                    }
        if do_init:
            self.avatar_creator=AvatarCreatorWindow(
                avatar_info=avatar_info,
                application_path=self.application_path,
                init_character={'lock':not msg_id,'character':name},
                model_map=MODEL_MAP,#逆天全局变量
                default_apis=DEFAULT_APIS,
                msg_id=msg_id,
                chathistory=self.chathistory
                )
            self.avatar_creator.avatarCreated.connect(self.chat_history_bubbles.set_role_avatar)
            self.avatar_creator.avatarCreated.connect(self.update_avatar_to_system_prompt)
        self.avatar_creator.character_for.setCurrentText(avatar_info[name]['name'])
        self.avatar_creator.chathistory=self.chathistory
        self.avatar_creator.show()
        self.avatar_creator.raise_()
    
    # 头像和历史记录同步更新
    def update_avatar_to_system_prompt(self,name,path):
        if not 'info' in self.chathistory[0]:
            self.chathistory[0]['info']={"id":999999}#999999固定分配系统提示
        if not 'avatar' in self.chathistory[0]['info']:
            self.chathistory[0]['info']['avatar']={'user':'','assistant':''}#path
        self.chathistory[0]['info']['avatar'][name]=path
    
    #头像注入气泡
    def update_avatar_to_chat_bubbles(self):
        if 'avatar' in self.chathistory[0]['info']:
            self.chat_history_bubbles.avatars=self.chathistory[0]['info']['avatar']
        else:
            self.chat_history_bubbles.avatars={'user':'','assistant':''}
        self.chat_history_bubbles.update_all_avatars()

    #气泡名称更新
    def update_name_to_chatbubbles(self):
        self.chat_history_bubbles.nicknames={'user': self.name_user, 'assistant': self.name_ai}
        self.chat_history_bubbles.update_all_nicknames()

    #名称注入历史记录
    def init_name_to_history(self):
        self.chathistory[0]['info']['name']={
            'user':self.name_user,
            'assistant':self.name_ai
        }

    
    #默认头像，用于后续指定
    def init_avartor_to_history(self):#等一个默认路径
        self.chathistory[0]['info']['avatar']={
            'user':'',
            'assistant':''
        }
    
    #创建新消息
    def creat_new_chathistory(self):
        self.sysrule=self.init_sysrule()
        self.chathistory = []
        self.chathistory.append(
            {
            'role': 'system', 
            'content': self.sysrule,
            'info':{
                'id':999999,
                'name':{'user':self.name_user,'assistant':self.name_ai},
                'avatar':{'user':'','assistant':''},
                }
            }
        )
        self.init_name_to_history()

print(f'Chatapi Main window Class import finished, time cost:{time.time()-start_time_stamp:.2f}s')

def start():
    app = QApplication(sys.argv)
    if sys.platform == 'win32':
        appid = 'chatapi.0.25.1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
    window = MainWindow()
    window.show()
    print(f'Chatapi Main window shown on desktop, time cost:{time.time()-start_time_stamp:.2f}s')
    sys.exit(app.exec_())

if __name__=="__main__":
    start()
