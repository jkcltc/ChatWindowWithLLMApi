import os
import json
import requests
import time
import threading
from PyQt5.QtCore import QObject,pyqtSignal


class NovitaModelPresetVars:
    model_list_path=r'utils\text_to_image\providers\novita\NOVITA_MODEL_OPTIONS.json'

class NovitaModelManager:
    _DEFAULT_MODEL_OPTIONS = [
        'flat2DAnimerge_v30_72593.safetensors',
        'wlopArienwlopstylexl_v10_101973.safetensors',
        "colorBoxModel_colorBOX_20935.safetensors",
        'cyberrealistic_v32_81390.safetensors',
        'fustercluck_v2_233009.safetensors',
        'novaPrimeXL_v10_107899.safetensors',
        'foddaxlPhotorealism_v45_122788.safetensors',
        "sciFiDiffusionV10_v10_4985.ckpt",
        'cyberrealistic_v31_62396.safetensors'
    ]
    
    def __init__(self,application_path=''):
        self.file_path = os.path.join(application_path, NovitaModelPresetVars.model_list_path)
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

class NovitaImageGenerator(QObject):
    request_emit=pyqtSignal(str)
    pull_success=pyqtSignal(str)#path
    failure=pyqtSignal(str,str)

    def __init__(self, api_key,application_path,parent=None,save_folder='pics'):
        '''
        save_folder是后加的，指定pics
        '''
        super().__init__(parent)
        self.base_url = "https://api.novita.ai/v3/"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.application_path=application_path
        # 确保图片目录存在
        self.save_path=os.path.join(self.application_path,save_folder)
        os.makedirs(self.save_path, exist_ok=True)
        self.failure.connect(print)
        
    def _save_image(self, url, filename):
        """保存图片到指定目录"""
        try:
            filepath = os.path.join(self.save_path, filename)
            response = requests.get(url)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                print(f"图片已保存为 {filepath}")
                self.pull_success.emit(filepath)
                return filepath
            self.failure.emit('poll',f"下载失败，状态码：{response.status_code}")
        except Exception as e:
            self.failure.emit('poll',f"请求失败，状态码：{e}")
        
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
            self.failure.emit('generate',f"请求失败，状态码：{response.status_code}")
            return None
        task_id=response.json().get('task_id')
        self.request_emit.emit(task_id)
        return task_id

    def poll_result(self, task_id, timeout=600, interval=5):
        """轮询任务结果并返回图片路径"""
        start_time = time.time()
        print(f"开始轮询任务 {task_id}...")

        while True:
            # 超时检查
            if time.time() - start_time > timeout:
                self.failure.emit('poll',"请求超时")
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
                self.failure.emit('poll',f"请求异常: {str(e)}")
                continue

            data = response.json()
            status = data['task']['status']

            # 处理任务状态
            if status == 'TASK_STATUS_SUCCEED':
                if data.get('images'):
                   image_url = data['images'][0]['image_url']
                   return self._save_image(image_url, f"{task_id}.jpg")
                self.failure.emit('poll',"任务成功但未返回图片")
                return None
            elif status == 'TASK_STATUS_FAILED':
                self.failure.emit('poll',f"任务执行失败: {data['task']['reason']}")
                return None

class NovitaAgent(QObject):
    '''
    对已经实现的请求类做自动化
    保证工厂类接口
    '''
    pull_success = pyqtSignal(str)
    failure = pyqtSignal(str, str)

    def __init__(self, api_key, application_path,save_folder='pics'):
        """
        初始化Novita代理
        """
        super().__init__()
        self.application_path = application_path
        
        # 初始化图片生成器
        self.generator = NovitaImageGenerator(api_key, application_path,save_folder=save_folder)
        self.generator.request_emit.connect(print)
        self.generator.request_emit.connect(self.poll_result)
        self.generator.pull_success.connect(self.pull_success.emit)
        self.generator.failure.connect(self.failure.emit)
        self.generator.pull_success.connect(lambda _: setattr(self, 'thread_list', []))
        
        # 初始化模型管理器
        self.model_manager = NovitaModelManager(application_path)
        
        self.thread_list = []

    def get_model_list(self) -> list:
        """获取模型列表"""
        return self.model_manager.get_model_options()

    def create(self, config):
        """
        创建图片生成任务
        参数config已使用ParamTranslator翻译
        """
        # 解包字典参数并设置默认值
        self.create_thread = threading.Thread(target=self.generator.generate, args=(
            config['prompt'],
            config['model_name'],
            config['negative_prompt'],
            config.get('width', 512),
            config.get('height', 512),
            config.get('image_num', 1),
            config.get('steps', 20),
            config.get('seed', -1),
            config.get('clip_skip', 1),
            config.get('sampler_name', "Euler a"),
            config.get('guidance_scale', 7.5)
        ))
        
        self.thread_list.append(self.create_thread)
        self.create_thread.start()
        print('创建任务线程已启动')
    
    def poll_result(self, task_id):
        self.poll_thread = threading.Thread(target=self.generator.poll_result, args=(task_id,))
        self.thread_list += [self.poll_thread]
        self.poll_thread.start()
    
    def clear_thread(self):
        self.thread_list = []

    def translate_params(self,params):
        #先做值翻译
        params['model_name'] = params.get('model', '')
        
        # 收集需要删除的无效键
        invalid_keys = [
            key for key in params
            if key not in self.request_template
        ]
        
        # 批量删除无效键
        for key in invalid_keys:
            del params[key]
        return params


    @property
    def request_template(self):
        return  {
    'prompt': "required",     
    'model_name': "required", 
    'negative_prompt': "",              # 负面提示实际上没有也行
    'width': 512,                       # 生成图片宽度（像素），默认512
    'height': 512,                      # 生成图片高度（像素），默认512
    'image_num': 1,                     # 生成图片数量，默认1
    'steps': 20,                        # 迭代步数，默认20
    'seed': -1,                         # 随机种子，-1表示随机生成
    'clip_skip': 1,                     # CLIP跳过层数，默认1
    'sampler_name': "Euler a",          # 采样器名称，默认"Euler a"
    'guidance_scale': 7.5               # 指导系数(CFG)，默认7.5
}
    

if __name__=='__main__':
    module=NovitaModelManager()
    print(module.get_model_options())
