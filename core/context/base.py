from abc import ABC, abstractmethod
from typing import Optional

from .model import Descriptor, ContextPayload, PostPayload, CommitPayload


class ContextComponent(ABC):
    """前处理组件基类"""
    @abstractmethod
    def descriptor(self) -> Descriptor: ...
    @abstractmethod
    def process(self, payload: ContextPayload) -> ContextPayload: ...


class StreamPostComponent(ABC):
    """流处理组件基类"""
    @abstractmethod
    def descriptor(self) -> Descriptor: ...
    @abstractmethod
    def on_delta(self, delta: str) -> str:
        """收到增量文本，返回处理后的增量（可能为空）"""
        ...
    @abstractmethod
    def on_complete(self) -> str:
        """流结束，返回最终全量文本"""
        ...
    @abstractmethod
    def reset(self):
        """重置内部状态"""
        ...


class PostComponent(ABC):
    """批量后处理组件基类"""
    @abstractmethod
    def descriptor(self) -> Descriptor: ...
    @abstractmethod
    def process(self, payload: PostPayload) -> PostPayload: ...


class CommitComponent(ABC):
    """持久化管线组件基类"""
    @abstractmethod
    def descriptor(self) -> Descriptor: ...
    @abstractmethod
    def process(self, payload: CommitPayload) -> CommitPayload: ...


class ContextInjector(ContextComponent):
    """便捷基类：注入一段文本到 messages 的指定位置"""
    target: str = "before_last_user"  # before_last_user | after_system | append_system | as_new_system

    @abstractmethod
    def build_content(self, payload: ContextPayload) -> Optional[str]:
        """返回要注入的内容，返回 None 则跳过"""
        ...

    def process(self, payload: ContextPayload) -> ContextPayload:
        content = self.build_content(payload)
        if content is None:
            return payload
        new_msg = {"role": "system", "content": content}
        if self.target == "before_last_user":
            for i in range(len(payload.messages) - 1, -1, -1):
                if payload.messages[i]["role"] == "user":
                    payload.messages.insert(i, new_msg)
                    break
        elif self.target == "after_system":
            for i in range(len(payload.messages)):
                if payload.messages[i]["role"] != "system":
                    payload.messages.insert(i, new_msg)
                    break
        elif self.target == "append_system":
            payload.messages[0]["content"] += "\n" + content
        elif self.target == "as_new_system":
            payload.messages.insert(1, new_msg)
        return payload
