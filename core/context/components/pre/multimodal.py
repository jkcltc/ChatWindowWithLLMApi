from core.context.base import ContextComponent
from core.context.model import Descriptor, PrePhase, ContextPayload


class MultimodalFormatter(ContextComponent):
    """
    将 info.multimodal 合并入 content。
    原 Preprocessor._handle_multimodal_format
    """

    def descriptor(self) -> Descriptor:
        return Descriptor(
            name="multimodal_formatter",
            phase=PrePhase.FINALIZE,
            depth=0,
            description="multimodal 数据合并入 content",
        )

    def process(self, payload: ContextPayload) -> ContextPayload:
        messages = payload.messages
        for single_message in messages:
            if 'info' in single_message and 'multimodal' in single_message['info']:
                text_content = single_message.get('content', '')
                text_message = [{"type": "text", "text": text_content}]
                multimodal_data = single_message['info']['multimodal']
                single_message['content'] = text_message + multimodal_data
        payload.messages = messages
        return payload
