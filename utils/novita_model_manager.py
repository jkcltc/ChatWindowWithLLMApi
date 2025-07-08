import os
import json
import requests
import time
from PyQt5.QtCore import QObject,pyqtSignal

try:
    from .preset_data import NovitaModelPresetVars
except:
    from preset_data import NovitaModelPresetVars

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
    
    def __init__(self,applisction_path=''):
        self.file_path = os.path.join(applisction_path, NovitaModelPresetVars.model_list_path)
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

    def __init__(self, api_key,application_path,parent=None):
        super().__init__(parent)
        self.base_url = "https://api.novita.ai/v3/"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.application_path=application_path
        # 确保图片目录存在
        self.save_path=os.path.join(self.application_path,'pics')
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
            self.failure.emit('generate',f"请求失败，状态码：{response.status_code}")
            return None
        task_id=response.json().get('task_id')
        self.request_emit.emit(task_id)
        return 

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




if __name__=='__main__':
    module=NovitaModelManager()
    print(module.get_model_options())
