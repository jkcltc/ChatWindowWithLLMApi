from typing import List, Dict, Any, Optional, Callable, Union, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
import uuid

if TYPE_CHECKING:
    from core.session.session_model import ChatSession
    from config.settings import ProviderConfig

@dataclass
class ChatCompletionPack:
    """
    用于在不同组件间传递对话请求所需的完整上下文包。
    """
    chat_session: "ChatSession"

    model: str

    provider: "ProviderConfig" = None  # actually config.settings -> ProviderConfig(BaseSettings)

    provider_name:str = None

    tool_list: List[str] = field(default_factory=list)
    """function_manager.selected_tools=>list"""

    optional: Dict[str, Any] = field(default_factory=dict)
    """
    可选参数，包含:
    - temp_style: 临时样式
    - web_search_result: 网络搜索结果，但是Pre已经处理
    - enforce_lower_repeat_text: 强制降重文本
    """

    mod: Optional[List[Callable]] = field(default_factory=list)
    """模组函数列表"""

class RequestType(Enum):
    USER_MESSAGE = "user_message"
    """用户消息"""

    TOOL_MESSAGE="tool_message"
    """工具回调"""

    ASSISTANT_CONTINUE="assistant_continue"
    """中断继续"""

    TOOL_DIRECT_TO_USER = "tool_direct_to_user"
    """用户拦截了工具回调并且立即附上了一条消息"""

