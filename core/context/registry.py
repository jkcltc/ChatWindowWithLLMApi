from typing import List

from .base import ContextComponent, PostComponent, CommitComponent


class ContextRegistry:
    """
    内置组件注册表，按 phase:depth 排序。
    用于管理前处理、后处理、持久化的内置组件。
    """

    def __init__(self):
        self._components: List[ContextComponent | PostComponent | CommitComponent] = []

    def register(self, component: ContextComponent | PostComponent | CommitComponent) -> None:
        """注册一个内置组件"""
        self._components.append(component)

    def unregister(self, name: str) -> bool:
        """按名称移除组件"""
        for i, comp in enumerate(self._components):
            if comp.descriptor().name == name:
                self._components.pop(i)
                return True
        return False

    def get_sorted_pipeline(self) -> List[ContextComponent | PostComponent | CommitComponent]:
        """获取按 phase:depth 排序的组件管线"""
        return sorted(
            self._components,
            key=lambda c: (c.descriptor().phase.value, c.descriptor().depth)
        )

    def get_by_name(self, name: str):
        """按名称获取组件"""
        for comp in self._components:
            if comp.descriptor().name == name:
                return comp
        return None

    def list_components(self) -> List[str]:
        """列出所有注册的组件名称"""
        return [c.descriptor().name for c in self._components]
