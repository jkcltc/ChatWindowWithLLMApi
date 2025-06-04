import json
import os
from pathlib import Path

class ModelMapManager:
    _DEFAULT_FILE_PATH = Path("utils/global_presets/MODEL_MAP.json")
    
    def __init__(self, file_path: str = None):
        """
        初始化管理器，可自定义文件路径
        :param file_path: 可选的自定义文件路径
        """
        self.file_path = Path(file_path) if file_path else self._DEFAULT_FILE_PATH
    
    def get_model_map(self) -> dict:
        """从文件读取并返回MODEL_MAP字典"""
        try:
            # 确保目录存在
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            if not self.file_path.exists():
                # 文件不存在时返回默认
                return self.get_default_model_map()
            
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except (json.JSONDecodeError, OSError) as e:
            print(f"Error reading model map: {e}")
            return {}

    def save_model_map(self, model_map: dict):
        """将MODEL_MAP字典保存到文件"""
        try:
            # 确保目录存在
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(model_map, f, indent=2, ensure_ascii=False)
                
        except (TypeError, OSError) as e:
            print(f"Error saving model map: {e}")

    def get_default_model_map(self) -> dict:
        """获取代码中定义的默认MODEL_MAP"""
        return {
            "baidu": [
                "ernie-4.5-turbo-32k",
                "qwen3-0.6b",
            ],
            "deepseek": ["deepseek-chat", "deepseek-reasoner"],
            "tencent": ["deepseek-r1", "deepseek-v3"],
            "siliconflow": [
                'deepseek-ai/DeepSeek-V3',
                'deepseek-ai/DeepSeek-R1',
                'Pro/deepseek-ai/DeepSeek-R1',
                'SeedLLM/Seed-Rice-7B',
                'Qwen/QwQ-32B'
            ]
        }