import os
import json
import requests
import time
import threading
from PyQt5.QtCore import QObject,pyqtSignal

import os
import random
import requests
import base64
from PyQt5.QtCore import QObject, pyqtSignal

class BaiduImageGenerator(QObject):
    pull_success = pyqtSignal(str)  # 图片保存路径
    failure = pyqtSignal(str, str)  # 错误类型和错误信息

    def __init__(self, api_key, application_path, parent=None, save_folder='pics'):
        super().__init__(parent)
        self.api_key = api_key
        self.application_path = application_path
        self.save_path = os.path.join(application_path, save_folder)
        os.makedirs(self.save_path, exist_ok=True)
        self.base_url = "https://qianfan.baidubce.com/v2/images/generations"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _save_image(self, image_url, filename):
        """下载并保存图片"""
        try:
            # 确保文件名有后缀
            if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                filename += '.png'
                
            filepath = os.path.join(self.save_path, filename)
            response = requests.get(image_url)
            
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                self.pull_success.emit(filepath)
                return filepath
            else:
                self.failure.emit('save', f"下载失败，状态码：{response.status_code}")
        except Exception as e:
            self.failure.emit('save', f"保存图片异常：{str(e)}")
        return None

    def generate(self, prompt, model="irag-1.0", negative_prompt="", 
                 image_size="1024x1024", batch_size=1, steps=20,
                 guidance_scale=3.5, seed=None, refer_image=None, user_id=None):
        """
        百度千帆文生图请求并自动保存图片
        
        :param prompt: 提示词（必填，最大512字符）
        :param model: 模型名称（默认为"irag-1.0"）
        :param negative_prompt: 百度的API不支持负面提示词，此参数将被忽略
        :param image_size: 图片尺寸字符串（如"1024x1024"）
        :param batch_size: 生成数量（1-4）
        :param steps: 推理步数（仅flux.1-schnell模型支持，1-50）
        :param guidance_scale: 引导系数（仅flux.1-schnell模型支持，0-30）
        :param seed: 随机种子（仅flux.1-schnell模型支持）
        :param refer_image: 参考图URL或Base64编码（仅irag-1.0模型支持）
        :param user_id: 终端用户唯一标识
        """
        # 准备请求数据
        payload = {
            "model": model,
            "prompt": prompt,
            "n": batch_size,
            "size": image_size
        }
        
        # 可选参数
        if refer_image:
            if refer_image.startswith("http://") or refer_image.startswith("https://"):
                payload["refer_image"] = refer_image
            else:  # Base64编码
                payload["refer_image"] = refer_image
        
        if user_id:
            payload["user"] = user_id
            
        # flux.1-schnell模型专用参数
        if model == "flux.1-schnell":
            payload["steps"] = steps
            payload["seed"] = seed
            payload["guidance"] = guidance_scale

        try:
            # 发送请求
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload
            )
            
            # 处理响应
            if response.status_code != 200:
                self.failure.emit('request', 
                                 f"请求失败，状态码：{response.status_code}, 响应：{response.text}")
                return None
                
            result = response.json()
            
            # 验证响应格式
            if not result.get('data') or not isinstance(result['data'], list):
                self.failure.emit('response', "响应格式错误：缺少data字段")
                return None
                
            # 保存所有生成的图片
            saved_paths = []
            for i, img_data in enumerate(result['data']):
                if 'url' in img_data:
                    filename = f"baidu_{result.get('id', '')}_{i}"
                    saved_path = self._save_image(img_data['url'], filename)
                    if saved_path:
                        saved_paths.append(saved_path)
                else:
                    self.failure.emit('response', f"图片{i}缺少URL字段")
            
            return saved_paths
            
        except Exception as e:
            self.failure.emit('request', f"请求异常：{str(e)}")
            return None
class BaiduModelManager:
    """百度模型管理器（静态模型列表）"""
    def __init__(self, application_path):
        self.model_options = ['irag-1.0', 'flux.1-schnell']
    
    def get_model_options(self) -> list:
        """获取百度支持的模型列表"""
        return self.model_options.copy()
    
    def save_model_options(self):
        """百度模型列表是静态的，无需保存"""
        pass

class BaiduAgent(QObject):
    pull_success = pyqtSignal(str)  # 图片保存路径
    failure = pyqtSignal(str, str)  # 错误类型和错误信息

    def __init__(self, api_key, application_path, save_folder='pics', parent=None):
        super().__init__(parent)
        self.application_path = application_path
        
        # 初始化图片生成器
        self.generator = BaiduImageGenerator(
            api_key, 
            application_path,
            save_folder=save_folder
        )
        # 连接生成器的信号
        self.generator.pull_success.connect(self.pull_success.emit)
        self.generator.failure.connect(self.failure.emit)
        
        # 初始化模型管理器（静态模型列表）
        self.model_manager = BaiduModelManager(application_path)
        
        # 线程列表
        self.thread_list = []

    def get_model_list(self) -> list:
        """获取模型列表"""
        return self.model_manager.get_model_options()

    def create(self, config):
        """
        创建图片生成任务
        参数config已使用ParamTranslator翻译
        """
        # 转换参数格式
        params = self.translate_params(config)
        
        # 创建并启动后台线程
        thread = threading.Thread(target=self.generator.generate, kwargs=params)
        thread.daemon = True
        thread.start()
        
        # 添加到线程列表
        self.thread_list.append(thread)

    def clear_thread(self):
        """清空线程列表"""
        self.thread_list = []

    def translate_params(self, params):
        """
        参数格式转换
        将统一格式的参数转换为百度API所需的格式
        """
        # 必选参数
        new_params = {
            'prompt': params['prompt'],
            'model': params['model'],
        }
        
        # 图片尺寸 - 可选参数
        width = params.get('width')
        height = params.get('height')
        
        # 仅在提供了宽度和高度时才设置 image_size
        if width is not None and height is not None:
            new_params['image_size'] = f"{width}x{height}"
        
        # 生成数量 - 可选但建议提供
        if 'image_num' in params:
            new_params['batch_size'] = params['image_num']
        else:
            # 如果没有提供，使用API默认值1
            new_params['batch_size'] = 1
            
        # 可选参数 - 仅当提供时才设置
        if 'seed' in params and params['seed'] != -1:
            new_params['seed'] = params['seed']
            
        if 'steps' in params:
            new_params['steps'] = params['steps']
            
        if 'guidance_scale' in params:
            new_params['guidance_scale'] = params['guidance_scale']
            
        # 百度专用可选参数
        if 'refer_image' in params and params['refer_image']:
            new_params['refer_image'] = params['refer_image']
            
        if 'user_id' in params and params['user_id']:
            new_params['user_id'] = params['user_id']
            
        return new_params


    def update_model_list(self):
        """百度模型列表是静态的，无需更新"""
        # 这里可以发出一个信号表示更新完成（如果需要）
        pass
    
    @property
    def request_template(self):
        """返回参数模板"""
        return {
            'prompt': "required",
            'model': "required",
            'width': 1024,
            'height': 1024,
            'image_num': 1,
            'steps': 20,
            'guidance_scale': 3.5,
            'seed': -1,
            'refer_image': None,
            'user_id': None
        }
