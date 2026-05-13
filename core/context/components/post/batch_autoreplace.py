from utils.str_tools import StrTools

from core.context.base import PostComponent
from core.context.model import Descriptor, PostPhase, PostPayload


class BatchAutoReplace(PostComponent):
    """
    批量 vast_replace，空内容保护。
    原 PostProcessor._content_replace
    """

    def __init__(self, ARS_config=None):
        self.ARS_config = ARS_config

    def descriptor(self) -> Descriptor:
        return Descriptor(
            name="batch_autoreplace",
            phase=PostPhase.REWRITE,
            depth=0,
            description="批量 vast_replace，空内容保护",
        )

    def process(self, payload: PostPayload) -> PostPayload:
        chat_message = payload.response
        content_base = chat_message[0]['content'] or ''

        content = StrTools.vast_replace(
            content_base,
            self.ARS_config.autoreplace_from,
            self.ARS_config.autoreplace_to,
        )

        warnings = payload.meta.setdefault('warnings', [])

        if not content and content_base and content != content_base:
            warnings.append("[CMPL_main_Post] 过度替换警告：响应内容在自动替换完成后为空。")
            content = "_"

        chat_message[0]['content'] = content

        payload.response = chat_message
        payload.meta['warnings'] = warnings
        return payload
