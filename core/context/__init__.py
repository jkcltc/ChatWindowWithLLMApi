from .engine import ContextEngine
from .model import (
    PrePhase, StreamPhase, PostPhase, CommitPhase,
    AnyPhase,
    Descriptor, PendingWrite,
    ContextPayload, PostPayload, PostResult, CommitPayload,
    ModHook, ModDescriptor,
)
from .base import (
    ContextComponent, StreamPostComponent, PostComponent, CommitComponent, ContextInjector,
)
from .mod import ContextMod
from .mod_registry import ModRegistry
from .registry import ContextRegistry

from .components.pre.raw_message import RawMessageComponent
from .components.pre.chat_history_fixer import ChatHistoryFixer
from .components.pre.special_style import SpecialStyleModifier
from .components.pre.web_search import WebSearchInjector
from .components.pre.mcp_context import MCPContextProvider
from .components.pre.lci_placement import LCIPlacement
from .components.pre.skill_context import SkillContextProvider
from .components.pre.user_char import UserCharHandler
from .components.pre.multimodal import MultimodalFormatter
from .components.pre.purger import MessagePurger
from .components.pre.request_params import RequestParamsBuilder
from .components.pre.provider_patcher import ProviderPatcher

from .components.post.finish_reason_validator import FinishReasonValidator
from .components.post.batch_autoreplace import BatchAutoReplace

from .stream.stream_autoreplace import StreamAutoReplace

# 保留 lci 子模块的导出
from .lci import LciEngine, LCIValidator, LciEvaluation, LciMetrics


def create_default_engine(ARS_config=None) -> ContextEngine:
    """创建默认配置的 ContextEngine"""

    # 前处理注册
    pre_registry = ContextRegistry()
    pre_registry.register(RawMessageComponent())
    pre_registry.register(ChatHistoryFixer())
    pre_registry.register(SpecialStyleModifier())
    pre_registry.register(WebSearchInjector())
    pre_registry.register(MCPContextProvider())
    pre_registry.register(LCIPlacement())
    pre_registry.register(SkillContextProvider())
    pre_registry.register(UserCharHandler())
    pre_registry.register(MultimodalFormatter())
    pre_registry.register(MessagePurger())
    pre_registry.register(RequestParamsBuilder())
    pre_registry.register(ProviderPatcher())

    # 后处理注册
    post_registry = ContextRegistry()
    post_registry.register(FinishReasonValidator())
    post_registry.register(BatchAutoReplace(ARS_config))

    # 流式组件
    stream_comps = [StreamAutoReplace(ARS_config)]

    # 持久化管线（默认无内置组件，由 Mod 按需注入）
    commit_registry = ContextRegistry()

    engine = ContextEngine(pre_registry, post_registry, stream_comps, commit_registry)
    return engine


__all__ = [
    # Engine
    "ContextEngine",
    "create_default_engine",
    # Model
    "PrePhase", "StreamPhase", "PostPhase", "CommitPhase", "AnyPhase",
    "Descriptor", "PendingWrite",
    "ContextPayload", "PostPayload", "PostResult", "CommitPayload",
    "ModHook", "ModDescriptor",
    # Base
    "ContextComponent", "StreamPostComponent", "PostComponent", "CommitComponent", "ContextInjector",
    # Mod
    "ContextMod", "ModRegistry",
    # Registry
    "ContextRegistry",
    # Pre components
    "RawMessageComponent", "ChatHistoryFixer", "SpecialStyleModifier",
    "WebSearchInjector", "MCPContextProvider", "LCIPlacement",
    "SkillContextProvider", "UserCharHandler", "MultimodalFormatter",
    "MessagePurger", "RequestParamsBuilder", "ProviderPatcher",
    # Post components
    "FinishReasonValidator", "BatchAutoReplace",
    # Stream components
    "StreamAutoReplace",
    # LCI
    "LciEngine", "LCIValidator", "LciEvaluation", "LciMetrics",
]
