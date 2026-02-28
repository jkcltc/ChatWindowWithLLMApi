from dataclasses import dataclass, field, asdict, fields
import uuid
import json
from typing import List, Dict, Union, Optional, TypedDict, Literal,TYPE_CHECKING
import copy

if TYPE_CHECKING:
    from .system_prompt_manager import SystemPromptPreset

MEDIA_TYPES = {'image_url', 'image', 'input_audio', 'audio', 'video'}

class MessageInfo(TypedDict, total=False):
    """消息元数据"""
    id: str
    time: Optional[str]
    model: Optional[str]
    # Usage data: 来自供应商返回值
    # completion_tokens: int
    # prompt_tokens: int
    # total_tokens: int
    # ...

class BaseMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    info: MessageInfo

class UserContentImage(TypedDict):
    url: str

class UserContentItem(TypedDict):
    type: Literal["text", "image_url"]
    text: Optional[str]
    image_url: Optional[UserContentImage]

class ToolContentItem(TypedDict):
    type: Literal["text", "image_url"]
    text: Optional[str]
    image_url: Optional[UserContentImage]

class ToolMessage(BaseMessage):
    role: Literal["tool"]
    content: Union[str, List[ToolContentItem]]
    tool_call_id: str

class UserMessage(BaseMessage):
    role: Literal["user"]
    content: Union[str, List[UserContentItem]]

class AssistantMessage(BaseMessage):
    role: Literal["assistant"]
    content: str
    reasoning_content: Optional[str]
    tool_calls: Optional[List[Dict]]

class SystemMessage(BaseMessage):
    role: Literal["system"]
    content: str


ChatMessage = Union[SystemMessage, UserMessage, AssistantMessage,ToolMessage]
DEFAULT_TITLE_SET = {None, '', 'New Chat', 'Untitled Chat'}

@dataclass
class ChatSession:
    """
    ChatSession 类用于管理单个聊天会话的状态和数据。
    它包含了聊天历史记录、会话ID、标题等信息，并提供了操作这些信息的方法。
    """
    history: List[ChatMessage] = field(default_factory=lambda: [
        {
            "role": "system",
            "content": "",
            "info": {
                "id": "system_prompt",
            }
        }
    ])
    chat_id: str = ''
    new_chat_rounds: int = 0
    new_background_rounds: int = 0
    title:str = ""
    name: Dict[str, str] = field(
        default_factory=lambda: {
            "user": "",
            "assistant": ""
        }
    )
    avatars: Dict[str, str] = field(
        default_factory=lambda: {
            "user": "",
            "assistant": ""
        }
    )
    tools: List[str] = field(default_factory=list)
    _version: str = 'V2'
    """ChatSession 类的版本号"""

    # chat_length 缓存相关字段（不参与序列化）
    _cached_chat_length: Optional[int] = field(default=None, init=False, repr=False, compare=False)
    _cached_history_signature: Optional[tuple] = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self):
        if not self.chat_id:
            self.chat_id = str(uuid.uuid4())

    # ==================== 对内速查速改 ====================
    def to_json(self):
        """
        将当前会话对象序列化为 JSON 字符串。
        """
        data_dict = asdict(self)
        return json.dumps(data_dict, ensure_ascii=False, indent=4)
    
    def get_msg_index(self, msg_id: str) -> int:
        """根据 ID 查找消息索引，找不到返回 -1"""
        target_id = str(msg_id) # 提前转一次 string，避免循环里重复转
        for i, msg in enumerate(self.history):
            if str(msg.get('info', {}).get('id')) == target_id:
                return i
        raise ValueError(f"Message with ID {msg_id} not found in history")
    
    def truncate_to_message(self, msg_id: str, include_target: bool = True):
        """
        从后向前截断历史记录到指定消息
        """
        index = self.get_msg_index(msg_id)
        end_index = index + 1 if include_target else index
        # 直接修改自己的数据
        self.history = self.history[:end_index]

    def truncate_to_user(self):
        """
        清理尾部，确保最后一条是用户消息（为重生成做准备）
        """
        if len(self.history) <= 1:
            return

        while len(self.history) > 1 and self.history[-1].get('role') != 'user':
            self.history.pop()

    def apply_preset(self, preset: 'SystemPromptPreset'):
        self.history[0]["content"] = preset.content
        self.avatars = preset.avatars
        self.name = preset.name
        self.tools = preset.tools

    def get_last_n_length(self,n:int=1):
        target_types_set = MEDIA_TYPES
        _len = len
        _str = str

        total = 0

        if n:
            his=self.history[-n:]
        else:
            his=self.history

        for message in his:

            content = message.get('content')
            if not content:
                continue

            if type(content) is str:
                total += _len(content)
                continue

            for item in content:
                try:
                    item_type = item['type']

                    if item_type == 'text':
                        total += _len(item['text'])

                    elif item_type in target_types_set:
                        total += 1000

                    else:
                        total += _len(_str(item))
                except KeyError:
                    total += _len(_str(item))

        return total

    def get_last_message(self, role: str = "") -> Optional[Dict]:
        """获取最后一条消息（可按role过滤）"""
        if not self.history:
            return {}
        if not role:
            return self.history[-1]
        for msg in reversed(self.history):
            if msg.get("role") == role:
                return msg
        return {}
    
    def get_last_index(self, role: str = "") -> int:
        """获取最后一条消息的索引（可按role过滤），找不到返回 -1"""
        if not self.history:
            return -1
        if not role:
            return len(self.history) - 1
        for i in range(len(self.history) - 1, -1, -1):
            if self.history[i].get("role") == role:
                return i
        return -1
    
    @property
    def new_chat_length(self):
        return self.get_last_n_length(self.new_chat_rounds)
    
    @property
    def new_background_length(self):
        return self.get_last_n_length(self.new_background_rounds)

    @property
    def chat_rounds(self) -> int:
        return len(self.history)

    @property
    def chat_length(self):
        return self.get_last_n_length()
        
    
    @classmethod
    def from_json(cls, json_str):
        """
        从 JSON 字符串反序列化创建一个新的 ChatSession 对象。
        这是一个类方法。
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            raise ValueError("[ChatSession]Invalid JSON string provided.")
        valid_fields = {f.name for f in fields(cls)}

        clean_data = {k: v for k, v in data.items() if k in valid_fields}

        # 使用解包操作符 ** 创建新实例
        return cls(**clean_data)

    @classmethod
    def from_dict(cls, data: dict):
        """直接从字典创建对象，避免重复的序列化/反序列化"""
        valid_fields = {f.name for f in fields(cls)}
        clean_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**clean_data)

    @property
    def is_title_default(self) -> bool:
        """标题是否仍为默认/空状态"""
        return self.title in DEFAULT_TITLE_SET


    # ==================== 上下文优化计数器 ====================
    def increment_chat_rounds(self, delta: int = 2) -> None:
        """增加新对话轮次计数"""
        self.new_chat_rounds += delta
    
    def increment_background_rounds(self, delta: int = 2) -> None:
        """增加背景更新轮次计数"""
        self.new_background_rounds += delta
    
    def reset_chat_rounds(self) -> None:
        """重置新对话轮次计数"""
        self.new_chat_rounds = 0
    
    def reset_background_rounds(self) -> None:
        """重置背景更新轮次计数"""
        self.new_background_rounds = 0

    @ property
    def shallow_history(self):
        return list(self.history)
