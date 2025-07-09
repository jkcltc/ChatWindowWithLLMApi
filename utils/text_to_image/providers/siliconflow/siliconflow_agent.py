import os
import json
import requests
import time
import threading
import random
from PyQt5.QtCore import QObject,pyqtSignal

class SiliconflowModelFetcher(QObject):
    update_done=pyqtSignal(list)

    def __init__(self,application_path='',api_key=''):
        super().__init__()
        self.base_url = 'https://api.siliconflow.cn/v1/models?sub_type=text-to-image'
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self.model_list = SiliconflowModelManager().get_model_options()  # 共享资源需要保护
        self.application_path=application_path
        
        # 添加线程同步工具
        self.lock = threading.Lock()
        self.fetch_complete = threading.Event()  # 用于标记获取完成状态
    
    def fetch_models(self):
        """启动后台线程获取模型数据"""
        # 重置完成标志
        self.fetch_complete.clear()
        
        # 创建并启动后台线程
        thread = threading.Thread(target=self._fetch_in_thread)
        thread.daemon = True  # 设为守护线程
        thread.start()
    
        return True  # 表示线程启动成功
    
    def _fetch_in_thread(self):
        """在后台线程中执行实际请求"""
        try:
            response = requests.get(self.base_url, headers=self.headers)
            response.raise_for_status()
            result = response.json()
            
            if 'data' not in result:
                raise ValueError("API响应缺少'data'字段")
                
            # 获取模型ID列表
            new_list = [model['id'] for model in result['data']]
            
            # 安全更新共享资源
            with self.lock:
                self.model_list = new_list
            
            # 标记任务成功完成
            print('sil sec')
            self.fetch_complete.set()
            self.update_done.emit(self.model_list)
            
        except Exception as e:  # 捕获所有异常
            print(f"后台请求出错: {e}")
            # 即使出错也标记完成，防止永久阻塞
            self.fetch_complete.set()
    
    def get_model_list(self, timeout=None):
        """返回模型列表，可选等待操作完成"""
        # 如果设置了超时，等待操作完成
        if timeout is not None:
            self.fetch_complete.wait(timeout=timeout)
            
        # 安全返回当前模型列表
        with self.lock:
            return self.model_list.copy()  # 返回副本避免直接修改

class SiliconflowModelManager:
    _DEFAULT_MODEL_OPTIONS = [
        'stabilityai/stable-diffusion-xl-base-1.0',
        'black-forest-labs/FLUX.1-schnell',
        'black-forest-labs/FLUX.1-dev',
        'Pro/black-forest-labs/FLUX.1-schnell',
        'stabilityai/stable-diffusion-3-5-large',
        'black-forest-labs/FLUX.1-pro',
        'LoRA/black-forest-labs/FLUX.1-dev',
        'Kwai-Kolors/Kolors',
    ]

    def __init__(self,application_path=''):
        self.file_path = os.path.join(application_path, 'utils','text_to_image','providers','siliconflow','SILICON_IMAGE_MODELS.json')
        self._ensure_file_exists()
       
    def _ensure_file_exists(self):
        """确保文件存在，如果不存在则创建并写入默认值"""
        if not os.path.exists(self.file_path):
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            self.save_model_options(self._DEFAULT_MODEL_OPTIONS)
    
    def get_model_options(self) -> list:
        """获取模型选项列表，文件不存在时返回默认值"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            # 如果文件意外丢失，重新创建并返回默认值
            self._ensure_file_exists()
            return self._DEFAULT_MODEL_OPTIONS.copy()
    
    def save_model_options(self, model_options: list):
        """保存模型选项列表到文件"""
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(model_options, f, indent=2, ensure_ascii=False)

class SiliconFlowImageGenerator(QObject):
    pull_success = pyqtSignal(str)  # 图片保存路径
    failure = pyqtSignal(str, str)  # 错误类型和错误信息

    def __init__(self, api_key, application_path, parent=None, save_folder='pics'):
        super().__init__(parent)
        self.api_key = api_key
        self.application_path = application_path
        self.save_path = os.path.join(application_path, save_folder)
        os.makedirs(self.save_path, exist_ok=True)
        self.base_url = "https://api.siliconflow.cn/v1/images/generations"
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

    def generate(self, prompt, model="Kwai-Kolors/Kolors", negative_prompt="", 
                 image_size="1024x1024", batch_size=1, steps=20,
                 guidance_scale=7.5, seed=None):
        """
        文生图请求并自动保存图片
        :param prompt: 提示词
        :param model_name: 模型名称（默认Kwai-Kolors/Kolors）
        :param negative_prompt: 负面提示词
        :param image_size: 图片尺寸（"1024x1024"等）
        :param batch_size: 生成数量（1-4）
        :param steps: 推理步数（1-100）
        :param guidance_scale: 引导系数（0-20）
        :param seed: 随机种子，如果为None则使用随机值
        """
        # 准备请求数据
        payload = {
            "model": model,
            "prompt": prompt,
            "image_size": image_size,
            "batch_size": batch_size,
            "num_inference_steps": steps,
            "guidance_scale": guidance_scale
        }
        
        # 可选参数
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
            
        if seed is not None:
            payload["seed"] = seed
        else:
            payload["seed"] = random.randint(0, 9999999999)  # 生成随机种子

        try:
            # 发送请求
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload
            )
            
            # 处理响应
            if response.status_code != 200:
                self.failure.emit('request', f"请求失败，状态码：{response.status_code}, 响应：{response.text}")
                return None
                
            result = response.json()
            
            # 验证响应格式
            if not result.get('images') or not isinstance(result['images'], list):
                self.failure.emit('response', "响应格式错误：缺少images字段")
                return None
                
            # 保存所有生成的图片
            saved_paths = []
            for i, img_data in enumerate(result['images']):
                if 'url' in img_data:
                    # 使用种子+索引作为文件名
                    filename = f"silicon_{payload['seed']}_{i}"
                    saved_path = self._save_image(img_data['url'], filename)
                    if saved_path:
                        saved_paths.append(saved_path)
                else:
                    self.failure.emit('response', f"图片{i}缺少URL字段")
            
            return saved_paths
            
        except Exception as e:
            self.failure.emit('request', f"请求异常：{str(e)}")
            return None

class SiliconFlowAgent(QObject):
    pull_success = pyqtSignal(str)  # 图片保存路径
    failure = pyqtSignal(str, str)  # 错误类型和错误信息

    def __init__(self, api_key, application_path, save_folder='pics', parent=None):
        super().__init__(parent)
        self.application_path = application_path
        
        # 初始化图片生成器
        self.generator = SiliconFlowImageGenerator(
            api_key, 
            application_path,
            save_folder=save_folder
        )
        # 连接生成器的信号
        self.generator.pull_success.connect(self.pull_success.emit)
        self.generator.failure.connect(self.failure.emit)
        
        # 初始化模型管理器
        self.model_manager = SiliconflowModelManager(application_path)
        self.model_updater = SiliconflowModelFetcher(application_path=application_path,api_key=api_key)
        self.model_updater.update_done.connect(self.model_manager.save_model_options)
        
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
        将统一格式的参数转换为硅基流动API所需的格式
        """
        # 参数映射
        mapping = {
            'model_name': 'model',
            'image_num': 'batch_size',
            'steps': 'steps',
            'guidance_scale': 'guidance_scale',
            'prompt': 'prompt',
            'negative_prompt': 'negative_prompt',
        }
        
        # 构建新的参数字典
        new_params = {}
        for key, value in mapping.items():
            if key in params:
                new_params[value] = params[key]
        
        # 特殊参数处理
        # 1. 合并宽高生成图像尺寸字符串
        width = params.get('width', 512)
        height = params.get('height', 512)
        new_params['image_size'] = f"{width}x{height}"
        
        # 2. 处理种子参数
        seed = params.get('seed', -1)
        new_params['seed'] = seed if seed != -1 else None
        
        return new_params

    def update_model_list(self):
        try:
            self.model_updater.fetch_models()
        except Exception as e :
            self.failure.emit('update_model_list',str(e))
        return
    
    @property
    def request_template(self):
        """返回参数模板"""
        return {
            'prompt': "required",
            'model_name': "required",
            'negative_prompt': "",
            'width': 512,
            'height': 512,
            'image_num': 1,
            'steps': 20,
            'guidance_scale': 7.5,
            'seed': -1
        }
