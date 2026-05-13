from config import APP_SETTINGS

from core.context.base import ContextComponent
from core.context.model import Descriptor, PrePhase, ContextPayload


class LCIPlacement(ContextComponent):
    """
    处理长对话总结 (LCI) 的位置。
    原 Preprocessor._handle_long_chat_placement
    """

    def descriptor(self) -> Descriptor:
        return Descriptor(
            name="lci_placement",
            phase=PrePhase.INJECT,
            depth=10,
            description="LCI 消息合并",
        )

    def process(self, payload: ContextPayload) -> ContextPayload:
        messages = payload.messages
        placement = APP_SETTINGS.lci.placement

        if placement == "对话第一位" and len(messages) >= 3:
            lci_msg = messages[1]
            next_msg = messages[2]

            if lci_msg['role'] == 'system' and lci_msg.get('info', {}).get('lci'):
                # 合并内容
                next_msg['content'] = lci_msg['content'] + "\n" + next_msg['content']
                # 移除 LCI 消息
                messages.pop(1)

        payload.messages = messages
        return payload
