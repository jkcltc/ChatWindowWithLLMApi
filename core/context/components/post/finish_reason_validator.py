from core.context.base import PostComponent
from core.context.model import Descriptor, PostPhase, PostPayload
from service.chat_completion.request_model import FINISH_REASON_MAP

_VALID_FINISH_REASONS = {k for k in FINISH_REASON_MAP if k is not None} | {"None"}


class FinishReasonValidator(PostComponent):
    """
    校验 finish_reason，标注空回复警告。
    原 PostProcessor._handle_finish_reason
    """

    def descriptor(self) -> Descriptor:
        return Descriptor(
            name="finish_reason_validator",
            phase=PostPhase.VALIDATE,
            depth=0,
            description="校验 finish_reason，标注空回复警告",
        )

    def process(self, payload: PostPayload) -> PostPayload:
        message = payload.response[0]
        finish_reason = str(message['info'].get('finish_reason'))
        if not finish_reason:
            return payload

        warnings = payload.meta.setdefault('warnings', [])

        if finish_reason not in _VALID_FINISH_REASONS:
            warnings.append(f"非正常结束：{message['info']['finish_reason']}")

        if finish_reason != 'content_filter':
            has_content = (
                message.get('content')
                or message.get('reasoning_content')
                or (message.get('tool_calls', [{}])[0].get('function', {}).get('arguments'))
            )

            if not has_content:
                warnings.append(f"空回复: {finish_reason}")

        payload.meta['warnings'] = warnings
        return payload
