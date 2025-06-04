import os
import json

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
    
    def __init__(self):
        self.file_path = os.path.join('utils', 'global', 'NOVITA_MODEL_OPTIONS.json')
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