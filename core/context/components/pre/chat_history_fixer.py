import copy

from core.context.base import ContextComponent
from core.context.model import Descriptor, PrePhase, ContextPayload


class ChatHistoryFixer(ContextComponent):
    """
    修复被截断的聊天记录，保证工具调用的完整性。
    原 Preprocessor._fix_chat_history
    """

    def descriptor(self) -> Descriptor:
        return Descriptor(
            name="chat_history_fixer",
            phase=PrePhase.TRANSFORM,
            depth=0,
            description="截断后首条非 user 时补齐",
        )

    def process(self, payload: ContextPayload) -> ContextPayload:
        messages = payload.messages
        full_history = payload.pack.chat_session.history

        if len(messages) > 1 and messages[1]['role'] != 'user':
            current_length = len(messages)
            cutten_len = len(full_history) - current_length

            if cutten_len > 0:
                for item in reversed(full_history[:cutten_len + 1]):
                    if item['role'] != 'user':
                        messages.insert(1, copy.deepcopy(item))
                    elif item['role'] == 'user':
                        messages.insert(1, copy.deepcopy(item))
                        break

        payload.messages = messages
        return payload
