import os,sys
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, ConfigDict,Field, model_validator

# ==================== 核心基类 ====================

class BaseSettings(BaseModel):
    """
    基于 Pydantic 的配置基类。
    所有配置类都继承这个，自动获得 Update 能力和类型检查能力。
    """

    # 配置 Pydantic V2 的行为
    model_config = ConfigDict(
        validate_assignment=True,  # 运行时修改属性也会触发校验 (setter 保护)
        extra='ignore',           # 忽略多余的字段 (防止旧版 JSON 导致崩溃)
        arbitrary_types_allowed=True
    )

    def update(self, data: Dict[str, Any]):
        """
        原地更新
        递归更新嵌套的 Pydantic 模型，确保对象内存地址（引用）不变。
        """
        if not isinstance(data, dict):
            return

        for key, value in data.items():
            if key not in self.model_fields:
                continue

            # 获取当前属性值
            current_val = getattr(self, key)

            # 如果是嵌套的 Model，且新值也是字典，则递归更新
            if isinstance(current_val, BaseSettings) and isinstance(value, dict):
                current_val.update(value)

            # 否则直接赋值，利用 validate_assignment 触发 Pydantic 的校验逻辑
            # 注意：List 类型会全量替换
            else:
                setattr(self, key, value)

    def to_dict(self) -> dict:
        """兼容旧代码的 to_dict 调用"""
        return self.model_dump()


# ==================== 分类子配置 (Settings) ====================


class BackgroundSettings(BaseSettings):
    """模型与风格选择"""
    background_style: str = '现实'
    back_ground_summary_model: str = 'deepseek-reasoner'
    back_ground_summary_provider: str = 'deepseek'
    back_ground_image_provider: str = 'novita'
    back_ground_image_model: str = 'foddaxlPhotorealism_v45_122788.safetensors'

    back_ground_update_var: bool = True
    """启用自动背景生成"""

    lock_background: bool = False
    """锁定背景：生成背景，但不更新到UI"""

    max_background_rounds: int = 15    
    """自动背景生成的对话轮数"""

    max_backgound_lenth: int = 2000 
    """用于提交自动背景生成的对话文本长度"""  

    background_image_path: str = 'background.jpg' 


class BackgroundSettings(BaseSettings):
    """背景图自动生成设置"""

    enabled: bool = True
    """启用自动背景生成"""  # back_ground_update_var

    lock: bool = False
    """锁定背景：生成但不更新到UI"""  # lock_background

    style: str = '现实'
    """背景风格"""  # background_style

    image_path: str = 'background.jpg'
    """当前背景图路径"""  # background_image_path

    # === 触发条件 ===
    max_rounds: int = 15    
    """触发生成的对话轮数"""  # max_background_rounds

    max_length: int = 2000 
    """提交生成的对话文本长度"""  # max_backgound_lenth

    # === 总结模型 ===
    summary_provider: str = 'deepseek'
    """总结用的API供应商"""  # back_ground_summary_provider

    summary_model: str = 'deepseek-reasoner'
    """总结用的模型"""  # back_ground_summary_model

    # === 图像生成 ===
    image_provider: str = 'novita'
    """图像生成API供应商"""  # back_ground_image_provider

    image_model: str = 'foddaxlPhotorealism_v45_122788.safetensors'
    """图像生成模型"""  # back_ground_image_model

class LciSettings(BaseSettings):
    """上下文自动压缩设置"""

    enabled: bool = True      
    """启用LCI"""  # long_chat_improve_var

    collect_system_prompt: bool = True
    """系统提示注入压缩上下文"""  # enable_lci_system_prompt

    max_total_length: int = 8000
    """触发压缩最少的完整对话长度"""  # max_total_length (unchanged)

    max_segment_length: int = 8000
    """触发压缩最少的距离上次对话长度"""  # max_segment_length (unchanged)

    api_provider: Optional[str] = None
    """上下文压缩的API供应商"""  # long_chat_improve_api_provider

    model: Optional[str] = None
    """上下文压缩的模型"""  # long_chat_improve_model

    hint: str = ''
    """上下文压缩：总结模型的额外关注点"""  # long_chat_hint

    placement: str = ''
    """上下文压缩结果的放置位置"""  # long_chat_placement

class WebSearchSettings(BaseSettings):
    """手动强制搜索"""
    web_search_enabled: bool = False

class ForceRepeatSettings(BaseSettings):
    """强制降重"""
    enforce_lower_repeat_var: bool = False
    enforce_lower_repeat_text: str = ''

class GenerationSettings(BaseSettings): 
    """生成参数设置"""
    stream_receive: bool = True
    top_p_enable: bool = True
    top_p: float = 0.8
    temperature_enable: bool = True
    temperature: float = 0.7
    presence_penalty_enable: bool = True
    presence_penalty: float = 1.0
    thinking_enabled: bool = False
    reasoning_effort: int = 0

    max_message_rounds: int = 50   
    """最大发送长度"""

class InputLimitSettings(BaseSettings): 
    """长度限制与对话阈值"""

    max_send_rounds_enabled:bool=True
    """对话截断：启用轮数限制"""

    max_send_rounds:int=64
    """对话截断：最大上传对话数"""

    max_send_length_enabled:bool = False
    """对话截断：启用字数限制"""

    max_send_length:int = 32767
    """对话截断：最大上传字数"""

    max_send_token_enabled:bool = False
    """对话截断：启用词符限制"""

    max_send_token:int = 32767
    """对话截断：最大上传词符"""

    max_input_length_enabled:bool=False
    """启用单个对话长度限制：不是，限制这个干嘛"""

    max_input_length:int = 32767
    """单个对话长度"""


class TTSSettings(BaseSettings): 
    """语音合成配置"""
    tts_enabled: bool = False
    tts_provider: str = '不使用TTS'

class TitleSettings(BaseSettings): 
    """自动标题配置"""
    enable_title_creator_system_prompt: bool = True
    title_creator_use_local: bool = True
    title_creator_max_length: int = 20
    title_creator_provider: str = 'siliconflow'
    title_creator_model: str = 'deepseek-ai/DeepSeek-R1-0528-Qwen3-8B'

class AutoReplaceSettings(BaseSettings): 
    """文本自动替换配置"""
    autoreplace_var: bool = False
    autoreplace_from: str = ''
    autoreplace_to: str = ''

class HotkeySingle(BaseSettings):
    """单个快捷键配置"""
    enabled: bool = True
    key: str = ""

class HotkeySettings(BaseSettings):
    """快捷键配置"""

    # ===== 固定快捷键（始终生效） =====
    fullscreen: HotkeySingle = Field(
        default_factory=lambda: HotkeySingle(key="F11")
    )
    clear_history: HotkeySingle = Field(
        default_factory=lambda: HotkeySingle(key="Ctrl+N")
    )
    load_chat: HotkeySingle = Field(
        default_factory=lambda: HotkeySingle(key="Ctrl+O")
    )
    save_chat: HotkeySingle = Field(
        default_factory=lambda: HotkeySingle(key="Ctrl+S")
    )
    mod_config: HotkeySingle = Field(
        default_factory=lambda: HotkeySingle(key="Ctrl+M")
    )
    theme_settings: HotkeySingle = Field(
        default_factory=lambda: HotkeySingle(key="Ctrl+T")
    )
    dialog_settings: HotkeySingle = Field(
        default_factory=lambda: HotkeySingle(key="Ctrl+D")
    )
    background_settings: HotkeySingle = Field(
        default_factory=lambda: HotkeySingle(key="Ctrl+B")
    )
    function_call: HotkeySingle = Field(
        default_factory=lambda: HotkeySingle(key="Ctrl+F")
    )

    # ===== 可选快捷键 =====
    send_message: HotkeySingle = Field(
        default_factory=lambda: HotkeySingle(key="Ctrl+Return", enabled=True)
    )
    toggle_tree_tab: HotkeySingle = Field(
        default_factory=lambda: HotkeySingle(key="Tab", enabled=True)
    )
    toggle_tree_ctrl: HotkeySingle = Field(
        default_factory=lambda: HotkeySingle(key="Ctrl+Q", enabled=True)
    )
    system_prompt: HotkeySingle = Field(
        default_factory=lambda: HotkeySingle(key="Ctrl+E", enabled=True)
    )

class FilePaths(BaseSettings):
    """运行时计算的路径"""
    application_path: str = ''
    setting_img: str = ''
    think_img: str = '' 
    returned_file_path: str = '' 

    @property
    def history_path(self) -> str:
        """这个属性动态计算，不参与序列化"""
        return os.path.join(self.application_path, 'history')


# >>> 用户配置总入口 <<<
class AppSettings(BaseSettings):
    generation: GenerationSettings = Field(default_factory=GenerationSettings)
    limits: InputLimitSettings = Field(default_factory=InputLimitSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    title: TitleSettings = Field(default_factory=TitleSettings)
    replace: AutoReplaceSettings = Field(default_factory=AutoReplaceSettings)

    lci: LciSettings = Field(default_factory=LciSettings)
    """上下文自动压缩"""

    background: BackgroundSettings = Field(default_factory=BackgroundSettings)
    """背景更新"""

    web_search: WebSearchSettings = Field(default_factory=WebSearchSettings)
    """手动强制搜索"""

    force_repeat: ForceRepeatSettings = Field(default_factory=ForceRepeatSettings)
    """强制降重"""

# 初始化单例
APP_SETTINGS = AppSettings()

class AppPaths(BaseSettings):
    # 先定义成普通字段，给个空字符串当占位符
    application_path: str = ""
    history_path: str = ""

    @model_validator(mode='after')
    def calculate_paths(self):
        # 1. 如果没传值，就自动计算 application_path
        if not self.application_path:
            # 兼容 PyInstaller 打包后的情况 (frozen)
            if getattr(sys, 'frozen', False):
                base_path = os.path.dirname(sys.executable)
            else:
                base_path = os.path.dirname(os.path.abspath(sys.argv[0]))

            self.application_path = base_path

        # 2. 如果没传值，就根据 application_path 算出 history_path
        if not self.history_path:
            self.history_path = os.path.join(self.application_path, "history")

        return self

class AppRuntime(BaseSettings):
    paths: AppPaths = Field(default_factory=AppPaths)