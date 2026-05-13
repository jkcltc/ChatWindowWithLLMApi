from core.context.base import ContextInjector
from core.context.model import Descriptor, PrePhase, ContextPayload


class MCPContextProvider(ContextInjector):
    """
    MCP resources/prompts 注入。
    新增组件，暂为占位实现。
    """

    target = "before_last_user"

    def descriptor(self) -> Descriptor:
        return Descriptor(
            name="mcp_context_provider",
            phase=PrePhase.INJECT,
            depth=5,
            description="MCP resources/prompts 注入",
        )

    def build_content(self, payload: ContextPayload) -> str | None:
        # TODO: 实现 MCP 上下文注入逻辑
        return None
