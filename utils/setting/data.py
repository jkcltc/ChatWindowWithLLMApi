import os,sys
from typing import List, Dict, Optional,Literal
from pydantic import Field, model_validator
from utils.setting.model import BaseSettings

# ==================== 快捷编组 ====================
class LLMUsagePack(BaseSettings):
    provider: str = 'deepseek'
    model: str = 'deepseek-chat'

class LLMDetail(BaseSettings):
    name : str = Field(default="")

    input_ability: List[Literal[
        "text",
        "image",
        "audio",
        "video",
        "file"
    ]] = Field(default=["text","image"]) 

    output_ability: List[Literal[
        "text",
        "image",
        "audio",
        "video",
    ]] = Field(default=["text"])

    tool_ability: bool = True

    default_tool : list[str] = Field(default=[])

    reasoning_ability: bool = True

    extra_body : Dict = Field(default={})

    extra_headers : Dict = Field(default={})


# ==================== 用户配置 ====================

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

    mode : Literal['single','dispersed','mix'] = 'single'

class WebSearchSettings(BaseSettings):
    """手动强制搜索"""
    web_search_enabled: bool = False
    search_engine: str = 'bing'
    search_results_num: int = 5

    use_llm_reformat: bool = False
    reformat_config: LLMUsagePack = Field(default_factory=LLMUsagePack)

    enable_provider_buildin: bool = False

class ForceRepeatSettings(BaseSettings):
    """强制降重"""
    enabled: bool = False
    """启用"""

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

class NameSettings(BaseSettings): 
    """默认/回退名称"""
    user: str = "user"
    ai: str = 'assistant'

    character_enforce: bool = False
    """是否在消息中注入name字段"""

class TTSSettings(BaseSettings): 
    """语音合成配置"""
    tts_enabled: bool = False
    tts_provider: str = '不使用TTS'

class TitleSettings(BaseSettings):
    """自动标题配置"""

    include_sys_pmt: bool = True
    """包含系统提示词"""  # enable_title_creator_system_prompt

    use_local: bool = True
    """是否使用本地生成"""  # title_creator_use_local

    max_length: int = 20
    """生成的标题最大长度"""  # title_creator_max_length

    provider: str = 'siliconflow'
    """模型提供商"""  # title_creator_provider

    model: str = 'Qwen/Qwen3-8B'
    """模型名称"""  # title_creator_model

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

class ProviderConfig(BaseSettings):
    """单个供应商的配置结构"""
    url: str = ""
    key: str = ""
    models: List[str] = Field(default_factory=list)
    provider_type : str = "openai_compatible"

class ApiConfig(BaseSettings):
    """API配置"""

    providers: Dict[str, ProviderConfig] = Field(default_factory=lambda: {
        "baidu": ProviderConfig(
            url="https://qianfan.baidubce.com/v2",
            key="",
            models=["ernie-5.0-thinking-exp", "deepseek-v3.2"],
            provider_type="baidu"
        ),
        "deepseek": ProviderConfig(
            url="https://api.deepseek.com/v1",
            key="",
            models=["deepseek-chat", "deepseek-reasoner"],
            provider_type="deepseek"
        ),
        "siliconflow": ProviderConfig(
            url="https://api.siliconflow.cn/v1",
            key="",
            models=["deepseek-ai/DeepSeek-V3.2", "Pro/deepseek-ai/DeepSeek-V3.2"],
            provider_type="siliconflow"
        ),
        "tencent": ProviderConfig(
            url="https://api.lkeap.cloud.tencent.com/v1",
            key="",
            models=["deepseek-v3.2"],
            provider_type= "openai_compatible" # 兼容最不好的一集
        ),
        "openrouter": ProviderConfig(
            url="https://openrouter.ai/api/v1",
            key="",
            models=[],
            provider_type="openrouter"
        ),
        "novita": ProviderConfig(
            url="https://api.novita.ai/v3",
            key="",
            models=[],
            provider_type="novita_image" # not even chat,why is it here?
        )
    })

    @property
    def model_map(self) -> Dict[str, List[str]]:
        """便捷访问：{provider: [models]}"""
        return {
            name: list(config.models)
            for name, config in self.providers.items()
            if config.models  # 过滤掉空的
        }

    @property
    def endpoints(self) -> Dict[str, tuple]:
        """便捷访问：{provider: (url, key)}"""
        return {
            name: (config.url, config.key)
            for name, config in self.providers.items()
        }

class ModelPollSettings(BaseSettings):
    enabled : bool = False
    """启用模型轮询"""

    model_map : list[LLMUsagePack] = Field(default_factory=list)
    """模型轮询顺序"""

class ConcurrentLayerSettings(BaseSettings):
    name : str = ""
    """层名称"""
    
    model_map : list[str] = Field(default_factory=list)
    """模型并发清单"""

    prompt : str = ""
    """提示词"""

class ModelConcurrent(BaseSettings):
    enabled : bool = False
    """启用汇流优化"""

    layer_count: int = 2
    """汇流优化层数"""

    layers : list[ConcurrentLayerSettings] = Field(default_factory=list)
    """汇流优化层配置"""

class UIStatus(BaseSettings):
    """UI设置"""

    theme: str = r'theme\ds-r1-0528.qss'
    """主题"""

    LLM : LLMUsagePack = Field(default_factory=LLMUsagePack)
    """combobox: model + combobox : provider"""
    
    past_chat_load_count : int = 100
    """历史聊天加载数量"""

# >>> 用户配置总入口 <<<
class AppSettings(BaseSettings):
    generation: GenerationSettings = Field(default_factory=GenerationSettings)
    """生成参数"""

    limits: InputLimitSettings = Field(default_factory=InputLimitSettings)
    """输入限制和请求截断"""

    tts: TTSSettings = Field(default_factory=TTSSettings)
    """TTS"""

    title: TitleSettings = Field(default_factory=TitleSettings)
    """标题生成"""

    replace: AutoReplaceSettings = Field(default_factory=AutoReplaceSettings)
    """响应内容自动替换"""

    lci: LciSettings = Field(default_factory=LciSettings)
    """上下文自动压缩"""

    background: BackgroundSettings = Field(default_factory=BackgroundSettings)
    """背景更新"""

    web_search: WebSearchSettings = Field(default_factory=WebSearchSettings)
    """手动强制搜索"""

    force_repeat: ForceRepeatSettings = Field(default_factory=ForceRepeatSettings)
    """强制降重"""

    concurrent: ModelConcurrent = Field(default_factory=ModelConcurrent)
    """并发优化"""

    model_poll: ModelPollSettings = Field(default_factory=ModelPollSettings)
    """模型轮询"""

    api: ApiConfig = Field(default_factory=ApiConfig)
    """api: 供应商和key"""

    names: NameSettings = Field(default_factory=NameSettings)
    """默认/回退名称"""

    ui: UIStatus = Field(default_factory=UIStatus)
    """UI和UI恢复设置"""

# 初始化单例
APP_SETTINGS = AppSettings()

# ==================== 运行时配置 ====================
class AppPaths(BaseSettings):
    # 先定义成普通字段，给个空字符串当占位符
    application_path: str = ""
    history_path: str = ""
    theme_path: str = ""

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
            
        if not self.theme_path:
            self.theme_path = os.path.join(self.application_path, "theme")

        return self

class ForceRepeatSettings(BaseSettings):
    """强制降重"""
    text: str = ''

# >>> 全局运行时单例 <<<
class AppRuntime(BaseSettings):
    paths: AppPaths = Field(default_factory=AppPaths)
    force_repeat: ForceRepeatSettings = Field(default_factory=ForceRepeatSettings)

APP_RUNTIME=AppRuntime()
