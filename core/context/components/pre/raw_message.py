from config import APP_SETTINGS

from core.context.base import ContextComponent
from core.context.model import Descriptor, PrePhase, ContextPayload


# ==================== 策略函数 ====================

def _cut_from_id(messages, value, first_msg):
    """策略: 从指定 ID 的消息开始保留（含该消息），第0条始终保留"""
    for i in range(1, len(messages)):
        if messages[i].get('info', {}).get('id', '') == value:
            return [first_msg] + messages[i:]
    return messages  # ID 未找到，不裁切


def _cut_from_index(messages, value, first_msg):
    """策略: 从指定索引的消息开始保留（含该消息），第0条始终保留"""
    if isinstance(value, int) and 1 <= value < len(messages):
        return [first_msg] + messages[value:]
    return messages


def _cut_max_rounds(messages, value, first_msg):
    """策略: 按轮数从尾部截取，tool 消息不消耗额度"""
    max_rounds = value if isinstance(value, int) and value > 0 else APP_SETTINGS.generation.max_message_rounds
    quota = max_rounds - 1
    current_valid_count = 0
    recent_messages = []

    for i in range(len(messages) - 1, 0, -1):
        msg = messages[i]
        recent_messages.append(msg)
        if msg.get("role") != "tool":
            current_valid_count += 1
        if current_valid_count >= quota:
            break

    recent_messages.reverse()
    return [first_msg] + recent_messages


# 策略注册表
_STRATEGY_MAP = {
    "cut_from_id": _cut_from_id,
    "cut_from_index": _cut_from_index,
    "max_rounds": _cut_max_rounds,
}

# 默认策略列表（向后兼容无 cut_policies 时）
_DEFAULT_POLICIES = [
    {"type": "cut_from_id", "enabled": False},
    {"type": "cut_from_index", "enabled": False},
    {"type": "max_rounds", "enabled": True},
]


class RawMessageComponent(ContextComponent):
    """
    截取历史消息。

    支持组合式裁切：按 cut_policies 列表顺序依次叠加执行，
    每个策略有 enabled 开关，可调整顺序。

    用法 (pack.optional):
        # 组合式：列表顺序 = 执行顺序，enabled 控制开关
        "cut_policies": [
            {"type": "cut_from_id", "value": "CWLA_xxx", "enabled": True},
            {"type": "max_rounds", "value": 20, "enabled": True},
        ]
        # 上面表示：先按 ID 裁切，再对裁切后的结果按轮数截尾

        # 快捷式（向后兼容，自动转为组合式）
        "cut_from_id": "CWLA_xxx"
        "cut_from_index": 3

    策略类型:
        - cut_from_id:   按消息 ID 裁切头部（保留该 ID 及之后的消息）
        - cut_from_index: 按数组索引裁切头部
        - max_rounds:     按轮数从尾部截取（tool 不消耗额度）
    """

    def descriptor(self) -> Descriptor:
        return Descriptor(
            name="raw_message",
            phase=PrePhase.PRE_PROCESS,
            depth=0,
            description="截取历史，组合式裁切",
        )

    def process(self, payload: ContextPayload) -> ContextPayload:
        messages = payload.messages
        optional = getattr(payload.pack, 'optional', {}) or {}

        if not messages:
            payload.messages = []
            return payload

        if len(messages) <= 1:
            return payload

        # 构建策略列表
        policies = self._resolve_policies(optional)

        # 始终保留第 0 条
        first_msg = messages[0]

        # 按列表顺序依次叠加执行
        for policy in policies:
            if not policy.get('enabled', True):
                continue

            strategy_type = policy.get('type')
            handler = _STRATEGY_MAP.get(strategy_type)
            if not handler:
                continue

            value = policy.get('value')
            # max_rounds 无 value 时使用全局设置
            if strategy_type == 'max_rounds' and value is None:
                value = APP_SETTINGS.generation.max_message_rounds

            messages = handler(messages, value, first_msg)

        payload.messages = messages
        return payload

    @staticmethod
    def _resolve_policies(optional: dict) -> list:
        """
        解析策略配置。

        优先级：
        1. cut_policies 列表 → 直接使用
        2. 快捷字段 cut_from_id / cut_from_index → 自动转为列表
        3. 默认策略 → 只有 max_rounds 启用
        """
        # 1. 组合式
        policies = optional.get('cut_policies')
        if policies and isinstance(policies, list):
            return policies

        # 2. 快捷式向后兼容
        result = list(_DEFAULT_POLICIES)  # 浅拷贝

        cut_from_id = optional.get('cut_from_id')
        if cut_from_id:
            result[0] = {"type": "cut_from_id", "value": cut_from_id, "enabled": True}

        cut_from_index = optional.get('cut_from_index')
        if cut_from_index is not None:
            result[1] = {"type": "cut_from_index", "value": cut_from_index, "enabled": True}

        max_rounds = optional.get('max_rounds')
        if max_rounds is not None:
            result[2] = {"type": "max_rounds", "value": max_rounds, "enabled": True}

        return result
