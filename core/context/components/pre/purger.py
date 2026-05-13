from core.context.base import ContextComponent
from core.context.model import Descriptor, PrePhase, ContextPayload


class MessagePurger(ContextComponent):
    """
    清理 info 字段，恢复 server_id。
    原 Preprocessor._purge_message
    """

    def descriptor(self) -> Descriptor:
        return Descriptor(
            name="message_purger",
            phase=PrePhase.FINALIZE,
            depth=10,
            description="清理 info 字段，恢复 id",
        )

    def process(self, payload: ContextPayload) -> ContextPayload:
        messages = payload.messages
        new_messages = []
        not_needed = ['info']

        for item in messages:
            # recover server_id
            info = item.get('info', {})
            server_id = info.get('server_id', [])
            if server_id:
                item['id'] = server_id[-1]
            temp_dict = {}
            for key, value in item.items():
                if key not in not_needed:
                    temp_dict[key] = value
            new_messages.append(temp_dict)

        payload.messages = new_messages
        return payload
