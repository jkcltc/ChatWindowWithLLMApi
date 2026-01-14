import os
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, ConfigDict

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
        【智能原地更新】
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
        """兼容你旧代码的 to_dict 调用习惯"""
        return self.model_dump()


# ==================== 分类子配置 (Settings) ====================

class IdentitySettings(BaseSettings): 
    """身份与头像配置"""
    name_user: str = "用户"
    name_ai: str = ""
    avatar_user: str = ''
    avatar_ai: str = ''

class ModelStyleSettings(BaseSettings):
    """模型与风格选择"""
    novita_model: str = 'foddaxlPhotorealism_v45_122788.safetensors'
    background_style: str = '现实'
    back_ground_summary_model: str = 'deepseek-reasoner'
    back_ground_summary_provider: str = 'deepseek'
    back_ground_image_provider: str = 'novita'
    back_ground_image_model: str = 'foddaxlPhotorealism_v45_122788.safetensors'

class FeatureSwitches(BaseSettings): 
    """功能开关"""
    stream_receive: bool = True
    long_chat_improve_var: bool = True
    enable_lci_system_prompt: bool = True
    hotkey_sysrule_var: bool = True
    back_ground_update_var: bool = True
    lock_background: bool = False
    web_search_enabled: bool = False
    thinking_enabled: bool = False
    reasoning_effort: int = 0
    enforce_lower_repeat_var: bool = False
    enforce_lower_repeat_text: str = ''

class GenerationSettings(BaseSettings): 
    """生成参数设置"""
    top_p_enable: bool = True
    top_p: float = 0.8
    temperature_enable: bool = True
    temperature: float = 0.7
    presence_penalty_enable: bool = True
    presence_penalty: float = 1.0

class InputLimitSettings(BaseSettings): 
    """长度限制与长对话阈值"""
    max_total_length: int = 8000
    max_segment_length: int = 8000
    long_chat_hint: str = ''
    long_chat_placement: str = ''
    max_message_rounds: int = 50       
    max_background_rounds: int = 15    
    max_backgound_lenth: int = 1000   
    long_chat_improve_api_provider: Optional[str] = None
    long_chat_improve_model: Optional[str] = None

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

class APICredentials(BaseSettings):
    """API 密钥与连接配置"""
    novita_api_key: str = ""

class MemoryPreference(BaseSettings):
    """记忆相关的偏好"""
    saved_api_provider: str = ''    
    saved_model_name: str = ''      

# >>> 用户配置总入口 <<<
class AppSettings(BaseSettings):
    identity: IdentitySettings = Field(default_factory=IdentitySettings)
    models: ModelStyleSettings = Field(default_factory=ModelStyleSettings)
    features: FeatureSwitches = Field(default_factory=FeatureSwitches)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)
    limits: InputLimitSettings = Field(default_factory=InputLimitSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    title: TitleSettings = Field(default_factory=TitleSettings)
    replace: AutoReplaceSettings = Field(default_factory=AutoReplaceSettings)
    api: APICredentials = Field(default_factory=APICredentials)
    memory: MemoryPreference = Field(default_factory=MemoryPreference)

# 初始化单例
APP_SETTINGS = AppSettings()


# ==================== 运行时状态 (Runtime) ====================

class RuntimePaths(BaseSettings):
    """运行时计算的路径"""
    application_path: str = ''
    setting_img: str = ''
    think_img: str = '' 
    background_image_path: str = 'background.jpg' 
    returned_file_path: str = '' 

    @property
    def history_path(self) -> str:
        """这个属性动态计算，不参与序列化"""
        return os.path.join(self.application_path, 'history')

class ChatContext(BaseSettings):
    """当前聊天会话的上下文状态"""
    # 这里的 List[Dict] 会被 Pydantic 虽然不校验 Dict 内部，但会确保是 List
    chathistory: List[Dict[str, Any]] = Field(default_factory=list)
    past_chats: Dict[str, Any] = Field(default_factory=dict)

    new_chat_rounds: int = 0         
    new_background_rounds: int = 0   

    last_summary: str = ''           
    full_response: str = ''          
    temp_style: str = ''             

class LastResponseState(BaseSettings): 
    """上一条回复的详细状态"""
    think_response: str = ''
    tool_response: str = ''
    finish_reason_raw: str = ''
    finish_reason_readable: str = ''

class RuntimeFlags(BaseSettings):
    """程序运行时的临时标志位"""
    firstrun_do_not_load: bool = True
    difflib_modified_flag: bool = False 

# >>> 运行时总入口 <<<
class AppRuntime(BaseSettings):
    paths: RuntimePaths = Field(default_factory=RuntimePaths)
    context: ChatContext = Field(default_factory=ChatContext)
    last_response: LastResponseState = Field(default_factory=LastResponseState)
    flags: RuntimeFlags = Field(default_factory=RuntimeFlags)

# 初始化单例
APP_RUNTIME = AppRuntime()