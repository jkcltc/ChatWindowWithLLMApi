import copy
from typing import List, Callable, TYPE_CHECKING

from .model import (
    ContextPayload, PostPayload, CommitPayload, PostResult, PendingWrite,
    AnyPhase, Descriptor, PrePhase,
)
from .base import StreamPostComponent, ContextComponent
from .registry import ContextRegistry
from .mod_registry import ModRegistry
from .mod import ContextMod

if TYPE_CHECKING:
    from service.chat_completion.signals import RequesterSignals
    from utils.str_tools import StrTools


DEFAULT_PACK_MOD_PHASE = PrePhase.PRE_PROCESS
DEFAULT_PACK_MOD_DEPTH = 10


def _parse_pack_mod(raw_mod: list) -> dict:
    """
    解析 pack.mod 列表，按 (phase, depth) 分组返回 { (phase, depth): [func, ...] }。

    支持格式:
        callable                          → 默认 phase/depth
        (callable, depth: int)             → 默认 phase，自定义 depth
        (callable, phase: AnyPhase, depth: int) → 完全自定义
    """
    groups: dict = {}
    for entry in raw_mod:
        if callable(entry):
            func, phase, depth = entry, DEFAULT_PACK_MOD_PHASE, DEFAULT_PACK_MOD_DEPTH
        elif isinstance(entry, tuple):
            if len(entry) == 2:
                func, depth = entry
                phase = DEFAULT_PACK_MOD_PHASE
            elif len(entry) == 3:
                func, phase, depth = entry
            else:
                continue
        else:
            continue

        key = (phase, depth)
        groups.setdefault(key, []).append(func)
    return groups


class _PackModAdapter(ContextComponent):
    """将 pack.mod 函数列表适配为管线中的一个 ContextComponent。

    默认 PRE_PROCESS depth=10，紧接 RawMessageComponent(depth=0) 之后，
    在所有 TRANSFORM 组件之前执行，与旧 Preprocessor 的 _handle_mod_functions 行为一致。
    可通过 (func, depth) 或 (func, phase, depth) 自定义位置。
    """
    def __init__(self, name: str, mod_funcs: list, phase=DEFAULT_PACK_MOD_PHASE, depth=DEFAULT_PACK_MOD_DEPTH):
        self._mod_funcs = mod_funcs
        self._phase = phase
        self._depth = depth
        self._name = name

    def descriptor(self) -> Descriptor:
        return Descriptor(
            name=self._name,
            phase=self._phase,
            depth=self._depth,
            description=f"pack.mod adapter (depth={self._depth})",
        )

    def process(self, payload: ContextPayload) -> ContextPayload:
        for func in self._mod_funcs:
            payload.messages = func(payload.messages)
        return payload


class ContextEngine:
    def __init__(
        self,
        pre_registry: ContextRegistry,
        post_registry: ContextRegistry,
        stream_components: List[StreamPostComponent],
        commit_registry: ContextRegistry = None,
    ):
        self.pre_registry = pre_registry
        self.post_registry = post_registry
        self.stream_components = stream_components
        self.commit_registry = commit_registry or ContextRegistry()
        self.mod_registry = ModRegistry()

        self._session_manager = None

        # 流式信号桥接状态
        self._bridge_output_signals = None
        self._requester_signals = None

    def set_session_manager(self, session_manager) -> None:
        self._session_manager = session_manager

    # ==================== Mod API ====================

    def register_mod(self, mod: ContextMod) -> None:
        """注册 Mod，下次请求立即生效"""
        self.mod_registry.register(mod)
        mod.on_activate(self)

    def register_mod_handler(self, name: str, phase: AnyPhase, handler: Callable, depth: int = 50):
        """快捷注册：一个函数即 Mod"""
        self.mod_registry.register_handler(name, phase, handler, depth)
        mod = self.mod_registry._mods.get(name)
        if mod:
            mod.on_activate(self)

    def register_mod_stream(self, name: str, on_delta: Callable, depth: int = 50, **kwargs):
        """快捷注册流式 Mod"""
        self.mod_registry.register_stream_handler(name, depth, on_delta, **kwargs)
        mod = self.mod_registry._mods.get(name)
        if mod:
            mod.on_activate(self)

    def unregister_mod(self, name: str) -> bool:
        """卸载 Mod"""
        mod = self.mod_registry._mods.get(name)
        if mod:
            mod.on_deactivate()
        return self.mod_registry.unregister(name)

    def list_mods(self) -> List[str]:
        """列出已注册 Mod"""
        return self.mod_registry.list_mods()

    # ==================== 前处理 ====================

    def prepare(self, pack) -> tuple:
        """
        前处理：ChatCompletionPack → (messages, params)
        组件产生的 pending_writes 在管线结束后自动提交到 session。
        """
        payload = ContextPayload(
            messages=copy.deepcopy(pack.chat_session.history),
            params={},
            pack=pack,
        )

        # 合并内置 + Mod + pack.mod 适配器，按 phase:depth 统一排序
        all_pre = list(self.pre_registry.get_sorted_pipeline()) + \
                  self.mod_registry.get_pre_components()

        pack_mod_funcs = getattr(pack, 'mod', []) or []
        if pack_mod_funcs:
            groups = _parse_pack_mod(pack_mod_funcs)
            for idx, ((phase, depth), funcs) in enumerate(groups.items()):
                all_pre.append(_PackModAdapter(
                    name=f"_pack_mod_{idx}",
                    mod_funcs=funcs,
                    phase=phase,
                    depth=depth,
                ))

        all_pre.sort(key=lambda c: (c.descriptor().phase.value, c.descriptor().depth))

        for comp in all_pre:
            payload = comp.process(payload)

        # 提交 pending_writes 到 session（不刷新 payload.messages）
        # payload.messages 已经是管线顺序处理后的结果，不需要被 session 快照覆盖。
        if self._session_manager and payload.pending_writes:
            self.commit(self._session_manager, payload.pending_writes, pack)

        return payload.messages, payload.params

    # ==================== 流处理 ====================

    def on_stream_delta(self, req_id: str, delta: str) -> str:
        """流式增量处理"""
        processed = delta
        # 先走内置
        for comp in self.stream_components:
            processed = comp.on_delta(processed)
        # 再走 Mod
        for comp in self.mod_registry.get_stream_components():
            processed = comp.on_delta(processed)
        return processed

    def on_stream_complete(self, req_id: str) -> str:
        """流式完成，获取最终全量文本"""
        results = []
        for comp in self.stream_components:
            results.append(comp.on_complete())
        for comp in self.mod_registry.get_stream_components():
            results.append(comp.on_complete())
        return results[-1] if results else ""

    def reset_stream(self):
        """重置所有流式组件状态"""
        for comp in self.stream_components:
            comp.reset()
        for comp in self.mod_registry.get_stream_components():
            comp.reset()

    def bridge_stream_signals(self, requester_signals: "RequesterSignals") -> "RequesterSignals":
        """
        桥接请求器信号，stream_content 走组件改写，其余直通。
        返回输出信号总线，供上层（RFM）连接。
        """
        from service.chat_completion.signals import RequesterSignals

        output = RequesterSignals()
        self._bridge_output_signals = output
        self._requester_signals = requester_signals

        # 直通非流式信号
        requester_signals.bus_connect(other=output, exclude=['stream_content', 'full_content', 'finished'])

        # 流式内容走组件改写
        requester_signals.stream_content.connect(self._handle_stream_content)

        # finished 信号需要经过 full_content 处理后发射
        requester_signals.finished.connect(self._handle_stream_finished)

        return output

    def _handle_stream_content(self, req_id: str, delta: str):
        """处理流式增量内容"""
        processed_delta = self.on_stream_delta(req_id, delta)
        if processed_delta and self._bridge_output_signals:
            self._bridge_output_signals.stream_content.emit(req_id, processed_delta)

        # 同步更新 full_content
        full = self.on_stream_complete(req_id)
        if self._bridge_output_signals:
            self._bridge_output_signals.full_content.emit(req_id, full)

    def _handle_stream_finished(self, request_id: str, result: list):
        """流式完成后，发射 finished"""
        if self._bridge_output_signals:
            self._bridge_output_signals.finished.emit(request_id, result)

    # ==================== 批量后处理 ====================

    def post_process(self, response: list, pack) -> PostResult:
        """后处理：LLM 响应 → PostResult"""
        payload = PostPayload(response=response, pack=pack)

        all_post = list(self.post_registry.get_sorted_pipeline()) + \
                   self.mod_registry.get_post_components()
        all_post.sort(key=lambda c: (c.descriptor().phase.value, c.descriptor().depth))

        for comp in all_post:
            payload = comp.process(payload)

        return PostResult(
            messages=payload.response,
            tool_calls=payload.meta.get('tool_calls', []),
            pending_writes=payload.pending_writes,
            warnings=payload.meta.get('warnings', []),
        )

    # ==================== 持久化 ====================

    def commit(self, session_manager=None, pending_writes: list = None, pack=None):
        """将前/后处理累积的 pending_writes 经管线变换后统一提交给 SessionManager。
        
        session_manager 可选，未传时使用 set_session_manager() 注入的实例。
        mod 同步写回：engine.commit(pending_writes=[PendingWrite(...)])
        从非主线程调用需使用 commit_threadsafe()。
        """
        if session_manager is None:
            session_manager = self._session_manager
        if session_manager is None:
            raise RuntimeError(
                "commit() 需要 session_manager。"
                "请先调用 engine.set_session_manager() 或显式传入。"
            )
        self._commit_impl(session_manager, pending_writes, pack)

    def commit_threadsafe(self, pending_writes: list = None, pack=None):
        """
        线程安全版 commit，mod 异步写回专用。
        通过 MainThreadDispatcher 将写操作调度到主线程，
        避免 session 信号触发 Qt UI 更新时的跨线程问题。
        
        用法（mod 的任意线程中）：
            engine.commit_threadsafe(pending_writes=[PendingWrite(...)])
        """
        from core.utils.dispatcher import MainThreadDispatcher

        session_manager = self._session_manager
        if session_manager is None:
            raise RuntimeError(
                "commit_threadsafe() 需要 session_manager。"
                "请先调用 engine.set_session_manager()。"
            )

        @MainThreadDispatcher.run_in_main
        def _do_commit():
            self._commit_impl(session_manager, pending_writes, pack)

        _do_commit()

    def _commit_impl(self, session_manager, pending_writes: list, pack=None):
        """commit 的实际实现，commit() 和 commit_threadsafe() 共用"""
        # 1. 构造 CommitPayload，走持久化管线
        payload = CommitPayload(pending_writes=list(pending_writes), pack=pack)
        all_commit = list(self.commit_registry.get_sorted_pipeline()) + \
                     self.mod_registry.get_commit_components()
        all_commit.sort(key=lambda c: (c.descriptor().phase.value, c.descriptor().depth))
        for comp in all_commit:
            payload = comp.process(payload)

        # 2. 落盘
        for write in payload.pending_writes:
            if write.action == "insert_by_anchor":
                session_manager.insert_items_by_anchor(
                    items=write.payload['items'],
                    anchor_id=write.payload['anchor_id'],
                    business_tag=write.tag or write.source,
                )
            elif write.action == "insert_by_index":
                for i, item in enumerate(write.payload['items']):
                    session_manager.history.insert(
                        write.payload['index'] + i, item)
            elif write.action == "add_messages":
                session_manager.add_messages(write.payload['messages'])
            elif write.action == "edit_message":
                session_manager.edit_by_id(
                    id=write.payload['id'],
                    new_content=write.payload['content'],
                )
            elif write.action == "edit_by_index":
                session_manager.edit_by_index(
                    index=write.payload['index'],
                    new_content=write.payload['content'],
                )
            elif write.action == "delete_message_by_indexes":
                session_manager.delete_by_indexes(write.payload['indexes'])
            elif write.action == "delete_message_by_ids":
                session_manager.delete_by_ids(write.payload['ids'])
        session_manager.request_autosave()
