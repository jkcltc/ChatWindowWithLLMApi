import os,sys
from typing import List, Dict, Optional,Literal
from pydantic import Field, model_validator
from config.base import BaseSettings

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


# ============== >>>   用户配置   <<< ==============

# ==================== 伴随请求 ====================

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

class LongChatImprovePersetVars(BaseSettings):
    summary_prompt:str="""
[背景要求]详细提取关键信息，需要严格符合格式。
格式：
所有角色的个人资料:[名字是##,性别是##,年龄是##,关键特征]（名字不明也需要，关键特征两条或更多）
所有角色的人际关系:[角色1:##,角色2:##,..](A对B的关系/感情/评价/事件/关键交互或其他,优先合并同类项)
主线情节总结:[]（总结对话完整发展，着重于发展节点）
支线事件:[##,##,##]（总结所有过去非主线的事件起因和发展节点）
物品栏:[##,##,##]（物品来源，作用）


注意：
1. 提取内容必须客观、完整。禁止遗漏。
2. 使用书面、正式的语言,避免"行业黑话"和趣味性语言。不对思考过程进行解释。
3. 不需要提到暗示，伏笔等内容。
4. 优先使用一句主谓宾齐全的表述，而不是名词组合。
5. 以下可选项如果被显式或直接提到，则写进个人资料的"关键特征"中；如果没有提到，则省略。


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

    # [新增] Single模式的完整模板，替代了原来的 before/after 拼接
    single_update_prompt:str='''基于要求详细提取关键信息。保留之前的信息，加入新总结的信息。
{hint_text}
**已发生事件和当前人物形象**
{context_summary}

**之后的事件**
{new_content}'''

    long_chat_hint_prefix:str='以最高的优先级处理：'

    summary_merge_prompt:str='将两段内容的信息组合。1.禁止缺少或省略信息。\n2.格式符合[背景要求]。\n3.不要做出推断，保留原事件内容。\n内容1：\n'
    summary_merge_prompt_and:str='\n\n内容2：\n'

    dispersed_summary_prompt:str="""请基于背景信息，仅为最新的对话片段撰写摘要。
{hint_text}
### 🎞️ 前情提要 (背景参考，请勿重复)
{context_summary}

### 💬 刚刚发生的对话 (本次总结目标)
{new_content}

### 📝 摘要指令
1. **理解上下文**：利用【前情提要】来解析新对话中的代词（如“他”、“这件事”）指代的对象。
2. **专注当下**：你的输出**必须仅包含**【刚刚发生的对话】中的内容摘要。不要复述前情提要。
3. **客观陈述**：使用第三人称（如“用户询问了...”，“助手回答说...”）。
4. **输出限制**：直接输出摘要文本。
"""

    mix_consolidation_prompt:str='''请将以下片段整合成完整剧情：
{dispersed_contents}'''

class LciSettings(BaseSettings):
    """上下文自动压缩设置"""

    enabled: bool = True
    """启用LCI"""  # long_chat_improve_var

    collect_system_prompt: bool = True
    """系统提示注入压缩上下文"""  # enable_lci_system_prompt

    max_segment_rounds : int = 50
    """触发压缩的最少对话轮数"""  # long_chat_improve_rounds

    max_total_length: int = 8000
    """触发压缩最少的完整对话长度"""  # max_total_length (unchanged)

    max_segment_length: int = 8000
    """触发压缩最少的距离上次对话长度"""  # max_segment_length (unchanged)

    api_provider: Optional[str] = "deepseek"
    """上下文压缩的API供应商"""  # long_chat_improve_api_provider

    model: Optional[str] = "deepseek-chat"
    """上下文压缩的模型"""  # long_chat_improve_model

    hint: str = ''
    """上下文压缩：总结模型的额外关注点"""  # long_chat_hint

    placement: str = ''
    """上下文压缩结果的放置位置"""  # long_chat_placement

    mode : Literal['single','dispersed','mix'] = 'single'

    preset : LongChatImprovePersetVars = Field(default_factory=LongChatImprovePersetVars)

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

# ==================== 请求前处理 ====================

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
    top_p_enable: bool = False
    top_p: float = 0.8
    temperature_enable: bool = False
    temperature: float = 0.7
    presence_penalty_enable: bool = False
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

# ================== 请求后处理 =====================

class AutoReplaceSettings(BaseSettings): 
    """文本自动替换配置"""
    autoreplace_var: bool = False
    autoreplace_from: str = ''
    autoreplace_to: str = ''

# ================== 工具隔离 =====================

class UserToolPermission(BaseSettings):
    """用户工具权限"""
    enabled:bool = True
    names:list = []

# ==================== 快捷键 =====================

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

# ==================== API配置 ====================

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

# ==================== 模型花活 ====================

# 模型轮询
class ModelPollSettings(BaseSettings):
    enabled : bool = False
    """启用模型轮询"""

    mode: Literal['random','order'] = 'order'

    model_map : list[LLMUsagePack] = Field(default_factory=list)
    """模型轮询顺序"""

# 模型聚合
class ModelGroup(BaseSettings):
    """模型聚合存单"""
    strategy: Literal['random', 'order'] = 'order'

    models: List[LLMUsagePack] = Field(default_factory=list)

    description: Optional[str] = ""

class ModelAggregationSettings(BaseSettings):
    enabled: bool = False
    """启用模型聚合"""

    strategy: Literal['random', 'order'] = 'order'

    groups: Dict[str, ModelGroup] = Field(default_factory=dict)

    execution_list: List[str] = Field(default_factory=list)

# 模型并发
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

# ==================== UI设置 ====================

class UIStatus(BaseSettings):
    """UI设置"""

    theme: str = r'theme\ds-r1-0528.qss'
    """主题"""

    LLM : LLMUsagePack = Field(default_factory=LLMUsagePack)
    """combobox: model + combobox : provider"""
    
    past_chat_load_count : int = 100
    """历史聊天加载数量"""

# ==============>>> 用户配置总入口 <<<==============
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

    model_aggregation: ModelAggregationSettings = Field(default_factory=ModelAggregationSettings)
    """模型聚合"""

    api: ApiConfig = Field(default_factory=ApiConfig)
    """api: 供应商和key"""

    names: NameSettings = Field(default_factory=NameSettings)
    """默认/回退名称"""

    ui: UIStatus = Field(default_factory=UIStatus)
    """UI和UI恢复设置"""

    tool_permission: UserToolPermission = Field(default_factory=UserToolPermission)

# 初始化单例
APP_SETTINGS = AppSettings()

# ==================== 运行时配置 ====================
class AppPaths(BaseSettings):
    # 先定义成普通字段，给个空字符串当占位符
    application_path: str = ""
    history_path: str = ""
    theme_path: str = ""
    system_prompt_preset_path: str = ""
    config_path:str = ""

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
            self.history_path = os.path.join(self.application_path,"data", "history")
            
        if not self.theme_path:
            self.theme_path = os.path.join(self.application_path,"data", "theme")
        
        if not self.system_prompt_preset_path:
            self.system_prompt_preset_path = os.path.join(self.application_path, "data","system_prompt_presets")

        if not self.config_path:
            self.config_path = os.path.join(self.application_path, "data","config")

        return self

class ForceRepeatSettings(BaseSettings):
    """强制降重"""
    text: str = ''


class DangerousTools(BaseSettings):
    """危险工具"""
    names:list = []

# >>> 全局运行时单例 <<<
class AppRuntime(BaseSettings):
    paths: AppPaths = Field(default_factory=AppPaths)
    force_repeat: ForceRepeatSettings = Field(default_factory=ForceRepeatSettings)
    dangerous_tools: DangerousTools = Field(default_factory=DangerousTools)

APP_RUNTIME=AppRuntime()
