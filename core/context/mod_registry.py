from typing import Callable, Dict, List

from .model import (
    PrePhase, PostPhase, CommitPhase, StreamPhase, AnyPhase,
    ModDescriptor, ModHook,
)
from .base import ContextComponent, PostComponent, CommitComponent, StreamPostComponent
from .mod import ContextMod, _HandlerAsComponent, _HandlerAsPostComponent, _HandlerAsCommitComponent, _HandlerAsStreamComponent, _SingleHookMod, _StreamMod


class ModRegistry:
    """
    Mod 运行时注册表，独立于内置组件注册表。
    支持热插拔：register / unregister 在任意时刻调用，下次请求立即生效。
    """

    def __init__(self):
        self._mods: Dict[str, ContextMod] = {}
        self._cache_valid = False
        self._cached_pre_components: List[ContextComponent] = []
        self._cached_post_components: List[PostComponent] = []
        self._cached_stream_components: List[StreamPostComponent] = []
        self._cached_commit_components: List[CommitComponent] = []

    def register(self, mod: ContextMod) -> None:
        """注册一个 Mod"""
        self._mods[mod.name] = mod
        self._cache_valid = False

    def register_handler(
        self,
        name: str,
        phase: AnyPhase,
        handler: Callable,
        depth: int = 50,
    ) -> None:
        """快捷注册：一个函数即 Mod"""
        mod = _SingleHookMod(name=name, phase=phase, depth=depth, handler=handler)
        self.register(mod)

    def register_stream_handler(
        self,
        name: str,
        depth: int,
        on_delta: Callable[[str], str],
        on_complete: Callable[[], str] = lambda: "",
        on_reset: Callable[[], None] = lambda: None,
    ) -> None:
        """快捷注册流式 Mod"""
        mod = _StreamMod(name=name, depth=depth,
                         on_delta=on_delta, on_complete=on_complete, on_reset=on_reset)
        self.register(mod)

    def unregister(self, name: str) -> bool:
        """按名称卸载 Mod"""
        if name in self._mods:
            del self._mods[name]
            self._cache_valid = False
            return True
        return False

    def get_pre_components(self) -> List[ContextComponent]:
        self._ensure_cache()
        return self._cached_pre_components

    def get_post_components(self) -> List[PostComponent]:
        self._ensure_cache()
        return self._cached_post_components

    def get_stream_components(self) -> List[StreamPostComponent]:
        self._ensure_cache()
        return self._cached_stream_components

    def get_commit_components(self) -> List[CommitComponent]:
        self._ensure_cache()
        return self._cached_commit_components

    def _ensure_cache(self):
        if self._cache_valid:
            return
        self._cached_pre_components = []
        self._cached_post_components = []
        self._cached_stream_components = []
        self._cached_commit_components = []

        for mod in self._mods.values():
            desc = mod.descriptor()
            if not isinstance(desc, ModDescriptor):
                continue
            for hook in desc.hooks:
                if isinstance(hook.phase, StreamPhase):
                    comp = _HandlerAsStreamComponent(
                        name=desc.name, depth=hook.depth,
                        on_delta=hook.stream_on_delta,
                        on_complete=hook.stream_on_complete,
                        on_reset=hook.stream_on_reset,
                    )
                    self._cached_stream_components.append(comp)
                elif isinstance(hook.phase, PrePhase):
                    comp = _HandlerAsComponent(
                        name=desc.name, phase=hook.phase, depth=hook.depth,
                        handler=hook.handler,
                    )
                    self._cached_pre_components.append(comp)
                elif isinstance(hook.phase, PostPhase):
                    comp = _HandlerAsPostComponent(
                        name=desc.name, phase=hook.phase, depth=hook.depth,
                        handler=hook.handler,
                    )
                    self._cached_post_components.append(comp)
                elif isinstance(hook.phase, CommitPhase):
                    comp = _HandlerAsCommitComponent(
                        name=desc.name, depth=hook.depth,
                        handler=hook.handler,
                    )
                    self._cached_commit_components.append(comp)

        # 按 phase:depth 排序
        self._cached_pre_components.sort(
            key=lambda c: (c.descriptor().phase.value, c.descriptor().depth))
        self._cached_post_components.sort(
            key=lambda c: (c.descriptor().phase.value, c.descriptor().depth))
        self._cached_stream_components.sort(key=lambda c: c.descriptor().depth)
        self._cached_commit_components.sort(key=lambda c: c.descriptor().depth)
        self._cache_valid = True

    def get_mod(self, name: str):
        return self._mods.get(name)

    def list_mods(self) -> List[str]:
        return list(self._mods.keys())
