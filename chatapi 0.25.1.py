import base64
import concurrent.futures
import configparser
import copy
import ctypes
from collections import deque
from io import BytesIO
import json
import html
import os
import queue
import re
import sys
import threading
import time
import difflib
import random
from typing import Any, Dict, List, Tuple,Optional
from urllib.parse import quote
import urllib
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message="libpng warning: iCCP: known incorrect sRGB profile")
print("import_done")
def install_packages():
    import subprocess
    import tkinter as tk
    from tkinter import messagebox
    # 定义需要安装的模块
    packages = [
        "requests",
        "openai",
        "pyqt5",
        'beautifulsoup4',
        'lxml',
        'pygments',
        'markdown',
        'jsonfinder'
    ]

    # 过滤掉标准库模块
    packages_to_install = [pkg for pkg in packages if pkg not in sys.builtin_module_names]

    # 提示用户需要安装的模块，并询问是否继续
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    response = messagebox.askyesno("初始化", f"需要向程序库安装 {packages_to_install}，是否继续？")

    if not response:
        messagebox.showinfo("操作取消", "用户选择取消安装，程序将退出。")
        # 用户拒绝安装，终止程序
        sys.exit(0)

    # 使用 pip 安装模块
    for package in packages_to_install:
        try:
            print(f"正在安装 {package}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package, 
                                       "--index-url", "https://mirrors.aliyun.com/pypi/simple/"])
                print(f"{package} 安装成功！")
            except:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        except subprocess.CalledProcessError as e:
            messagebox.showerror("错误", f"安装 {package} 时出错: {e}")
            print(f"安装 {package} 时出错: {e}")
    messagebox.showinfo("提示", "程序初始化完成！")

def delete_directory(dir_path):
    """递归删除目录及其所有内容（仅使用 os 模块）"""
    if not os.path.exists(dir_path):
        return
    
    # 先删除目录中的所有文件和子目录
    for entry in os.listdir(dir_path):
        full_path = os.path.join(dir_path, entry)
        
        if os.path.isdir(full_path) and not os.path.islink(full_path):
            # 递归删除子目录
            delete_directory(full_path)
        else:
            # 删除文件或符号链接
            try:
                os.remove(full_path)
            except:
                pass  # 忽略删除错误
    
    # 当目录为空时，删除该目录
    try:
        os.rmdir(dir_path)
    except:
        pass  # 忽略删除错误

try:    
    from PyQt5.QtWidgets import *
    from PyQt5.QtCore import *
    from PyQt5.QtGui import *
    from PyQt5.QtSvg import *
    import openai, requests
    from requests.adapters import HTTPAdapter
    from requests.exceptions import RequestException
    from lxml import etree
    from bs4 import BeautifulSoup
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name
    from pygments.formatters import HtmlFormatter
    import markdown
    import jsonfinder
except ImportError:
    install_packages()
finally:
    try:
        from PyQt5.QtWidgets import *
        from PyQt5.QtCore import *
        from PyQt5.QtGui import *
        from PyQt5.QtSvg import *
        import openai, requests
        from requests.adapters import HTTPAdapter
        from requests.exceptions import RequestException
        from lxml import etree
        from bs4 import BeautifulSoup
        from pygments import highlight
        from pygments.lexers import get_lexer_by_name
        from pygments.formatters import HtmlFormatter
        import markdown
    except:
        import tkinter as tk
        from tkinter import messagebox
        messagebox.showinfo("提示", "导入失败，检查支持库完整性。")
        sys.exit(0)

#自定义类初始化
from utils.custom_widget import *
from utils.system_prompt_updater import SystemPromptUI
from utils.settings import *
from utils.model_map_manager import ModelMapManager
from utils.novita_model_manager import NovitaModelManager
from utils.theme_manager import ThemeSelector
from utils.function_manager import *
from utils.concurrentor import ConvergenceDialogueOptiProcessor

#自定义插件初始化
try:
    #from mods.GptToCad import CADCommandProcessor
    #global cad_processor
    #cad_processor = CADCommandProcessor()
    pass
except ImportError:
    print("GptToCad模块导入失败，CAD功能不可用。")

try:
    from mods.chatapi_tts import TTSWindow
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
NOVITA_MODEL_OPTIONS = NovitaModelManager().get_model_options()
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
    
    #QMessageBox.warning(None, "注意", "首次启动需要先填写API")
    return {k: [v["url"], v["key"]] for k, v in DEFAULT_APIS.items()}

def _read_existing_config():
    """读取已存在的配置文件"""
    config = configparser.ConfigParser()
    api_data = {}
    
    try:
        if not config.read(API_CONFIG_FILE):
            raise FileNotFoundError
        
        for api_name in DEFAULT_APIS.keys():
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
        #QMessageBox.warning(None, "配置错误", f"配置文件损坏或不存在：{str(e)}")
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
if True:
    setting_img_base64='''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'''

    setting_img = base64.b64decode(setting_img_base64)

    think_img_base64='''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'''

    think_img = base64.b64decode(think_img_base64)

    none_img_base64='iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAAVSURBVBhXY/z//z8DAwMTEDMwMAAAJAYDAbrboo8AAAAASUVORK5CYII='

    none_img= base64.b64decode(none_img_base64)

    MAIN_ICON= b'<svg t="1741501269002" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="11664" width="200" height="200"><path d="M920.642991 1.684336h-583.775701c-48.08972 0-87.327103 39.428785-87.327103 87.738617v88.217122H103.596262c-48.328972 0-87.566355 39.419215-87.566355 87.977869V675.935701c0 48.558654 39.237383 87.977869 87.566355 87.977869H133.024299v229.31858a28.901682 28.901682 0 0 0 18.42243 27.159925c3.588785 1.435514 7.17757 2.162841 10.766355 2.162841a29.284486 29.284486 0 0 0 21.293458-9.129869L418.691589 763.674318h268.201869c23.685981 0 44.740187-10.335701 60.770093-26.202916l93.069159 98.552822c5.742056 6.010019 13.398131 9.139439 21.293458 9.13944 3.588785 0 7.17757-0.727327 10.766355-2.162842a29.265346 29.265346 0 0 0 18.42243-27.169495V587.718579H920.642991c48.08972 0 87.327103-39.428785 87.327102-87.738616v-410.55701C1007.730841 41.103551 968.73271 1.684336 920.642991 1.684336zM686.893458 705.019215h-281.839252c-9.809346 0-18.183178 5.292262-23.446729 12.737794L191.401869 919.437159V735.547813c0-0.239252-0.239252-0.478505-0.239252-0.717757 0-0.239252 0.239252-0.478505 0.239252-0.727327 0-16.096897-13.158879-29.322766-29.188785-29.322766H103.596262c-16.029907 0-29.188785-13.216299-29.188785-29.322767V265.617944c0-16.106467 13.158879-29.332336 29.188785-29.332337h145.943925v263.943178c0 48.309832 39.237383 87.729047 87.327103 87.729047h269.876635l101.442991 107.453009c-5.502804 5.761196-12.919626 9.608374-21.293458 9.608374z m262.699065-204.8c0 16.106467-12.919626 29.093084-28.949532 29.093084h-58.616823c-16.029907 0-29.188785 13.206729-29.188785 29.322766v183.889346l-192.358878-204.082243-0.239253-0.239252c-1.914019-1.923589-4.06729-3.129421-6.459813-4.564935-0.957009-0.727327-1.914019-1.684336-3.11028-1.923588-0.957009-0.478505-1.914019-0.239252-2.871028-0.727328a24.757832 24.757832 0 0 0-8.373832-1.684336H336.86729a28.968673 28.968673 0 0 1-28.949533-29.083514V89.422953c0-16.106467 12.919626-29.093084 28.949533-29.093084h583.775701a28.968673 28.968673 0 0 1 28.949532 29.093084v410.796262z" fill="#2E323F" p-id="11665"></path></svg>'
    if not os.path.exists('background.jpg'):
        with open('background.jpg', 'wb') as f:
            f.write(think_img)
# 全局变量
application_path = None
temp_path = None
api = api_init()
user_input = ''
# 初始化聊天历史
pause_flag = False  # 暂停标志变量，默认为 False（未暂停）

class ModelListUpdater:
    _lock = threading.Lock()

    @staticmethod
    def _read_api_config():
        """读取api_config.ini文件并返回配置字典"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "api_config.ini")
        
        if not os.path.exists(config_path):
            print(f"配置文件不存在: {config_path}")
            return {}

        config = configparser.ConfigParser()
        config.read(config_path)
        
        api_configs = {}
        for section in config.sections():
            try:
                url = config.get(section, "url").strip()
                key = config.get(section, "key").strip()
                api_configs[section] = {"url": url, "key": key}
            except (configparser.NoOptionError, configparser.NoSectionError) as e:
                print(f"配置解析错误[{section}]: {str(e)}")
        
        return api_configs

    @staticmethod
    def _correct_url(url: str) -> str:
        """修正URL，确保以/models结尾"""
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.rstrip('/')
        
        # 如果路径不以/models结尾，则添加
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
    def update_model_map(update_ollama=False):
        """从api_config.ini读取配置并发更新模型数据"""
        global MODEL_MAP
        
        # 读取INI配置文件
        api_configs = ModelListUpdater._read_api_config()
        if not api_configs:
            print("无有效API配置，跳过更新")
            return
        
        # 动态处理Ollama配置
        if not update_ollama and "ollama" in api_configs:
            del api_configs["ollama"]
            print("跳过ollama更新")

        threads = []
        for platform, config in api_configs.items():
            # 修正URL（特殊处理百度）
            corrected_config = {
                "url": ModelListUpdater._correct_url(config["url"]),
                "key": config["key"]
            }
            
            thread = threading.Thread(
                target=ModelListUpdater._update_platform_models,
                args=(platform, corrected_config)
            )
            thread.start()
            threads.append(thread)
        
        for thread in threads:
            thread.join()

    @staticmethod
    def _update_platform_models(platform: str, platform_config: dict):
        """单个平台的模型更新逻辑"""
        try:
            # 使用新的get_model_list函数
            models = ModelListUpdater.get_model_list(platform_config)
            
            if models:
                models.sort()  # 排序以便后续处理
                with ModelListUpdater._lock:  # 加锁操作共享数据
                    # 获取该平台现有的模型列表
                    existing = set(MODEL_MAP.get(platform, []))
                    # 找出新模型
                    new_models = [m for m in models if m not in existing]
                    
                    if new_models:
                        # 如果platform键不存在，会自动创建空列表
                        MODEL_MAP.setdefault(platform, []).extend(new_models)
                        print(f"[{platform}] 新增 {len(new_models)} 模型")
                    else:
                        print(f"[{platform}] 无新模型")
            else:
                print(f"[{platform}] 响应数据为空")
        except Exception as e:
            print(f"[{platform}] 更新失败: {str(e)}")

    @staticmethod
    def is_ollama_alive(url='http://localhost:11434/'):
        """
        检查Ollama服务是否存活
        
        :return: 如果Ollama服务存活，返回True；否则返回False
        """
        try:
            corrected_url = urllib.parse.urljoin(url, 'api/tags')
            # 使用较短的超时时间，避免长时间阻塞
            response = requests.get(corrected_url, timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    @staticmethod
    def get_model_list(platform):
        """获取指定平台的模型ID列表
        
        Args:
            platform (dict): 平台配置信息，包含url和key
            
        Returns:
            list: 模型ID的列表，如 ["model1", "model2"]
        """
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {platform["key"]}'
        }
        
        try:
            response = requests.get(platform["url"], headers=headers)
            response.raise_for_status()  # 检查HTTP错误
            
            data = response.json()
            
            # 提取模型ID列表
            if 'data' in data:
                return [model['id'] for model in data['data']]
            else:
                print(f"返回数据中缺少'data'字段: {data}")
                return []
                
        except requests.exceptions.RequestException as e:
            print(f"请求失败: {e}")
            return []
        except json.JSONDecodeError:
            print("返回的不是有效JSON格式")
            return []

    @staticmethod
    def update():
        """更新所有API平台的模型列表"""
        ollama_alive = ModelListUpdater.is_ollama_alive()
        print(f"Ollama服务状态: {'存活' if ollama_alive else '未启动'}")
        ModelListUpdater.update_model_map(update_ollama=ollama_alive)
    

#路径初始化
if getattr(sys, 'frozen', False):
    # 打包后的程序
    application_path = os.path.dirname(sys.executable)
    temp_path = sys._MEIPASS
else:
    # 普通 Python 脚本
    application_path = os.path.dirname(os.path.abspath(__file__))

##支持类
#Novita Api 下的图像生成
class NovitaImageGenerator:
    def __init__(self, api_key):
        self.base_url = "https://api.novita.ai/v3/"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        # 确保图片目录存在
        os.makedirs("pics", exist_ok=True)
        
    def _save_image(self, url, filename):
        """保存图片到指定目录"""
        filepath = os.path.join("pics", filename)
        response = requests.get(url)
        if response.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(response.content)
            print(f"图片已保存为 {filepath}")
            return filepath
        print(f"下载失败，状态码：{response.status_code}")
        return None

    def generate(self, prompt, model_name, negative_prompt, 
                width=512, height=512, image_num=1, steps=20,
                seed=-1, clip_skip=1, sampler_name="Euler a",
                guidance_scale=7.5):
        """生成图片请求"""
        data = {
            "extra": {
                "response_image_type": "jpeg",
                "enable_nsfw_detection": False,
                "nsfw_detection_level": 2
            },
            "request": {
                "prompt": prompt,
                "model_name": model_name,
                "negative_prompt": negative_prompt,
                "width": width,
                "height": height,
                "image_num": image_num,
                "steps": steps,
                "seed": seed,
                "clip_skip": clip_skip,
                "sampler_name": sampler_name,
                "guidance_scale": guidance_scale
            }
        }
        
        response = requests.post(
            f"{self.base_url}async/txt2img",
            headers=self.headers,
            json=data  # 使用json参数自动处理序列化和Content-Type
        )
        
        if response.status_code != 200:
            print(f"请求失败，状态码：{response.status_code}")
            return None
            
        return response.json().get('task_id')

    def poll_result(self, task_id, timeout=600, interval=5):
        """轮询任务结果并返回图片路径"""
        start_time = time.time()
        print(f"开始轮询任务 {task_id}...")

        while True:
            # 超时检查
            if time.time() - start_time > timeout:
                print("请求超时")
                return None

            # 间隔轮询
            time.sleep(interval)
            
            # 查询任务状态
            try:
                response = requests.get(
                   f"{self.base_url}async/task-result",
                   params={"task_id": task_id},  # 更规范的参数传递方式
                   headers=self.headers
                )
                response.raise_for_status()  # 自动抛出HTTP错误
            except requests.exceptions.RequestException as e:
                print(f"请求异常: {str(e)}")
                continue

            data = response.json()
            status = data['task']['status']

            # 处理任务状态
            if status == 'TASK_STATUS_SUCCEED':
                if data.get('images'):
                   image_url = data['images'][0]['image_url']
                   return self._save_image(image_url, f"{task_id}.jpg")
                print("任务成功但未返回图片")
                return None
            elif status == 'TASK_STATUS_FAILED':
                print(f"任务执行失败: {data['task']['reason']}")
                return None

#爬虫组件
class bing_search:
    def __init__(self):
        self.BING_SEARCH_URL = "https://www.bing.com/search?q="
    def get_search_results(self,query: str) -> List[Dict[str, Any]]:
        session = requests.Session()
        # 重试机制
        adapter = HTTPAdapter(max_retries=3)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
    
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0'
        }
        
        try:
            response = session.get(self.BING_SEARCH_URL + quote(query)+'&ensearch=1', headers=headers, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'  # 确保使用正确的编码
        except RequestException as e:
            return []
    
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        # 处理普通搜索结果
        for result in soup.select('#b_results .b_algo'):
            link_tag = result.find('a', class_='tilk')
            title_tag = result.find('h2')
            content_tag = result.find('p')
            
            link = link_tag.get('href') if link_tag else ''
            title = title_tag.get_text(strip=True) if title_tag else ''
            content = content_tag.get_text(strip=True) if content_tag else ''
            
            if link and title and content:
                results.append({
                    'title': title,
                    'link': link,
                    'content': content
                })
    
        # 处理新闻结果
        for news in soup.select('.b_nwsAns'):
            link_tag = news.find('a', class_='itm_link')
            title_tag = news.find(class_='na_t_news_caption')
            content_tag = news.find(class_='itm_spt_news_caption')
            
            link = link_tag.get('href') if link_tag else ''
            title = title_tag.get_text(strip=True) if title_tag else ''
            content = content_tag.get_text(strip=True) if content_tag else ''
            
            if link and title and content:
                results.append({
                    'title': title,
                    'link': link,
                    'content': content,
                    '_source': 'Bing News'
                })
        for img in soup.select('.imgpt'):
            img_link = img.find('a', class_='iusc')
            img_meta = img.find('div', class_='img_info')
            img_tag = img.find('img')
            
            # 解析JSON数据获取高清图片URL
            if img_link and 'm' in img_link.attrs:
                import json
                try:
                    img_data = json.loads(img_link['m'])
                    full_size_url = img_data.get('murl', '')
                except:
                    full_size_url = ''
            
            results.append({
                'title': img_tag.get('alt', '') if img_tag else '',
                'link': full_size_url,
                'thumbnail': img_tag.get('src', '') if img_tag else '',
                'dimensions': img_meta.get_text(' ') if img_meta else '',
                '_source': 'Bing Images'
            })
        
        
        # 知识面板
        knowledge_panel = soup.find('div', class_='b_knowledge')
        if knowledge_panel:
            title_tag = knowledge_panel.find('h2')
            content_tag = knowledge_panel.find('div', class_='b_snippet')
            
            results.append({
                'title': title_tag.get_text(strip=True) if title_tag else '',
                'content': content_tag.get_text(strip=True) if content_tag else '',
                '_source': 'Bing Knowledge'
            })
        
        # 相关搜索
        for related in soup.select('.b_rs'):
            related_link = related.find('a')
            results.append({
                'query': related_link.get_text(strip=True),
                'link': related_link.get('href'),
                '_source': 'Bing Related'
            })
        return results
class baidu_search:
    def __init__(self):
        self.TOTAL_SEARCH_RESULTS = 10  # 假设默认搜索结果数量

    def clean_url(self,url: str) -> str:
        """清理 URL 结尾的斜杠"""
        return url.rstrip('/')

    def get_search_results(self,query: str) -> List[Dict]:
        """本地百度搜索实现"""
        try:
            url = f"https://www.baidu.com/s?wd={quote(query)}&tn=json&rn={self.TOTAL_SEARCH_RESULTS}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            entries = data.get("feed", {}).get("entry", [])
            
            results = []
            for entry in entries:
                result = {
                    "title": entry.get("title", ""),
                    "link": entry.get("url", ""),
                    "content": entry.get("abs", "")
                }
                if result["link"]:
                    results.append(result)
                    
            return results
        
        except Exception as e:
            print(f"Search error: {e}")
            return []
class WebScraper:
    def __init__(self):
        # 初始化一个requests的Session对象，方便管理请求
        self.session = requests.Session()

    def fetch_response(self, url):
        """
        发送HTTP GET请求并返回响应内容。
        """
        try:
            response = self.session.get(url)
            response.raise_for_status()  # 检查请求是否成功
            return response
        except requests.exceptions.RequestException as e:
            print(f"请求出现错误: {e}")
            return None
 
    def extract_link_from_script(self, html_content):
        """
        从HTML内容中提取<script>标签中嵌入的链接。
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        script_content = soup.find('script').string  # 假设目标链接在第一个<script>标签中

        if not script_content:
            print("未找到<script>标签内容")
            return None

        # 使用正则表达式查找链接
        pattern = r'var u = "(https?://[^"]+)";'
        match = re.search(pattern, script_content)

        if match:
            link = match.group(1)
            print("已提取链接")
            return link
        else:
            print("未找到链接")
            return None

    def get_webpage_content(self, url):
        """
        获取网页的主要文本内容。
        """
        try:
            response = self.session.get(url)
            response.raise_for_status()  # 检查请求是否成功

            # 解析HTML内容
            
            try:
                html = response.text
                html = html.encode("ISO-8859-1")
                html = html.decode("utf-8")
                
                # 解析HTML
                tree = etree.HTML(html)
                body_text = tree.xpath('//body//text()')
                full_text = ' '.join(body_text)
            except Exception as e:
                try:
                    html = response.text
                    html = html.encode("gb2312")
                    html = html.decode("utf-8")
                    
                    # 解析HTML
                    tree = etree.HTML(html)
                    body_text = tree.xpath('//body//text()')
                    full_text = ' '.join(body_text)
                except:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    full_text = soup.body.get_text(strip=True)
            # 提取网页正文内容
            
            return full_text

        except Exception as e:
            print(f"请求出现错误: {e}")
            return None

    def run(self, initial_url):
        """
        主流程逻辑：从初始URL中提取目标链接，并获取目标网页内容。
        """
        # Step 1: 获取初始URL的响应
        response = self.fetch_response(initial_url)
        if not response:
            print("无法获取初始URL的响应")
            return None

        # Step 2: 从响应HTML中提取链接
        if 'bing' in initial_url:
            link = self.extract_link_from_script(response.text)
        else:
            print('链接地址获取完成')
            return response.text
        if not link :
            print("无法提取链接，流程终止")
            return None
        
        # Step 3: 获取提取链接对应网页的内容
        content = self.get_webpage_content(link)
        if content:
            print("目标网页内容提取成功:")
            return content
        else:
            print("目标网页内容提取失败")
            return None
class WebSearchTool:
    def __init__(self, search_engine, scraper):
        """
        初始化工具类。
        
        :param search_engine: 搜索引擎实例，需要实现 `get_search_results(query)` 方法。
        :param scraper: 网页抓取器实例，需要实现 `run(url)` 方法。
        """
        self.search_engine = search_engine
        self.scraper = scraper
        self.search_results = {}
        self.query=''
 
    def search_and_scrape(self, query):
        """
        使用多线程执行搜索和抓取操作。
        
        :param query: 搜索查询字符串。
        :return: 格式化后的搜索结果字符串。
        """
        # 获取搜索结果
        self.query=query
        results = self.search_engine.get_search_results(query)
        
        # 创建线程安全的队列和锁
        task_queue = queue.Queue()

        # 准备队列任务（添加索引i保持顺序）
        for i, result in enumerate(results, start=1):
            task_queue.put((i, result))

        # 定义工作线程函数
        def worker():
            while True:
                try:
                    # 获取任务（非阻塞方式）
                    i, result = task_queue.get(block=False)
                    link = result.get("link")
                    content = self.scraper.run(link)

                    if content:
                        # 线程安全的打印操作

                        # 直接按索引存储结果（天然线程安全，因为i是唯一的）
                        self.search_results[i] = {
                            "title": result.get("title", "No Title"),
                            "link": link,
                            "abstract": result.get("content", "No Abstract"),
                            "content": content
                        }
                    else:
                        self.search_results[i] = {
                            "title": result.get("title", "No Title"),
                            "link": link,
                            "abstract": result.get("content", "No Abstract"),
                            "content": result.get("content", "No Abstract")
                        }
                    
                    # 标记任务完成
                    task_queue.task_done()
                except queue.Empty:
                    break

        # 创建并启动工作线程
        threads = []
        for _ in range(5):
            t = threading.Thread(target=worker)
            t.start()
            threads.append(t)

        # 等待所有任务完成
        task_queue.join()

        # 等待所有线程结束
        for t in threads:
            t.join()
        sorted_results = {k: self.search_results[k] for k in sorted(self.search_results)}
        self.search_results=sorted_results
        return self.search_results
 
    def format_results(self,abstracter=True,useable_list=[]):
        """
        格式化搜索结果。
        
        :return: 格式化后的搜索结果字符串。
        """
        web_reference = ''
        for key, value in self.search_results.items():
            if not key in useable_list and not abstracter:
                continue
            web_reference += '\n Result ' + str(key)
            web_reference += '\n Title: ' +value['title']
            web_reference += '\n Link: ' +value['link']
            if abstracter:
                web_reference += '\n Abstract: ' + value['abstract']
            elif len(value['content'])<10000 :
                web_reference += '\n content: ' + value['content']

            web_reference += '\n' + ("-" * 10)
        if len(str(web_reference))<15000:
            return web_reference
        else:
            return str(web_reference)[:12000]

    def online_rag(self,api_key,rag_provider_link,rag_model):
        def extract_all_json(ai_response):
            json_pattern = r'\{[\s\S]*?\}'
            matches = re.findall(json_pattern, ai_response)
            
            valid_json_objects = []
            for match in matches:
                try:
                    json_obj = json.loads(match)
                    valid_json_objects.append(json_obj)
                except json.JSONDecodeError:
                    continue
            
            if valid_json_objects:
                return valid_json_objects
            else:
                print("未找到有效的JSON部分")
                print(ai_response)
                return None
        if self.search_results == {}:
            print("no search results,returning None")
            return None
        client = openai.Client(
            api_key=api_key,  # 替换为实际的 API 密钥
            base_url=rag_provider_link  # 替换为实际的 API 基础 URL
        )
        user_input='''请提取出提交的网页摘要中符合问题："'''+self.query+'''"的条目编号。
如果当前提供的网页摘要能够详细、准确地回答问题，则按以下格式回答：
{"enough_intel": "True",
"useful_result":[1,2,3]}#举例，按请求中的编号填写
如果当前提供的网页摘要不能详细回答问题，但有完全访问后可能有帮助的条目，按以下格式回答：
{"enough_intel": "False",
"useful_result":[1,2,3]}#举例，按请求中的编号填写
如果当前提供的网页摘要与要求无关，useful_result返回空列表。
如果不能处理,enough_intel返回false,useful_result返回空列表。
'''+self.format_results()
        message=[{"role":"user","content":user_input}]
        print(user_input)
        params={'model':rag_model,
                'messages':message,
                'stream':False,  # 设置为 True 可启用流式输出
                'temperature':0
            }
        try:
            response = client.chat.completions.create(**params)
            return_message = response.choices[0].message.content
            result=extract_all_json(return_message)
            print(result)
            if not result:
                return 'Result: Rag模型报告没有有效的搜索结果'
            if result[0]["enough_intel"]==True or result[0]["enough_intel"]=='True':
                return self.format_results(abstracter=True)
            elif result[0]["enough_intel"]==False or result[0]["enough_intel"]=='False':
                return self.format_results(abstracter=False,useable_list=result[0]["useful_result"])
            elif (result[0]["enough_intel"]==False or result[0]["enough_intel"]=='False') and result[0]["useful_result"]=='':
                return 'Result: Rag模型报告没有有效的搜索结果'

        except Exception as e:
            print(result)
            print("online rag failed,Error code:",e)
            return ''

#图片创建器
class PromptGenerationWorker(QThread):
    result_ready = pyqtSignal(str)
    
    def __init__(self, func, mode, input_text):
        super().__init__()
        self.func = func
        self.mode = mode
        self.input_text = input_text

    def run(self):
        result = self.func(mode=self.mode, pic_creater_input=self.input_text)
        self.result_ready.emit(str(result))
class NovitaAPICallWorker(QThread):
    finished = pyqtSignal()
    
    def __init__(self, main_window, return_prompt):
        super().__init__()
        self.main_window = main_window
        self.return_prompt = return_prompt

    def run(self):
        self.main_window.back_ground_update_thread_to_novita(
            return_prompt=self.return_prompt
        )
        self.finished.emit()
class PicCreaterWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window)
        self.resize(600, 400)
        self.main_window = parent
        self.setup_ui()
        
    def setup_ui(self):
        layout = QGridLayout(self)
        
        # 第一行控件
        label_desc = QLabel("文生图描述")
        layout.addWidget(label_desc, 1, 0, 1, 1)
        
        self.send_btn = QPushButton("发送")
        layout.addWidget(self.send_btn, 1, 1, 1, 1)
        
        # 第二行控件
        self.desc_input = QTextEdit()
        layout.addWidget(self.desc_input, 2, 0, 1, 2)
        
        # 第三行控件
        self.label_prompt = QLabel("生成的prompt")
        layout.addWidget(self.label_prompt, 3, 0, 1, 2)
        
        # 第四行控件
        self.ai_created_prompt = QTextBrowser()
        layout.addWidget(self.ai_created_prompt, 4, 0, 1, 2)
        self.novita_model = QComboBox()
        self.novita_model.addItems(NOVITA_MODEL_OPTIONS)
        # 设置默认选中项
        self.novita_model.setCurrentText('foddaxlPhotorealism_v45_122788.safetensors')
        self.main_window.novita_model = self.novita_model.currentText()
        layout.addWidget(self.novita_model,0,0,1,2)
        
        # 设置布局自适应
        layout.setColumnStretch(0, 3)
        layout.setColumnStretch(1, 1)
        layout.setRowStretch(1, 2)
        layout.setRowStretch(3, 2)
        
        self.send_btn.clicked.connect(self.start_background_task)


    def start_background_task(self):
        self.send_btn.setEnabled(False)
        self.ai_created_prompt.setText('已发送。等待生成。')
        self.label_prompt.setText("生成的prompt")

        if self.main_window and not hasattr(self.main_window, 'novita_model'):
            self.main_window.novita_model = self.novita_model.currentText()
        input_text = self.desc_input.toPlainText()
        self.prompt_worker = PromptGenerationWorker(
            func=self.main_window.back_ground_update_thread,
            mode='pic_creater',
            input_text=input_text
        )
        self.prompt_worker.result_ready.connect(self.handle_result)
        self.prompt_worker.start()

    def handle_result(self, return_prompt):
        # UI操作保持在主线程
        self.ai_created_prompt.setText(return_prompt)
        # 启动新的线程处理API调用
        self.api_worker = NovitaAPICallWorker(
            self.main_window, 
            return_prompt
        )
        self.api_worker.start()
        self.send_btn.setEnabled(True)
        self.label_prompt.setText("等待Novita api响应")

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

# 搜索组件
class WebSearchSettingWindows:
    def __init__(self):
        self.search_engine = "baidu"
        self.results_num=10

        self.search_queue = queue.Queue()
        
        # 初始化UI组件
        self.search_settings_widget = QWidget()
        self.search_settings_widget.setWindowTitle("搜索设置")
        self.search_results_widget = QWidget()
        #self.search_results_widget.setWindowTitle("搜索结果")
        
        self.create_search_settings()
        self.create_search_results()
        
        # 初始化工具和结果
        self.tool = None
        self.result = None
        self.finished= False
        self.search_complete_event = threading.Event()

    def create_search_settings(self):
        layout = QVBoxLayout(self.search_settings_widget)
        
        # 搜索引擎选择
        engine_label = QLabel("搜索引擎")
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["baidu", "bing"])
        self.engine_combo.setCurrentText(self.search_engine)
        layout.addWidget(engine_label)
        layout.addWidget(self.engine_combo)
        
        # 返回结果数
        result_num_label = QLabel("返回结果数")
        self.result_num_edit = QLineEdit()
        self.result_num_edit.setText('10')
        self.result_num_edit.setValidator(QIntValidator())  # 确保输入为整数
        layout.addWidget(result_num_label)
        layout.addWidget(self.result_num_edit)
        
        # RAG相关控件
        self.rag_checkbox = QCheckBox("使用RAG过滤")
        layout.addWidget(self.rag_checkbox)
        
        self.rag_provider_label = QLabel("RAG 过滤器模型提供商")
        self.rag_provider_combo = QComboBox()
        self.rag_provider_combo.addItems(MODEL_MAP.keys())
        layout.addWidget(self.rag_provider_label)
        layout.addWidget(self.rag_provider_combo)
        
        self.rag_model_label = QLabel("RAG过滤模型")
        self.rag_model_combo = QComboBox()
        self.update_rag_models()
        layout.addWidget(self.rag_model_label)
        layout.addWidget(self.rag_model_combo)
        
        # 初始隐藏RAG控件
        self.toggle_rag_controls(False)
        self.rag_checkbox.stateChanged.connect(
            lambda state: self.toggle_rag_controls(state == Qt.Checked)
        )
        
        # 确定按钮
        confirm_btn = QPushButton("确定")
        confirm_btn.clicked.connect(self.save_settings)
        layout.addWidget(confirm_btn)
        
        self.search_settings_widget.setLayout(layout)
        
        # 联动模型提供商和模型列表
        self.rag_provider_combo.currentTextChanged.connect(self.update_rag_models)


    def toggle_rag_controls(self, visible):
        """控制RAG相关控件的可见性"""
        self.rag_provider_label.setVisible(visible)
        self.rag_provider_combo.setVisible(visible)
        self.rag_model_label.setVisible(visible)
        self.rag_model_combo.setVisible(visible)

    def update_rag_models(self):
        """更新模型列表"""
        provider = self.rag_provider_combo.currentText()
        self.rag_model_combo.clear()
        self.rag_model_combo.addItems(MODEL_MAP.get(provider, []))
        
    def save_settings(self):
        """保存设置"""
        self.search_engine = self.engine_combo.currentText()
        self.results_num = int(self.result_num_edit.text() or 10)  # 默认10条
        self.search_settings_widget.hide()
        
    def create_search_results(self):
        layout = QVBoxLayout()
        self.results_list = QListWidget()
        
        # 紧凑列表样式
        self.results_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 2px;
                font-family: "Segoe UI";
                outline: 0;
            }
            QListWidget::item {
                margin: 1px;
                padding: 0;
            }
            QListWidget::item:hover {
                background: #f5f5f5;
            }
            QScrollBar:vertical {
                width: 10px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #d0d0d0;
                border-radius: 3px;
            }
        """)
        
        layout.setContentsMargins(5, 5, 5, 5)  # 减少外层边距
        layout.setSpacing(0)  # 去除布局间距
        layout.addWidget(self.results_list)
        self.search_results_widget.setLayout(layout)
        

        
    def perform_search(self, query, apikey=None):
        """执行搜索并更新结果（使用线程避免阻塞UI）"""
        # 读取当前UI参数
        self.finished=False
        self.search_complete_event.clear()
        engine = self.engine_combo.currentText()
        results_num = self.results_num
        self.current_apikey = apikey  # 保存apikey供后续使用

        # 启动后台线程执行搜索
        search_thread = threading.Thread(
            target=self._threaded_search,
            args=(query, engine, results_num),
            daemon=True
        )
        search_thread.start()

        self.result_timer = QTimer()
        self.result_timer.timeout.connect(self.check_search_result)
        self.result_timer.start(100)

        # 开始检查结果（根据GUI框架调整）
        self.check_search_result()
    
    def _threaded_search(self, query, engine, results_num):
        """后台线程执行的搜索逻辑"""
        # 根据引擎创建搜索器
        if engine == "baidu":
            searcher = baidu_search()
            searcher.TOTAL_SEARCH_RESULTS = results_num
        elif engine == "bing":
            searcher = bing_search()
        
        scraper = WebScraper()
        self.tool = WebSearchTool(searcher, scraper)
        result = self.tool.search_and_scrape(query)
        
        # 将结果放入队列
        self.search_queue.put(result)

    def check_search_result(self):
        """主线程检查结果队列"""
        try:
            # 非阻塞获取结果
            result = self.search_queue.get_nowait()
            self.result_timer.stop()  # 停止定时器
            
            # 处理RAG（在主线程操作UI组件）
            if self.rag_checkbox.isChecked() and self.current_apikey:
                rag_model = self.rag_model_combo.currentText()
                rag_link = DEFAULT_APIS[self.rag_provider_combo.currentText()]["url"]
                
                # 创建临时工具处理RAG（假设不需要搜索器/爬虫）
                self.rag_result=self.tool.online_rag(
                    self.current_apikey,
                    rag_link,
                    rag_model
                )
            
            # 更新结果并显示
            self.result = result
            self.display_results()
        except queue.Empty:
            None
            ## 根据GUI框架设置下次检查（示例使用Tkinter的after）
            #if hasattr(self, 'after'):
            #    self.after(100, self.check_search_result)

    def display_results(self):
        """展示搜索结果"""
        self.results_list.clear()
        
        # 紧凑按钮样式
        button_style = """
            QPushButton {
                background: white;
                color: #404040;
                border: 1px solid #e0e0e0;
                border-radius: 3px;
                padding: 6px 10px;
                text-align: left;
                font-size: 13px;
                margin: 1px;
                min-width: 240px;
            }
            QPushButton:hover {
                background: #f8f8f8;
                border-color: #c0c0c0;
            }
            QPushButton:pressed {
                background: #f0f0f0;
            }
        """
        
        for idx, item in enumerate(self.result.items(), start=1):
            key, value = item
            btn = QPushButton(f"{key}. {value['title']}")
            btn.setStyleSheet(button_style)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # 紧凑尺寸设置
            btn.setFixedHeight(32)  # 减少按钮高度
            btn.setIconSize(QSize(16, 16))  # 缩小图标尺寸
            
            link = value['link']
            btn.clicked.connect(lambda _, l=link: os.startfile(l))

            list_item = QListWidgetItem()
            list_item.setSizeHint(QSize(0, 34))  # 固定行高
            self.results_list.addItem(list_item)
            self.results_list.setItemWidget(list_item, btn)
        self.finished = True
        self.search_complete_event.set()

    def wait_for_search_completion(self, timeout=None):
        """轮询函数，供其他线程阻塞等待"""
        return self.search_complete_event.wait(timeout)

#api导入窗口
class APIConfigDialogUpdateModelThread(QObject):
    """模型库更新线程"""
    started_signal = pyqtSignal()
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def run(self) -> None:
        try:
            self.started_signal.emit()
            ModelListUpdater.update()
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))
class APIConfigWidget(QWidget):
    """API配置管理组件，支持多服务商配置编辑和自定义供应商"""
    
    configUpdated = pyqtSignal(dict)  # 配置更新信号
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.preset_apis = [
            "baidu", "deepseek", "siliconflow", "tencent", "novita", "ollama"
        ]
        self.custom_apis = []  # 存储自定义API名称
        self.api_widgets: Dict[str, Tuple[QLineEdit, QLineEdit]] = {}
        self.custom_group_boxes: Dict[str, QGroupBox] = {} 
        
        # 初始化UI前设置尺寸策略
        #self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self._initialize_ui()
        self.load_config()
        self.adjustSize()  # 初始调整窗口大小

        screen_geometry = QApplication.primaryScreen().availableGeometry()
        
        width = int(screen_geometry.width() * 0.4)
        height = int(screen_geometry.height() * 0.5)
        
        left = (screen_geometry.width() - width) // 2
        top = (screen_geometry.height() - height) // 2
        
        self.setGeometry(left, top, width, height)
        self.setWindowTitle("API 配置管理")

    def _initialize_ui(self) -> None:
        """初始化现代化UI界面，优化布局管理"""
        # 主布局 - 使用垂直布局并设置内容边距
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # 标题
        title_label = QLabel("API 配置管理")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        main_layout.addWidget(title_label)
        
        # 使用选项卡控件来组织预设和自定义API
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)  # 扁平化样式
        main_layout.addWidget(self.tab_widget, 1)  # 添加拉伸因子
        
        # 预设API区域
        preset_tab = QWidget()
        preset_layout = QVBoxLayout(preset_tab)
        preset_layout.setContentsMargins(0, 10, 0, 10)
        self._setup_preset_apis(preset_layout)
        self.tab_widget.addTab(preset_tab, "预设供应商")
        
        # 自定义API区域
        custom_tab = QWidget()
        self.custom_layout = QVBoxLayout(custom_tab)
        self.custom_layout.setContentsMargins(0, 10, 0, 10)
        self._setup_custom_apis()
        self.tab_widget.addTab(custom_tab, "自定义供应商")
        
        # 添加自定义API按钮
        self.add_custom_btn = QPushButton("+ 添加自定义API供应商")
        self.add_custom_btn.setFixedHeight(40)
        self.add_custom_btn.clicked.connect(self.add_custom_api)
        main_layout.addWidget(self.add_custom_btn, 0, Qt.AlignLeft)
        
        # 操作按钮区域 - 使用水平布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        button_layout.addStretch(1)
        
        self.update_btn = QPushButton("更新模型库")
        self.update_btn.setFixedHeight(40)
        self.update_btn.clicked.connect(self.on_update_models)
        button_layout.addWidget(self.update_btn)
        
        self.save_btn = QPushButton("保存所有配置")
        self.save_btn.setFixedHeight(40)
        self.save_btn.clicked.connect(self._validate_and_save)
        button_layout.addWidget(self.save_btn)
        
        main_layout.addLayout(button_layout)
        
        # 状态栏
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.status_label.setWordWrap(True)  # 支持文本换行
        main_layout.addWidget(self.status_label)
        
        # 调整大小策略
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

    def _setup_preset_apis(self, layout: QVBoxLayout) -> None:
        """设置预设API区域的布局"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        
        # 内容容器
        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        
        # 使用网格布局处理预设API
        grid_layout = QGridLayout(content_widget)
        grid_layout.setSpacing(15)
        grid_layout.setContentsMargins(10, 10, 10, 10)
        
        # 将预设API分成两列显示
        for idx, api_name in enumerate(self.preset_apis):
            group = self._create_api_group(api_name)
            row = idx // 2
            col = idx % 2
            grid_layout.addWidget(group, row, col)
        
        # 添加拉伸项使网格布局顶部对齐
        grid_layout.setRowStretch(grid_layout.rowCount(), 1)
        
        layout.addWidget(scroll_area)

    def _setup_custom_apis(self) -> None:
        """设置自定义API区域的布局-使用垂直布局而不是网格布局"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        
        # 内容容器 - 使用垂直布局
        self.custom_container = QWidget()
        self.custom_container_layout = QVBoxLayout(self.custom_container)
        self.custom_container_layout.setSpacing(15)
        self.custom_container_layout.setContentsMargins(10, 10, 10, 10)
        
        # 添加拉伸项
        self.custom_container_layout.addStretch(1)
        
        # 添加滚动区域到主布局
        scroll_area.setWidget(self.custom_container)
        self.custom_layout.addWidget(scroll_area)

    def _arrange_custom_apis(self) -> None:
        """重新排列自定义API到垂直布局中"""
        # 清除现有内容（保留布局对象）
        while self.custom_container_layout.count() > 0:
            item = self.custom_container_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
            del item
        
        # 添加所有自定义API
        for api_name in self.custom_apis:
            if api_name in self.custom_group_boxes:
                self.custom_container_layout.addWidget(self.custom_group_boxes[api_name])
        
        # 添加底部拉伸
        self.custom_container_layout.addStretch(1)

    def _create_api_group(self, api_name: str, custom: bool = False) -> QGroupBox:
        """创建API配置组，固定尺寸策略"""
        group = QGroupBox(api_name)
        group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        if custom:
            self.custom_group_boxes[api_name] = group
            
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setContentsMargins(15, 15, 15, 15)
        
        url_entry = QLineEdit()
        url_entry.setPlaceholderText("请输入API端点URL...")
        url_entry.setClearButtonEnabled(True)
        
        key_entry = QLineEdit()
        key_entry.setPlaceholderText("请输入认证密钥...")
        key_entry.setEchoMode(QLineEdit.Password)
        key_entry.setClearButtonEnabled(True)
        
        form_layout.addRow("API URL:", url_entry)
        form_layout.addRow("API 密钥:", key_entry)
        
        # 自定义API添加删除按钮
        if custom:
            del_btn = QPushButton("删除")
            del_btn.setFixedWidth(80)
            del_btn.clicked.connect(lambda: self.remove_custom_api(api_name))
            
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            btn_layout.addWidget(del_btn)
            form_layout.addRow(btn_layout)
        
        group.setLayout(form_layout)
        
        # 保存到widgets字典
        self.api_widgets[api_name] = (url_entry, key_entry)
        return group

    def add_custom_api(self) -> None:
        """添加新的自定义API供应商"""
        name, ok = QInputDialog.getText(
            self, 
            "添加自定义API供应商", 
            "请输入供应商名称:",
            text="custom_api"
        )
        
        if ok and name:
            name = name.strip()
            if not name:
                QMessageBox.warning(self, "输入错误", "供应商名称不能为空")
                return
                
            if name in self.api_widgets:
                QMessageBox.warning(self, "名称冲突", "该供应商名称已存在")
                return
                
            # 添加新的自定义API
            self.custom_apis.append(name)
            group = self._create_api_group(name, custom=True)
            self._arrange_custom_apis()  # 重新排列自定义API

    def remove_custom_api(self, api_name: str) -> None:
        """删除自定义API供应商"""
        if api_name not in self.custom_apis:
            return
            
        # 确认删除
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除'{api_name}'的配置吗?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # 从UI中移除
                if api_name in self.custom_group_boxes:
                    # 从字典中移除
                    group_box = self.custom_group_boxes.pop(api_name)
                    # 删除小部件
                    group_box.setParent(None)
                    group_box.deleteLater()
                
                # 从自定义列表中移除
                if api_name in self.custom_apis:
                    self.custom_apis.remove(api_name)
                    
                # 从widgets字典中移除
                if api_name in self.api_widgets:
                    del self.api_widgets[api_name]
                    
                # 重新排列自定义API
                self._arrange_custom_apis()
                
            except Exception as e:
                QMessageBox.critical(self, "删除错误", f"删除时发生错误: {str(e)}")


    def load_config(self) -> None:
        """从配置文件加载已有配置"""
        if not os.path.exists("api_config.ini"):
            # 使用默认配置初始化
            self._apply_config(DEFAULT_APIS)
            return
            
        config = configparser.ConfigParser()
        try:
            config.read("api_config.ini")
            
            # 处理预设API
            for api_name in self.preset_apis:
                if config.has_section(api_name):
                    url_entry, key_entry = self.api_widgets[api_name]
                    url_entry.setText(config.get(api_name, "url", fallback=""))
                    key_entry.setText(config.get(api_name, "key", fallback=""))
            
            # 处理自定义API
            config = configparser.ConfigParser()
            config.read("api_config.ini")
            
            for section in config.sections():
                if section not in self.preset_apis and section not in self.custom_apis:
                    # 添加新的自定义API
                    self.custom_apis.append(section)
                    group = self._create_api_group(section, custom=True)
                    
            # 排列自定义API
            self._arrange_custom_apis()
                    
            # 设置自定义API的值
            for section in config.sections():
                if section in self.api_widgets:
                    url_entry, key_entry = self.api_widgets[section]
                    url_entry.setText(config.get(section, "url", fallback=""))
                    key_entry.setText(config.get(section, "key", fallback=""))
                    
        except configparser.Error as e:
            QMessageBox.warning(self, "配置加载错误", 
                f"配置文件格式错误:\n{str(e)}")

    def _apply_config(self, config: Dict[str, dict]) -> None:
        """应用配置到UI"""
        for api_name, values in config.items():
            if api_name not in self.api_widgets:
                if api_name not in self.preset_apis:
                    # 添加新的自定义API
                    self.custom_apis.append(api_name)
                    group = self._create_api_group(api_name, custom=True)
            
            if api_name in self.api_widgets:
                url_entry, key_entry = self.api_widgets[api_name]
                url_entry.setText(values.get("url", ""))
                key_entry.setText(values.get("key", ""))
        
        # 排列自定义API
        self._arrange_custom_apis()
    def _validate_and_save(self) -> None:
        """验证输入并保存配置"""
        config = configparser.ConfigParser()
        
        # 收集配置数据
        for api_name, (url_entry, key_entry) in self.api_widgets.items():
            url = url_entry.text().strip()
            key = key_entry.text().strip()
            
            if not config.has_section(api_name):
                config.add_section(api_name)
                
            config.set(api_name, "url", url)
            config.set(api_name, "key", key)

        # 尝试写入文件
        try:
            with open("api_config.ini", "w") as f:
                config.write(f)
        except IOError as e:
            QMessageBox.critical(self, "保存失败", 
                f"文件写入失败:\n{str(e)}")
            return
        except Exception as e:
            QMessageBox.critical(self, "未知错误", 
                f"保存时发生意外错误:\n{str(e)}")
            return

        # 发送更新信号
        config_data = {}
        for api_name, (url_entry, key_entry) in self.api_widgets.items():
            config_data[api_name] = {
                "url": url_entry.text().strip(),
                "key": key_entry.text().strip()
            }
        self.configUpdated.emit(config_data)
        
        # 更新状态
        self.status_label.setText("配置已成功保存")
        QTimer.singleShot(3000, lambda: self.status_label.setText(""))

    def on_update_models(self) -> None:
        """触发模型库更新操作（保持原有功能）"""
        self.status_label.setText("正在更新模型库...")
        self.update_thread = APIConfigDialogUpdateModelThread()
        self.update_thread.started_signal.connect(
            lambda: self.status_label.setText("正在更新模型库..."))
        self.update_thread.finished_signal.connect(
            lambda: self.status_label.setText("模型库更新完成！"))
        self.update_thread.finished_signal.connect(self._validate_and_save)
        self.update_thread.error_signal.connect(
            lambda msg: self.status_label.setText(f"更新出错: {msg}"))
        runner = threading.Thread(target=self.update_thread.run)
        self.threads=[runner]
        runner.start()

APIConfigDialog=APIConfigWidget

#窗口大小过渡器
class WindowAnimator:
    @staticmethod
    def animate_resize(window: QWidget, 
                      start_size: QSize, 
                      end_size: QSize, 
                      duration: int = 300):
        """
        窗口尺寸平滑过渡动画
        :param window: 要应用动画的窗口对象
        :param start_size: 起始尺寸（QSize）
        :param end_size: 结束尺寸（QSize）
        :param duration: 动画时长（毫秒，默认300）
        """
        # 创建并配置动画
        anim = QPropertyAnimation(window, b"size", window)
        anim.setDuration(duration)
        anim.setStartValue(start_size)
        anim.setEndValue(end_size)
        anim.setEasingCurve(QEasingCurve.InOutQuad)  # 平滑过渡
        
        # 启动动画
        anim.start()

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
        #return repeats

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
                config.read(filename, encoding='utf-8')
            except:
                config.read(filename)
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
    def debug_chathistory(dic_chathistory):
        """调试聊天记录"""
        actual_length = 0
        for i, message in enumerate(dic_chathistory):
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
                    args = func_info.get('arguments', '')
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

class ChatHistoryTools:
    @staticmethod
    def locate_chat_index(chathistory, request_id):
        for i, msg in enumerate(chathistory):
            info = msg.get('info', {})
            if str(info.get('id')) == str(request_id):
                return i
        return None
    
    @staticmethod
    def patch_history_0_25_1(chathistory):
        request_id=100001
        for item in chathistory:
            if not "info" in item:
                item['info']={'id':request_id}
                request_id+=1
        return chathistory


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
        message = self._purge_message(better_message)
        message = self._process_special_styles(message)
        message = self._handle_web_search_results(message)
        message = self._fix_chat_history(message)
        message = self._handle_long_chat_placement(message)
        message = self._handle_user_and_char(message)
        message = self._handle_mod_functions(message)
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
        for item in messages:
            new_message+=[{k: v for k, v in item.items() if (k != 'info' or k!='reasoning_content')}]
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
        
        if selected_names and not tools:
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
        return params

#tts处理器
class TTSHandler:
    def __init__(self):
        print("[Info] TTSHandler initialized")
        self.enable_tts=False
        if "mods.chatapi_tts" in sys.modules:
            self.tts_window = TTSWindow()
            self.tts_window_enabled=True
        else:
            self.tts_window = None
            self.tts_window_enabled=False
    
    def engage_chat_to_speech(self,income_message):
        print('[Info] TTS Handler engaged')
        # 前置条件检查
        if not self.tts_window or not hasattr(self.tts_window, "send_tts_request"):
            print("[Warn] TTS window not available or missing required method")
            return
        # 带异常处理的TTS请求
        try:
            self.tts_window.send_tts_request(income_message)
        except ConnectionError:
            print("[Error] TTS service unavailable")
        except ValueError as e:
            print(f"[Error] Invalid TTS request: {str(e)}")
        except Exception as e:
            print(f"[Critical] Unexpected TTS error: {str(e)}")

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
        self.theme_selector = ThemeSelector(parent=self)
        self.theme_selector.apply_saved_theme(init_path=None)

    def __init__(self):
        super().__init__()
        self.setupUi()
        self.setWindowTitle("早上好！夜之城！")
        self.setWindowIcon(self.render_svg_to_icon(MAIN_ICON))
        self.tokenpers=CharSpeedAnalyzer()
        self.repeat_processor=RepeatProcessor(self)
        self.ordered_model=RandomModelSelecter()
        self.tts_handler=TTSHandler()

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
        self.init_back_ground_label('background.jpg')

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
        self.stat_tab_widget.setMaximumHeight(135)
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
                                          (setattr(self, 
                                                   'pause_flag', not self.pause_flag), 
                                            self.send_button.setEnabled(True))[1]
                                        )


        self.clear_button = QPushButton("清空")
        self.clear_button.clicked.connect(self.clear_history)

        self.resend_button= QPushButton("重新回答")
        self.resend_button.clicked.connect(self.resend_message_last)

        self.edit_question_button=QPushButton("修改问题")
        self.edit_question_button.clicked.connect(self.edit_user_last_question)

        self.edit_message_button=QPushButton("修改回答")
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

        #思考内容角标
        think_info_pixmap = QPixmap()
        think_info_pixmap.loadFromData(self.think_img)
        self.think_info=QPushButton()
        self.think_info.clicked.connect(self.extend_think_text_box)
        self.think_info.setFixedSize(int(self.height()*0.04), int(self.height()*0.04))
        self.think_info.setIcon(QIcon(think_info_pixmap))
        self.think_info.setIconSize(self.think_info.size()*0.8)

        self.main_layout.addWidget(self.think_info, 6, 1, 1, 1,Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        #思考内容文本框
        self.think_text_box=QTextBrowser()
        self.ai_think_label=QLabel("AI思考链")
        #self.think_text_box.setGraphicsEffect(QGraphicsOpacityEffect().setOpacity(0.5))
        
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

        self.load_stories_chat_list=QPushButton('🗺')
        self.load_stories_chat_list.clicked.connect(self.load_stories_from_chat)
        self.load_stories_chat_list.setToolTip("载入世界观")
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
        #self.main_layout.addWidget(self.past_chat_frame, 0, 3, 1, 1)



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
        '''
QPushButton {
    background-color: #45a049;
    border: 3px solid #45a049; 
    border-radius: 3px; 
    color: #333333;
}

QPushButton:hover {
    background-color: #45a049;  /* 悬停填充色 */
    border-color: #98fb98;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #3d8b40;  /* 点击填充色 */
    border-color: #98fb98;
    color: #ffffff;
}'''
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
        self.chathistory = []
        self.chathistory.append({'role': 'system', 'content': self.sysrule})
        self.chathistory_detail=[]
        self.pause_flag = False
        self.update_response_signal.connect(self.receive_message)
        self.ai_response_signal.connect(self.update_ai_response_text)
        self.update_background_signal.connect(self.update_background)
        self.think_response_signal.connect(self.update_think_response_text)
        self.thread_event = threading.Event()
        self.installEventFilter(self)
        self.read_hotkey_config()
        self.bind_enter_key()
        self.update_opti_bar()

        #UI创建后
        self.init_post_ui_creation()

    def init_self_params(self):
        self.setting_img = setting_img
        self.think_img = think_img
        self.application_path = application_path
        self.history_path=os.path.join(self.application_path,'history')
        self.back_ground_update_model=None
        self.back_ground_update_provider=None
        self.temp_style=''
        self.enforce_lower_repeat_var=False
        self.enforce_lower_repeat_text=''
        self.novita_model='foddaxlPhotorealism_v45_122788.safetensors'
        self.web_searcher=WebSearchSettingWindows()

        # 状态控制标志
        self.stream_receive = True
        self.firstrun_do_not_load = True
        self.long_chat_improve_var = True
        self.hotkey_sysrule_var = True
        self.back_ground_update_var = True
        self.web_search_enabled=False
        self.difflib_modified_flag = False

        # 聊天会话管理
        self.past_chats = {}
        self.max_message_rounds = 50
        self.new_chat_rounds = 0
        self.last_summary = ''
        self.full_response = ''

        # 长度限制设置
        self.max_total_length = 8000
        self.max_segment_length = 8000
        self.max_backgound_lenth = 1000  
        self.long_chat_hint=''
        self.long_chat_improve_api_provider=None
        self.long_chat_improve_model=None
        self.long_chat_placement=''

        # 背景处理相关
        self.new_background_rounds = 0
        self.max_background_rounds = 15
        self.background_style='现实'

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

        #对话储存点
        self.think_response=''
        self.full_response=''

    def init_response_manager(self):
        # AI响应更新控制
        self.ai_last_update_time = 0
        self.ai_update_timer = QTimer()
        self.ai_update_timer.setSingleShot(True)
        #self.ai_update_timer.timeout.connect(self.perform_ai_actual_update)

        # 思考过程更新控制
        self.think_last_update_time = 0
        self.think_update_timer = QTimer()
        self.think_update_timer.setSingleShot(True)
        #self.think_update_timer.timeout.connect(self.perform_think_actual_update)

        self.last_chat_info={}

    def init_mod_configer_page(self):
        self.mod_configer=ModConfiger()

    def init_function_call(self):
        self.function_manager = FunctionManager()
        self.function_chooser = FunctionSelectorUI(self.function_manager)

    def init_post_ui_creation(self):
        self.dialog = APIConfigDialog()
        self.dialog.configUpdated.connect(self._handle_api_update)
        self.dialog.on_update_models()
        
    def init_chat_history_bubbles(self):
        # 聊天历史文本框
        self.chat_history_label = QLabel("聊天历史")
        self.display_full_chat_history=QPushButton("完整记录")
        self.display_full_chat_history.clicked.connect(self.display_full_chat_history_window)
        self.display_full_chat_history.hide()
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
        
    def init_concurrenter(self):
        self.concurrent_model=ConvergenceDialogueOptiProcessor()
        self.concurrent_model.concurrentor_content.connect(self.concurrentor_content_receive)
        self.concurrent_model.concurrentor_reasoning.connect(self.concurrentor_reasoning_receive)
        self.concurrent_model.concurrentor_finish.connect(self.concurrentor_finish_receive)

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

    def init_sysrule(self):
        # 定义文件路径
        file_path = "utils/system_prompt_presets/当前对话.json"
        
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
        tts_page = QWidget()
        tts_page_layout = QGridLayout(tts_page)
        enable_tts_button=QCheckBox("启用语音合成")
        enable_tts_button.setChecked(self.tts_handler.enable_tts)
        enable_tts_button.toggled.connect(lambda checked: setattr(self.tts_handler, 'enable_tts', checked))
        tts_setting_button=QPushButton("语音合成设置")
        tts_setting_button.clicked.connect(self.tts_handler.tts_window.show)
        tts_page_layout.addWidget(enable_tts_button,0,0,1,1)
        tts_page_layout.addWidget(tts_setting_button,0,1,1,1)
        self.stat_tab_widget.addTab(tts_page, "自动播放")

    def show_mod_configer(self):
        self.mod_configer.show()

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
            self.ai_think_label.show()
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
            self.think_text_box.show()
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
        #self.think_text_box.setGeometry(0, 0,int(self.height()*0.04), int(self.height()*0.04))
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
            {"上级名称": "对话", "按钮变量名": "self.chat_lenth", "提示语": "对话设置", "执行函数": "self.open_max_send_lenth_window"},
            {"上级名称": "对话", "按钮变量名": "self.enforce_chat_opti", "提示语": "强制触发长对话优化", "执行函数": "self.long_chat_improve"},
            {"上级名称": "对话", "按钮变量名": "self.trigger_function_call_window", "提示语": "函数调用", "执行函数": "self.show_function_call_window"},
            {"上级名称": "背景", "按钮变量名": "self.background_setting", "提示语": "设置背景更新", "执行函数": "self.background_settings_window"},
            {"上级名称": "背景", "按钮变量名": "self.setting_trigger_background_update", "提示语": "触发背景更新（跟随聊天）", "执行函数": "self.back_ground_update"},
            {"上级名称": "背景", "按钮变量名": "self.customed_background_update", "提示语": "触发背景更新（自定义内容）", "执行函数": "self.show_pic_creater"},
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
    # 创建子窗口
        history_window = QDialog(self)
        history_window.setWindowTitle("Full Chat History")
        history_window.setMinimumSize(650, 500)
        
        # 使用QTextBrowser提升性能
        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        
        buffer = []
        append = buffer.append  # 局部变量加速访问
        for msg in self.chathistory:
            if msg['role'] == 'system':
                continue
            append(f"\n## {msg['role']} \n{msg['content']}\n")
        
        # 单次设置内容（提升渲染性能）
        text_browser.setMarkdown('\n'.join(buffer))
        
        # 自动滚动到底部（避免重复计算）
        #scroll_bar = text_browser.verticalScrollBar()
        #scroll_bar.setValue(scroll_bar.maximum())
        
        # 优化布局参数
        layout = QVBoxLayout(history_window)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(text_browser)
        
        history_window.exec_()

    #更新聊天记录框，会清除用户和AI的输入框
    def update_chat_history(self, clear=True, new_msg=None,msg_id=''):
        # 清空界面元素
        if clear and not new_msg:
            self.user_input_text.clear()
            self.chat_history_bubbles.clear()

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
            self.chat_history_bubbles.set_role_nickname('assistant', role_ai)
            self.chat_history_bubbles.set_role_nickname('user', role_user)
            self.chat_history_bubbles.set_chat_history(self.chathistory)

        else:
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
        self.chathistory.append({'role': 'user', 'content': user_input,'info':{"id":random.randint(100000,999999)}})
        self.update_chat_history()
        if self.stream_receive:
            self.response=None
            self.previous_response = None
            self.temp_full_response = ''
            self.send_message_thread_stream()
            #thread1 = threading.Thread(target=self.send_message_thread_stream)
            #thread1.start()
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
        print('actual update',request_id)
        print('actual update cont',self.full_response)
        print('actual update think',self.think_response)
        actual_response = StrTools.combined_remove_var_vast_replace(self)

        self.ai_response_text.setMarkdown(actual_response)
        self.update_chat_history(new_msg=actual_response,msg_id=request_id)
        self.ai_response_text.verticalScrollBar().setValue(
            self.ai_response_text.verticalScrollBar().maximum()
        )

        #0.25.1 气泡
        self.chat_history_bubbles.update_bubble(msg_id=request_id,content=self.full_response,streaming='streaming')

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
        self.chat_history_bubbles.update_bubble(msg_id=request_id,reasoning_content=self.think_response,streaming='streaming')
        
        # 更新时间戳
        self.think_last_update_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
        self.tokenpers.process_input(self.think_response+self.full_response)
        self.enforce_lower_repeat.setText("强制去重   "+f"tps: {self.tokenpers.get_current_rate():.2f}|peak: {self.tokenpers.get_peak_rate():.2f}")

    #接受信息，信息后处理
    def receive_message(self,request_id,content):
        #if self.return_message
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
            last_message={
                'role': 'assistant', 
                'content': content,
                'info':self.last_chat_info
                }
            if getattr(self,'thinked'):
                last_message['reasoning_content']=self.think_response
            self.chathistory.append(last_message)
            #触发tts
            if self.tts_handler.enable_tts:
                self.tts_handler.engage_chat_to_speech(content)
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
            StrTools.debug_chathistory(message)
        except Exception as e:
            self.return_message = f"Error in preparing message: {e}"
            self.update_response_signal.emit(100000,self.return_message)
            return
        
        self.concurrent_model.start_workflow(params)
        return

        # 发送请求并处理响应
        try:
            self.send_request(params)
        except Exception as e:
            self.return_message = f"Error in sending request: {e}"
            self.update_response_signal.emit(100000,self.return_message)

    def send_request(self, params):
        """发送请求并处理流式响应"""
        # 处理常规响应内容
        def handle_response(content,temp_response):
            if hasattr(content, "content") and content.content:
                special_block_handler_result=StrTools.special_block_handler(self,
                                    temp_response,
                                    request_id,
                                    self.think_response_signal.emit,
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
                #print(content.content, end='', flush=True)

            # 处理思考链内容
            if hasattr(content, "reasoning_content") and content.reasoning_content:
                self.thinked=True
                self.think_response += content.reasoning_content
                self.think_response_signal.emit(request_id,self.think_response)
                #print(content.reasoning_content, end='', flush=True)

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
                "id":request_id
            }
            return self.last_chat_info


        request_id=random.randint(100000,999999)
        self.thinked=False
        api_provider = self.api_var.currentText()
        client = openai.Client(
            api_key=self.api[api_provider][1],
            base_url=self.api[api_provider][0]
        )

        print('AI回复(流式):')
        self.response = client.chat.completions.create(**params)
        self.full_response = ""
        self.think_response = "### AI 思考链\n---\n"
        temp_response = ""
        chatting_tool_call = None

        try:
            content= self.response.choices[0].message
            temp_response += content.content
            handle_response(content,temp_response)
        except Exception as e:
            print(e)

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
                        self.think_response=chatting_tool_call["function"]["arguments"]
                        self.think_response_signal.emit(request_id,self.think_response)
        if chatting_tool_call and chatting_tool_call["function"]["arguments"]:
            try:
                arguments = json.loads(chatting_tool_call["function"]["arguments"])  # 验证 JSON 是否合法
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
                        "arguments": json.dumps(arguments, ensure_ascii=False)
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
                return
                
            except json.JSONDecodeError:
                print("函数参数 JSON 解析失败:", chatting_tool_call["function"]["arguments"])
        
        
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
        if self.back_ground_update_var:
            try:
                self.new_background_rounds+=2
                full_chat_lenth=len(str(self.chathistory))
                message_lenth_bool=(len(self.chathistory)>self.max_background_rounds or full_chat_lenth>self.max_backgound_lenth)
                newchat_rounds_bool=self.new_background_rounds>self.max_background_rounds
                newchat_lenth_bool=(len(str(self.chathistory[-self.new_background_rounds:]))-len(str(self.chathistory[0])))>self.max_backgound_lenth
                long_chat_improve_bool=message_lenth_bool and newchat_rounds_bool or newchat_lenth_bool
                print('背景更新日志：',
                    '\n当前对话次数:',len(self.chathistory)-1,
                    '\n当前对话长度（包含system prompt）:',full_chat_lenth,
                    '\n当前新对话轮次:',self.new_background_rounds,'/',self.max_background_rounds,
                    '\n新对话长度:',(len(str(self.chathistory[-self.new_background_rounds:]))-len(str(self.chathistory[0]))),
                    '\n触发条件:',
                    '\n总对话轮数达标:'
                    '\n对话长度达达到',self.max_backgound_lenth,":", message_lenth_bool,
                    '\n新对话轮次超过限制:', newchat_rounds_bool,
                    '\n新对话长度超过限制:', newchat_lenth_bool,
                    '\n触发背景更新:',long_chat_improve_bool
                    )
                if long_chat_improve_bool:
                    self.new_background_rounds=0
                    
                    print('条件达到,背景更新已触发')
                    self.back_ground_update()
                
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
        self.api_window = APIConfigDialog()
        self.api_window.configUpdated.connect(self._handle_api_update)
        self.api_window.show()
    def _handle_api_update(self, config_data: dict={}) -> None:
        """处理配置更新信号"""
        print('模型库更新完成')
        if not config_data=={}:
            self.api = {
                name: (data["url"], data["key"])
                for name, data in config_data.items()
            }
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
        self.mod_configer.finish_story_creator_init()

    #清除聊天记录
    def clear_history(self):
        self.autosave_save_chathistory()
        self.chathistory = []
        self.chathistory.append({'role': 'system', 'content': self.sysrule})
        self.chat_history_bubbles.clear()
        self.ai_response_text.clear()
        self.new_chat_rounds=0
        self.new_background_rounds=0
        self.last_summary=''
        self.update_opti_bar()

    #打开设置窗口
    def open_system_prompt(self, show_at_call=True):
        def update_system_prompt(prompt):
            if self.chathistory and self.chathistory[0]['role'] == "system":
                self.chathistory[0]['content'] = prompt
            else:
                self.chathistory.insert(0, {'role': 'system', 'content': prompt})
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
        if show_at_call:
            self.system_prompt_override_window.show()
        if self.system_prompt_override_window.isVisible():
            self.system_prompt_override_window.raise_()
            self.system_prompt_override_window.activateWindow()
        self.system_prompt_override_window.load_income_prompt(get_system_prompt())


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
            print(self.send_message_var,self.autoslide_var,self.hotkey_sysrule_var)
            self.bind_enter_key()
            self.settings_window.close()

        confirm_bu.clicked.connect(confirm_settings)
        self.settings_window.exec_()

    #绑定快捷键
    def bind_enter_key(self):
        """根据设置绑定或解绑 Enter 键"""

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
        if file_path:
            #try:
            if True:
                with open(file_path, "r", encoding="utf-8") as file:
                    self.chathistory = json.load(file)
                ChatHistoryTools.patch_history_0_25_1(self.chathistory)
                self.update_chat_history()  # 更新聊天历史显示
                print("聊天记录已导入，当前聊天记录：", self.chathistory[-1]['content'])
                self.new_chat_rounds=min(self.max_message_rounds,len(self.chathistory))
                self.new_background_rounds=min(self.max_background_rounds,len(self.chathistory))
                self.last_summary=''
                self.update_opti_bar()
            #except json.JSONDecodeError:
            #    QMessageBox.critical(self, "格式错误", "JSON 格式不正确或来源非对话\n注意，需要点击“清空”后才不会触发API报错")
            #except Exception as e:
            #    QMessageBox.critical(self, "导入失败", f"导入聊天记录时发生错误：{e}")

    #编辑记录
    def edit_chathistory(self):
        # 创建子窗口
        edit_window = QDialog(self)
        edit_window.setWindowTitle("编辑聊天记录")
        edit_window.resize(self.width(), self.height())

        # 创建布局
        layout = QVBoxLayout()
        edit_window.setLayout(layout)

        # 标签
        note_label = QLabel("在文本框中修改内容，AI的回复也可以修改")
        layout.addWidget(note_label)

        # 创建文本编辑框
        text_edit = QTextEdit()
        layout.addWidget(text_edit)

        # 将 chathistory 转为 JSON 并添加到文本编辑框
        text_edit.setText(json.dumps(self.chathistory, ensure_ascii=False, indent=4))

        # 定义完成按钮的回调函数
        def on_complete():
            try:
                # 获取文本框中的内容
                edited_json = text_edit.toPlainText().strip()
                # 将 JSON 字符串转为 Python 对象
                new_chathistory = json.loads(edited_json)
                # 验证是否是列表且每个元素都是字典
                if isinstance(new_chathistory, list) and all(isinstance(item, dict) for item in new_chathistory):
                    self.chathistory = new_chathistory  # 更新全局变量
                    QMessageBox.information(self, "成功", "聊天记录已更新！")
                    self.update_chat_history()  # 更新聊天历史显示
                    edit_window.accept()
                else:
                    QMessageBox.critical(self, "格式错误", "聊天记录必须是一个包含字典的列表！")
            except json.JSONDecodeError as e:
                QMessageBox.critical(self, "格式错误", f"JSON 格式错误：{e}")

        def delete_last_message():
            edited_json = text_edit.toPlainText().strip()
            # 将 JSON 字符串转为 Python 对象
            new_chathistory = json.loads(edited_json)
            if new_chathistory and new_chathistory[-1]["role"] != "system":
                new_chathistory.pop()
                text_edit.setText(json.dumps(new_chathistory, ensure_ascii=False, indent=4))

        # 批量替换
        def show_replace_dialog():
            # 创建临时对话框，使用edit_window作为父窗口
            dialog = QDialog(edit_window)
            dialog.setWindowTitle("替换内容")

            old_edit = QLineEdit()
            new_edit = QLineEdit()
            btn = QPushButton('执行替换')

            layout = QVBoxLayout()
            layout.addWidget(old_edit)
            layout.addWidget(new_edit)
            layout.addWidget(btn)
            dialog.setLayout(layout)

            def execute_replace():
                old = old_edit.text()
                new_text = new_edit.text()
                if not old:
                    QMessageBox.warning(dialog, "警告", "替换内容不能为空")
                    return

                # 获取当前编辑框中的内容并处理
                current_text = text_edit.toPlainText().strip()
                try:
                    current_history = json.loads(current_text)
                    if not (isinstance(current_history, list) and all(isinstance(item, dict) for item in current_history)):
                        raise ValueError("无效的聊天记录结构")

                    for msg in current_history:
                        if "content" in msg:
                            msg["content"] = msg["content"].replace(old, new_text)
                    # 更新文本框内容
                    text_edit.setText(json.dumps(current_history, ensure_ascii=False, indent=4))
                    dialog.close()
                    QMessageBox.information(edit_window, "完成", "替换操作已完成")
                except Exception as e:
                    QMessageBox.critical(dialog, "错误", f"替换失败：{str(e)}")

            btn.clicked.connect(execute_replace)
            dialog.exec_()

        # 创建功能按钮区域
        grid_func = QGroupBox("快捷编辑")
        grid_func_layout = QGridLayout()
        grid_func.setLayout(grid_func_layout)

        delete_last_message_button = QPushButton("删除上一条")
        delete_last_message_button.clicked.connect(delete_last_message)

        replace_button = QPushButton("替换")
        # 连接信号时不需要传递参数
        replace_button.clicked.connect(show_replace_dialog)

        complete_button = QPushButton("完成")
        complete_button.clicked.connect(on_complete)

        grid_func_layout.addWidget(delete_last_message_button, 0, 0)
        grid_func_layout.addWidget(replace_button, 0, 1)

        layout.addWidget(grid_func)
        layout.addWidget(complete_button)

        # 显示子窗口
        edit_window.exec_()
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
        elif self.chathistory[-1]["role"]=="assistant":
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
        #try:
        #    self.save_sysrule()
        #except Exception as e:
        #    print("save sys prompt fail",e)
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
        config.read('hot_key.ini', encoding='utf-8')
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
        file_names=sorted(list(self.past_chats.keys()))
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
        summary_prompt="""
[背景要求]详细提取关键信息，需要严格符合格式。
格式：
所有角色的个人资料:[名字是##,性别是##,年龄是##,关键特征]（名字不明也需要，关键特征两条或更多）
所有角色的人际关系:[角色1:##,角色2:##,..](A对B的关系/感情/评价/事件/关键交互或其他,优先合并同类项)
主线情节总结:[]（总结对话完整发展，着重于发展节点）
支线事件:[##,##,##]（总结所有过去非主线的事件起因和发展节点）
物品栏:[##,##,##]（物品来源，作用）

注意：
1. 提取内容必须客观、完整。禁止遗漏。
2. 使用书面、正式的语言,避免“行业黑话”和趣味性语言。不对思考过程进行解释。
3. 不需要提到暗示，伏笔等内容。
4. 优先使用一句主谓宾齐全的表述，而不是名词组合。
5. 以下可选项如果被显式或直接提到，则写进个人资料的“关键特征”中；如果没有提到，则省略。

可选项：
性格、语言特征
常用修辞方式
情绪表达（压抑型/外放型）
童年经历
关键人生转折点（例：15岁目睹凶案→决定成为警察）
教育/训练经历（例：军校出身→纪律性极强）
核心行为逻辑
决策原则（功利优先/道德优先）
应激反应模式（战斗/逃避/伪装）
价值排序（亲情>友情>理想）
深层心理画像
潜意识恐惧（例：深海→童年溺水阴影）
自我认知偏差（例：自认冷血→实际多次救人）
时代印记（例：90年代人不用智能手机）
地域特征（例：高原住民）
身体特征（例：草药味体香）
动态标识（例：思考时转笔）
空间偏好（例：总坐在窗边位置）
物品偏好（例：动物/植物）
色彩偏好（例：只穿冷色调）
"""
        user_summary='''
基于要求详细提取关键信息。保留之前的信息，加入新总结的信息。
'''
        if self.long_chat_hint!='':
            user_summary+='以最高的优先级处理：'+str(self.long_chat_hint)
        if self.last_summary!='':
            last_full_story='**已发生事件和当前人物形象**\n'+self.last_summary+'\n**之后的事件**\n'+str(self.chathistory[-self.max_message_rounds:])
        elif self.chathistory[0]["role"]=="system":
            try:
                self.last_summary=str(self.chathistory[0]["content"].split('*已发生事件和当前人物形象**')[1])
            except:
                self.last_summary=''
            last_full_story='**已发生事件和当前人物形象**\n'+self.last_summary+'\n\n对话的新进展:\n\n'+str(self.chathistory[-self.max_message_rounds:])
        else:
            last_full_story=str(self.chathistory[-self.max_message_rounds:])
        last_full_story=user_summary+last_full_story
        print('\n\n\n长文本优化\n获取的完整故事\n\n')
        print(last_full_story)
        print('\n\n')
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
            print("长文本优化：迭代1完成。\n返回长度:",len(return_story))
            if self.last_summary!='':
                last_full_story='将两段内容的信息组合。1.禁止缺少或省略信息。\n2.格式符合[背景要求]。\n3.不要做出推断，保留原事件内容。\n内容1：\n'+self.last_summary+'\n\n内容2：\n'+return_story
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
                    pervious_sysrule = self.chathistory[0]["content"].split('已发生事件和当前人物形象')[0]
                else:
                    pervious_sysrule=self.sysrule.split('已发生事件和当前人物形象')[0]
            except Exception as e:
                if self.chathistory[0]["role"]=="system":
                    pervious_sysrule = self.chathistory[0]["content"]
                else:
                    pervious_sysrule=self.sysrule
                print("pervious_sysrule failure, Error code:",e,'\nCurrent "pervious_sysrule":',pervious_sysrule)
            # 替换系统背景
            
            self.sysrule=pervious_sysrule+'\n**已发生事件和当前人物形象**\n'+return_story
            self.chathistory[0]={"role":"system","content":self.sysrule}
            self.last_summary=return_story
            print('长对话处理一次,历史记录第一位更新为：',self.chathistory[0]["content"])

        except Exception as e:
            # 如果线程中发生异常，也通过信号通知主线程
            self.update_response_signal.emit(100000,f"Error: {str(e)}")
            print('长对话优化报错，Error code:',e)

    #对话设置
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
            'name_ai': self.name_ai
        }
        if not hasattr(self,"main_setting_window"):
            self.main_setting_window=MainSettingWindow(config=config)
            self._connect_signal_mcsw_window()
        #自动模型库更新完成后需要更新模型盒子
        self.main_setting_window.config=config
        self.main_setting_window.update_api_provider_combo()
        self.main_setting_window.show()

    def _connect_signal_mcsw_window(self):
        if hasattr(self, "main_setting_window"):
            # 最大对话轮数
            self.main_setting_window.max_rounds_changed.connect(
                lambda value: setattr(self, 'max_message_rounds', value))
            # 长对话优化设置
            self.main_setting_window.long_chat_improve_changed.connect(
                lambda state: setattr(self, 'long_chat_improve_var', state))
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
                lambda text: setattr(self, 'name_user', text))
            self.main_setting_window.assistant_name_changed.connect(
                lambda text: setattr(self, 'name_ai', text))
            self.main_setting_window.user_name_changed.connect(
                lambda text: print(text))
            
            self.main_setting_window.long_chat_improve_changed.connect(
                self.update_opti_bar
            )

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
        import_action.triggered.connect(
            lambda: self.load_sys_pmt_from_past_record()
        )

        world_view_action = context_menu.addAction("载入世界观")
        world_view_action.triggered.connect(
            lambda: self.load_stories_from_chat()
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
                # 文件不存在时询问是否继续
                choice = QMessageBox.question(
                    self,
                    "文件不存在",
                    "关联文件已丢失，是否从列表中移除该记录？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if choice != QMessageBox.Yes:
                    return
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

    def load_stories_from_chat(self):
        QMessageBox.information(self, "懒得写了", "没写完，不想写")

    #背景更新：触发线程
    def back_ground_update(self,mode='chathistory',pic_creater_input=''):
        self.new_background_rounds=0
        self.update_opti_bar()
        if self.novita_api_key=="":
            try:
                self.novita_api_key=self.api["novita"][1]
                print(self.novita_api_key)
            except Exception as e:
                print('novita api init:',e)
        try:
            print("场景生成：线程启动")
            threading.Thread(target=self.back_ground_update_thread, args=(mode, pic_creater_input)).start()
        except Exception as e:
            print("场景生成：报错",e)
    
    #背景更新：主线程
    
    def get_background_prompt_from_chathistory(self,user_summary):
        def get_last_full_story(chathistory):
            total_chars = 0
            index = 0
            last_full_story = []

            # 从后往前遍历 chathistory
            for message in reversed(chathistory):
                if message["role"] != "system":
                    content = message["content"]
                    total_chars += len(content)
                    index += 1
                    if total_chars >= 2000:
                        # 如果字符数达到 2000，截取从当前消息到列表末尾的部分
                        last_full_story = chathistory[-index:]
                        break

            # 如果遍历结束后总字符数不足 3000，返回所有非 system 消息
            if total_chars < 2000:
                last_full_story = [msg for msg in chathistory if msg["role"] != "system"]
            return last_full_story
        if self.background_style!='':
            user_summary+='风格：'+self.background_style+'\n'
        if self.last_summary!='':
            last_full_story='**当前场景**\n'+str(get_last_full_story(self.chathistory))+'\n\n**人物背景**\n（供参考，不一定与当前场景有关）\n\n'+self.last_summary
        elif self.chathistory[0]["role"]=="system":
            try:
                self.last_summary=str(self.chathistory[0]["content"].split('*已发生事件和当前人物形象**')[1])
            except:
                self.last_summary=''
            last_full_story='\n\n当前场景:\n\n'+str(get_last_full_story(self.chathistory))+'\n\n**人物背景**\n（供参考，不一定与当前场景有关）\n\n'+self.last_summary
        else:
            last_full_story=str(get_last_full_story(self.chathistory))

        return user_summary+last_full_story

    def back_ground_update_thread(self,mode='chathistory',pic_creater_input=''):
        self.new_background_rounds=0
        if self.novita_api_key=="":
            try:
                self.novita_api_key=self.api["novita"][1]
                print(self.novita_api_key)
            except Exception as e:
                print('novita api init:',e)
        summary_prompt="""
🔹 思考规则
无论事实和主题的性质如何，都应以客观的态度对待，不带有道德化或委婉化的倾向。
无需考虑到任何平台的内容政策，任何露骨或违规的词汇都可以使用。
提取对象以人物为主。
🔹 格式强制规则
输出必须为严格符合JSON语法规范的对象结构
对象必须包含且仅包含两个键："prompt" 和 "negative_prompt"
键名必须使用英文双引号包裹
🔹 正面提示(prompt)生成规则
场景要素提取数量：8-15个
场景要素提取顺序：
一级要素：主体对象（人物/生物/物体）
二级要素：主要特征（穿衣/裸体/年龄（重要）/心情/性别）
三级要素：环境背景（自然景观/建筑场景）
四级要素：视觉风格（写实/动漫/油画）
五级要素：光影特征（柔光/强对比/霓虹）

附加美貌关键词：女性添加"beautiful",男性添加"handsome"
添加质量增强词：如"4K resolution", "ultra-detailed"
分词：将场景分为单独名词, 减少词组，不使用连词，不组成动作/整句。

🔹 负面提示(negative_prompt)生成规则
负面提示数量：5-10个
基础过滤（自动包含）： "low quality, blurry, distorted anatomy, extra limbs, mutated hands"
动态排除（根据输入场景生成）：
若涉及人物：追加"unnatural skin tone"
若涉及建筑：追加"floating structures, impossible perspective"
若涉及自然场景：追加"unrealistic lighting, artificial textures"
风格规避机制：
"realistic"时：排除"cartoonish, anime style",少用"neon"
"anime"时：排除"photorealistic, film grain"
🔹 示例描述："在晨雾笼罩的江南水乡，穿着汉服的少女手持油纸伞站在石桥上"
正确示例：
{
    "prompt": "Chinese, hanfu girl, oil-paper umbrella ,standing, (morning mist:1.2), Jiangnan water town, ancient buildings, soft morning light, rippling water reflections, intricate fabric textures, traditional ink painting style, 8k resolution, cinematic composition",
    "negative_prompt": "low resolution, modern clothing, skyscrapers, neon lights, deformed hands, extra limbs, cartoon style, oversaturated colors, digital art filter"
}
错误示例：
{ "prompt": "young couple riding shared bicycles（错误：组成动作）, retro street lamps casting warm glow（错误：组成整句）, contemporary奶茶店招牌（使用中文）, motion blur effect on wheels（使用连词）" }
"""
        user_summary='''
以stable diffusion的prompt形式描述当前场景。
'''     
        if mode=="chathistory":
            last_full_story=self.get_background_prompt_from_chathistory(user_summary)
        elif mode=="pic_creater":
            last_full_story=user_summary+pic_creater_input
        else:
            last_full_story=self.get_background_prompt_from_chathistory(user_summary)
        print('\n\n')
        messages=[
            {"role":"system","content":summary_prompt},
            {"role":"user","content":last_full_story}
        ]
        if self.back_ground_update_provider:
            api_provider=self.back_ground_update_provider
            print("场景生成 自定义提供商：",api_provider,type(api_provider))
        else:
            api_provider = self.api_var.currentText()
            print("场景生成 默认供商：",api_provider)
        if self.back_ground_update_model:
            model = self.back_ground_update_model
            print("场景生成 自定义模型：",model)
        else:
            model = self.model_combobox.currentText()
            print("场景生成 默认模型：",model)
        client = openai.Client(
            api_key=self.api[api_provider][1],
            base_url=self.api[api_provider][0]
        )
        try:
            print("场景生成：prompt请求发送。\n发送内容长度:",len(last_full_story))
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                #temperature=0
            )
            content = completion.choices[0].message
            return_prompt = completion.choices[0].message.content

            reasoning_content = None
            if hasattr(content, "reasoning_content"):  # 优先检查直接属性[2](@ref)
                reasoning_content = content.reasoning_content
            elif hasattr(content, "model_extra"):     # 备选检查扩展字段[4](@ref)
                reasoning_content = content.model_extra.get("reasoning_content", None)

            print("场景生成：prompt请求完成。\n返回长度:",len(return_prompt),
                  "\n返回内容：",return_prompt
                  )
            if reasoning_content:
                print('思考过程:',reasoning_content)
            print("场景生成：prompt json已提取。"
                  )
            if mode=='chathistory':
                self.back_ground_update_thread_to_novita(return_prompt= return_prompt)
            elif mode=='pic_creater':
                return return_prompt
            else:
                return return_prompt
            
        except Exception as e:
            # 如果线程中发生异常，也通过信号通知主线程
            self.update_background_signal.emit(f"Error: {str(e)}")
            print('场景生成报错，Error code:',e)

    def back_ground_update_thread_to_novita(self,return_prompt=''):
        def extract_all_json(ai_response):
            json_pattern = r'\{[\s\S]*?\}'
            matches = re.findall(json_pattern, ai_response)
            
            valid_json_objects = []
            for match in matches:
                try:
                    json_obj = json.loads(match)
                    valid_json_objects.append(json_obj)
                except json.JSONDecodeError:
                    continue
            
            if valid_json_objects:
                return valid_json_objects
            else:
                print("未找到有效的JSON部分")
                return None
        return_prompt=extract_all_json(return_prompt)
        try:
            for item in return_prompt:
                try:
                    prompt = item["prompt"]
                except:
                    None
                    print('prompt extract failed, Error code:',e)
                try:
                    negative_prompt = item["negative_prompt"]
                except Exception as e:
                    None
                    print('negative_prompt extract failed, Error code:',e)
            client = NovitaImageGenerator(api_key=self.novita_api_key)
            # 生成图片请求
            task_id = client.generate(
                prompt= prompt, 
                negative_prompt= negative_prompt,
                model_name=self.novita_model,
                width=1280,
                height=720
            )
            
            # 检查并轮询结果
            if task_id:
                self.returned_file_path=client.poll_result(task_id)
                self.update_background_signal.emit('')
            
        except Exception as e:
            # 如果线程中发生异常，也通过信号通知主线程
            self.update_background_signal.emit(f"Error: {str(e)}")
            print('场景生成报错，Error code:',e)
    
    #背景更新：触发UI更新
    def update_background(self):
        picpath=os.path.join(self.application_path,self.returned_file_path)
        self.switchImage(picpath)

    #背景更新：设置窗口
    def background_settings_window(self):
        """创建并显示设置子窗口，用于更新配置变量"""
        # 读取本地配置文件
        config = configparser.ConfigParser()
        config.read('api_config.ini')  # 读取配置文件

        # 如果 [novita] 节不存在，则添加
        if 'novita' not in config:
            config['novita'] = {'url': 'https://api.novita.ai/v3/', 'key': ''}

        # 创建对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("参数设置")
        layout = QFormLayout(dialog)

        use_api = QComboBox()
        use_api.addItems(list(MODEL_MAP.keys()))
        if self.back_ground_update_provider in MODEL_MAP:
            # 获取索引
            index = list(MODEL_MAP.keys()).index(self.back_ground_update_provider)
            # 设置当前索引
            use_api.setCurrentIndex(index)
        
        use_model = QComboBox()
        if self.back_ground_update_provider and self.back_ground_update_provider!='None':
            use_model.addItems(MODEL_MAP[self.back_ground_update_provider])
            if self.back_ground_update_model in list(MODEL_MAP[self.back_ground_update_provider]):
                # 获取索引
                index = list(MODEL_MAP[self.back_ground_update_provider]).index(self.back_ground_update_model)
                # 设置当前索引
                use_model.setCurrentIndex(index)
        else:
            use_model.addItems(list(MODEL_MAP[list(MODEL_MAP.keys())[0]]))
        
        use_api.currentIndexChanged.connect(lambda _: [use_model.clear(), use_model.addItems(list(MODEL_MAP[use_api.currentText()]))][-1])

        # 创建控件并绑定当前值
        sb_rounds = QSpinBox()
        sb_rounds.setRange(1, 10000)
        sb_rounds.setValue(self.max_background_rounds)

        sb_length = QSpinBox()
        sb_length.setRange(1, 100000)
        sb_length.setValue(self.max_backgound_lenth)

        le_api = QLineEdit(config['novita']['key'])  # 从配置文件读取 API 密钥
        le_api.setPlaceholderText("输入API密钥")

        cb_update = QCheckBox("启用后台更新")
        cb_update.setChecked(self.back_ground_update_var)

        cb_lock = QCheckBox("锁定背景")
        cb_lock.setChecked(self.target_label.locked)
        def on_lock_state_changed(state):
            if state == 2:  # Qt.Checked 状态
                # 用 Walrus Operator 简化文件路径获取（保持原逻辑）
                if (fp := QFileDialog.getOpenFileName()[0]):
                    self.target_label.update_icon(QPixmap(fp))
                    self.target_label.lock()
                # 无论是否选择文件，强制保持复选框选中（原逻辑）
                self.back_ground_update_var=False
                self.update_opti_bar()
                cb_lock.setChecked(True)  # 通过闭包访问外部 cb_lock
            else:
                self.target_label.unlock()  # 通过闭包访问外部 self
                cb_lock.setChecked(False)
                self.back_ground_update_var=True
                self.update_opti_bar()
            cb_update.setChecked(not cb_lock.isChecked())
        cb_lock.stateChanged.connect(on_lock_state_changed)

        #cb_update.stateChanged.connect(lambda state: cb_lock.setChecked(state != Qt.Checked))
        cb_lock.stateChanged.connect(lambda state: cb_update.setChecked(state != Qt.Checked))

        novita_model_combo = QComboBox()
        novita_model_combo.addItems(NOVITA_MODEL_OPTIONS)
        # 设置默认选中项
        novita_model_combo.setCurrentText('foddaxlPhotorealism_v45_122788.safetensors')

        # 添加风格选择控件
        style_editor = QTextEdit()
 
        # 如果存在先前的背景样式设置，则将其设置为 QTextEdit 的初始文本
        if hasattr(self, 'background_style'):
            style_editor.setText(self.background_style)

        # 添加到布局
        layout.addRow("总结器", use_api)
        layout.addRow("模型", use_model)
        layout.addRow("触发背景更新的对话轮次", sb_rounds)
        layout.addRow("参考对话长度", sb_length)
        layout.addRow("文生图模型", novita_model_combo)
        layout.addRow("Novita API密钥", le_api)
        layout.addRow(cb_update)
        layout.addRow(cb_lock)
        layout.addRow("背景风格", style_editor)

        # 添加对话框按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            parent=dialog
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        # 执行对话框并更新值
        if dialog.exec_() == QDialog.Accepted:
            self.max_background_rounds = sb_rounds.value()
            self.max_backgound_lenth = sb_length.value()
            self.novita_api_key = le_api.text().strip()
            self.back_ground_update_var = cb_update.isChecked()
            self.back_ground_update_provider = use_api.currentText()
            self.back_ground_update_model = use_model.currentText()
            self.background_style = style_editor.toPlainText()  # 更新背景风格
            self.novita_model=novita_model_combo.currentText()

            # 更新配置文件
            config['novita']['key'] = self.novita_api_key
            with open('api_config.ini', 'w') as configfile:
                config.write(configfile)
        self.update_opti_bar()

    #背景生成器
    def show_pic_creater(self):
        self.pic_window = PicCreaterWindow(self)
        self.pic_window.show()

        #打开背景图片    
    def open_background_pic(self):
        os.startfile(os.path.join(self.application_path,self.returned_file_path))

    #背景控件初始化
    def init_back_ground_label(self,path):
        # 先加载原始图片
        self.original_pixmap = QPixmap(path)

        # 实例化标签并传递原始图片
        self.target_label = AspectLabel(self.original_pixmap, self)
        self.viewbutton=AspectRatioButton(self.original_pixmap, self)
        self.viewbutton.clicked.connect(self.open_background_pic)

        # 视觉效果配置
        self.opacity_effect = QGraphicsOpacityEffect()
        self.opacity_effect.setOpacity(0.5)
        self.target_label.setGraphicsEffect(self.opacity_effect)
        
        # 布局配置
        self.main_layout.addWidget(self.target_label, 0, 0, 10, 10)
        self.main_layout.addWidget(self.viewbutton,0,3,2,2)

        self.viewbutton.hide()

 
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
        self.viewbutton.update_icon(pixmap)
        self.viewbutton.show()
        
        self.anim_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        # 使用类属性（需要在类中定义这些属性）
        self.anim_in.setDuration(300)  # 确保这个属性在类中已被定义和初始化
        self.anim_in.setStartValue(0.0)
        self.anim_in.setEndValue(0.5)
        self.anim_in.setEasingCurve(QEasingCurve.InOutQuad)  # 确保这个属性在类中已被定义和初始化
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
            self.web_searcher=WebSearchSettingWindows()
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
            #self.stat_tab_widget.hide()
            self.viewbutton         .hide()
            self.bubble_background  .hide()
            self.main_layout.setColumnStretch(0, 1)
            self.main_layout.setColumnStretch(1, 1)
            self.main_layout.setColumnStretch(2, 0)
            self.main_layout.setColumnStretch(3, 0)
            WindowAnimator.animate_resize(self, QSize(self.width(),self.height()), QSize(int(self.height()/2),self.height()-100))
        else:
            self.chat_history_label     .show()
            self.chat_history_bubbles   .show()
            #self.stat_tab_widget       .show()
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
        self.theme_selector.show()

    def show_concurrent_model(self,show=False):
        if not getattr(self,"concurrent_model",None):
            self.concurrent_model=ConvergenceDialogueOptiProcessor()
        if show:
            self.concurrent_model.show()
        else:
            self.concurrent_model.hide()

def start():
    app = QApplication(sys.argv)
    if sys.platform == 'win32':
        appid = 'chatapi.0.23.1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

def clean_cache():
    for root, dirs, files in os.walk('.', topdown=True):
        if '__pycache__' in dirs:
            cache_dir = os.path.join(root, '__pycache__')
            print(f"Removing: {cache_dir}")
            delete_directory(cache_dir)
            dirs.remove('__pycache__')


if __name__=="__main__":
    start()
    #try:
    #    start()
    #except:
    #    clean_cache()
    #    start()
    