from typing import Callable, List, Optional, TYPE_CHECKING

from .model import (
    PrePhase, PostPhase, CommitPhase, StreamPhase,
    ContextPayload, PostPayload, CommitPayload,
    ModDescriptor, ModHook,
)
from .base import ContextComponent, PostComponent, CommitComponent, StreamPostComponent, Descriptor

if TYPE_CHECKING:
    from .engine import ContextEngine


class ContextMod:
    """
    Mod 基类。支持两种使用方式：

    1. 轻量：直接传 handler 函数给 register_mod()
    2. 完整：继承 ContextMod，实现多个 on_xxx 方法，跨 Phase 干预

    异步写回：实现 on_activate(engine) 保存 engine 引用，
    在自行管理的线程/定时器中调用 engine.commit(pending_writes=[...])。
    """

    def __init__(self):
        self.config: dict = {}

    # ---- 生命周期 ----

    def on_activate(self, engine: "ContextEngine") -> None:
        """
        Mod 被注册到引擎时调用。
        可在此保存 engine 引用，用于异步写回：
            self._engine = engine
            # ... 在异步线程中:
            self._engine.commit(pending_writes=[...])
        """
        pass

    def on_deactivate(self) -> None:
        """Mod 被卸载时调用，用于清理资源（线程、定时器等）。"""
        pass

    # ---- 子类可覆盖的 Phase 钩子 ----

    def on_pre_process(self, payload: ContextPayload) -> ContextPayload:
        return payload

    def on_transform(self, payload: ContextPayload) -> ContextPayload:
        return payload

    def on_inject(self, payload: ContextPayload) -> ContextPayload:
        return payload

    def on_decorate(self, payload: ContextPayload) -> ContextPayload:
        return payload

    def on_finalize(self, payload: ContextPayload) -> ContextPayload:
        return payload

    def on_validate(self, payload: PostPayload) -> PostPayload:
        return payload

    def on_rewrite(self, payload: PostPayload) -> PostPayload:
        return payload

    def on_commit(self, payload: CommitPayload) -> CommitPayload:
        return payload

    # ---- 流式钩子 ----

    def on_stream_delta(self, delta: str) -> str:
        return delta

    def on_stream_complete(self) -> str:
        return ""

    def on_stream_reset(self):
        pass

    # ---- 辅助 ----

    def descriptor(self) -> ModDescriptor:
        """自动检测已实现的钩子，生成 ModDescriptor"""
        hooks: List[ModHook] = []
        phase_method_map = {
            PrePhase.PRE_PROCESS:  (self.on_pre_process, ContextPayload),
            PrePhase.TRANSFORM:    (self.on_transform, ContextPayload),
            PrePhase.INJECT:       (self.on_inject, ContextPayload),
            PrePhase.DECORATE:     (self.on_decorate, ContextPayload),
            PrePhase.FINALIZE:     (self.on_finalize, ContextPayload),
            PostPhase.VALIDATE:    (self.on_validate, PostPayload),
            PostPhase.REWRITE:     (self.on_rewrite, PostPayload),
            CommitPhase.TRANSFORM: (self.on_commit, CommitPayload),
        }
        base_defaults = set(ContextMod.__dict__.keys())

        for phase, (method, _payload_type) in phase_method_map.items():
            if method.__name__ not in base_defaults or method != getattr(ContextMod, method.__name__, None):
                hooks.append(ModHook(phase=phase, depth=self.default_depth, handler=method))

        # 流式钩子检测
        has_stream = self.on_stream_delta != ContextMod.on_stream_delta
        if has_stream:
            hooks.append(ModHook(
                phase=StreamPhase.REWRITE,
                depth=self.default_depth,
                stream_on_delta=self.on_stream_delta,
                stream_on_complete=self.on_stream_complete,
                stream_on_reset=self.on_stream_reset,
            ))

        return ModDescriptor(name=self.name, hooks=hooks, description=self.description)

    # ---- 子类需设置 ----
    name: str = "unnamed_mod"
    description: str = ""
    default_depth: int = 50


# ==================== 适配器 ====================

class _HandlerAsComponent(ContextComponent):
    """将单个 handler 函数包装为 ContextComponent"""
    def __init__(self, name: str, phase: PrePhase, depth: int, handler: Callable):
        self._desc = Descriptor(name=name, phase=phase, depth=depth)
        self._handler = handler

    def descriptor(self) -> Descriptor:
        return self._desc

    def process(self, payload):
        return self._handler(payload)


class _HandlerAsPostComponent(PostComponent):
    """将单个 handler 函数包装为 PostComponent"""
    def __init__(self, name: str, phase: PostPhase, depth: int, handler: Callable):
        self._desc = Descriptor(name=name, phase=phase, depth=depth)
        self._handler = handler

    def descriptor(self) -> Descriptor:
        return self._desc

    def process(self, payload):
        return self._handler(payload)


class _HandlerAsCommitComponent(CommitComponent):
    """将单个 handler 函数包装为 CommitComponent"""
    def __init__(self, name: str, depth: int, handler: Callable):
        self._desc = Descriptor(name=name, phase=CommitPhase.TRANSFORM, depth=depth)
        self._handler = handler

    def descriptor(self) -> Descriptor:
        return self._desc

    def process(self, payload):
        return self._handler(payload)


class _HandlerAsStreamComponent(StreamPostComponent):
    """将流式 handler 函数包装为 StreamPostComponent"""
    def __init__(self, name: str, depth: int,
                 on_delta: Callable, on_complete: Callable, on_reset: Callable):
        self._desc = Descriptor(name=name, phase=StreamPhase.REWRITE, depth=depth)
        self._on_delta = on_delta
        self._on_complete = on_complete
        self._on_reset = on_reset

    def descriptor(self) -> Descriptor:
        return self._desc

    def on_delta(self, delta: str) -> str:
        return self._on_delta(delta)

    def on_complete(self) -> str:
        return self._on_complete()

    def reset(self):
        self._on_reset()


# ==================== 快捷 Mod 包装 ====================

class _SingleHookMod(ContextMod):
    """将单个 handler 函数包装为 ContextMod，用于 register_handler"""
    def __init__(self, name: str, phase, depth: int, handler: Callable):
        super().__init__()
        self.name = name
        self.default_depth = depth
        self._phase = phase
        self._handler = handler

    def descriptor(self) -> ModDescriptor:
        return ModDescriptor(
            name=self.name,
            hooks=[ModHook(phase=self._phase, depth=self.default_depth, handler=self._handler)],
        )


class _StreamMod(ContextMod):
    """将流式 handler 函数包装为 ContextMod"""
    def __init__(self, name: str, depth: int,
                 on_delta: Callable, on_complete: Callable, on_reset: Callable):
        super().__init__()
        self.name = name
        self.default_depth = depth
        self._on_delta = on_delta
        self._on_complete = on_complete
        self._on_reset = on_reset

    def on_stream_delta(self, delta: str) -> str:
        return self._on_delta(delta)

    def on_stream_complete(self) -> str:
        return self._on_complete()

    def on_stream_reset(self):
        self._on_reset()
