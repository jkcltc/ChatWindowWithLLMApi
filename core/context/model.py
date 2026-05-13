from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional, Union,TYPE_CHECKING
if TYPE_CHECKING:
    from core.session.data import ChatCompletionPack


# ==================== 前处理 Phase ====================

class PrePhase(Enum):
    PRE_PROCESS = 100      # 原始数据准备
    TRANSFORM   = 200      # 消息变换（裁切、截断）
    INJECT      = 300      # 内容注入（搜索、LCI、MCP、Skill）
    DECORATE    = 400      # 字符串替换、name 注入
    FINALIZE    = 500      # 兜底（purge、params、patch）


# ==================== 流处理 Phase ====================

class StreamPhase(Enum):
    REWRITE = 100                   # 流式内容改写


# ==================== 后处理 Phase ====================

class PostPhase(Enum):
    VALIDATE = 100                  # 响应校验与元数据标注
    REWRITE  = 200                  # 批量内容改写


# ==================== 持久化 Phase ====================

class CommitPhase(Enum):
    TRANSFORM = 100                 # 写入前变换


# ==================== 统一 Phase ====================

AnyPhase = Union[PrePhase, StreamPhase, PostPhase, CommitPhase]


# ==================== 描述符 ====================

@dataclass
class Descriptor:
    name: str
    phase: AnyPhase
    depth: int = 0
    description: str = ""


# ==================== 持久化操作 ====================

@dataclass
class PendingWrite:
    """组件声明的延迟持久化写操作"""
    action: Literal[
        "insert_by_anchor",         # 在锚点消息后插入: {items, anchor_id}
        "insert_by_index",          # 按索引插入: {items, index}
        "add_messages",             # 追加消息到末尾: {messages}
        "edit_message",             # 按ID编辑: {id, content}
        "edit_by_index",            # 按索引编辑: {index, content}
        "delete_message_by_ids",    # 按ID删除: {ids: [str, ...]}
        "delete_message_by_indexes",# 按索引删除: {indexes: [int, ...]}
    ]
    payload: Dict[str, Any]
    source: str
    tag: str = ""


# ==================== 前处理载荷 ====================

@dataclass
class ContextPayload:
    messages: List[Dict]
    params: Dict[str, Any]
    pack:  "ChatCompletionPack"
    meta: Dict[str, Any] = field(default_factory=dict)
    pending_writes: List[PendingWrite] = field(default_factory=list)


# ==================== 后处理载荷 ====================

@dataclass
class PostPayload:
    response: List[Dict]
    pack: Any
    meta: Dict[str, Any] = field(default_factory=dict)
    pending_writes: List[PendingWrite] = field(default_factory=list)


@dataclass
class PostResult:
    messages: List[Dict]
    tool_calls: List[Dict]
    pending_writes: List[PendingWrite] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ==================== 持久化载荷 ====================

@dataclass
class CommitPayload:
    pending_writes: List[PendingWrite] = field(default_factory=list)
    pack: Any = None
    meta: Dict[str, Any] = field(default_factory=dict)


# ==================== Mod 系统 ====================

@dataclass
class ModHook:
    """Mod 的单个钩子声明"""
    phase: AnyPhase
    depth: int = 50
    handler: Optional[Callable] = None
    stream_on_delta: Optional[Callable] = None
    stream_on_complete: Optional[Callable] = None
    stream_on_reset: Optional[Callable] = None


@dataclass
class ModDescriptor:
    """Mod 描述符，一个 Mod 可挂载到多个 Phase"""
    name: str
    hooks: List[ModHook] = field(default_factory=list)
    description: str = ""
    version: str = "1.0"
    author: str = ""
