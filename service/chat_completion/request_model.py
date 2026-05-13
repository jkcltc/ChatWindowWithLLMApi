import time
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


FINISH_REASON_MAP = {
    "stop": "对话正常结束。",
    "length": "对话因长度限制提前结束。",
    "content_filter": "对话因内容过滤提前结束。",
    "function_call": "AI 发起了工具调用。",
    "tool_calls": "AI 发起了工具调用。",
    "tool_call": "AI 发起了工具调用。",
    "null": "未完成或进行中",
    "paused": "对话被用户暂停。",
    "empty_message": "服务端空回复。",
    None: "对话结束，未返回完成原因。"
}


class RequestState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RequestConfig:
    key: str = ""
    url: str = ""
    provider_type: str = "openai_compatible"
    timeout_connect: float = 30.0
    timeout_read: float = 180.0


@dataclass
class RequestResult:
    request_id: str
    content: str = ""
    reasoning_content: str = ""
    tool_calls: Optional[List[Dict]] = None
    finish_reason: Optional[str] = None
    model: Optional[str] = None
    usage: Optional[Dict] = None
    server_id: set = field(default_factory=set)

    info: Dict[str, Any] = field(default_factory=dict)
    messages: List[Dict] = field(default_factory=list)

    def to_chat_history(self) -> List[Dict]:
        message = {
            'role': 'assistant',
            'content': self.content,
            'reasoning_content': self.reasoning_content,
            'info': {
                'id': self.request_id,
                'model': self.model,
                'time': time.strftime("%Y-%m-%d %H:%M:%S"),
                'server_id': list(self.server_id),
                'finish_reason': self.finish_reason,
                **(self.usage or {})
            }
        }

        if self.tool_calls:
            message['tool_calls'] = self.tool_calls

        return [message]
