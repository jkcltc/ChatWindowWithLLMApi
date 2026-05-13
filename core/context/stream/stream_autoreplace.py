from utils.str_tools import StrTools

from core.context.base import StreamPostComponent
from core.context.model import Descriptor, StreamPhase


class StreamAutoReplace(StreamPostComponent):
    """
    流式自动替换，原 MidProcessor 的核心逻辑。
    """

    def __init__(self, ARS_config=None):
        self.ARS_config = ARS_config
        self._raw_buffer = ""
        self._last_processed = ""

    def descriptor(self) -> Descriptor:
        return Descriptor(
            name="stream_autoreplace",
            phase=StreamPhase.REWRITE,
            depth=0,
        )

    def on_delta(self, delta: str) -> str:
        self._raw_buffer += delta
        current = StrTools.vast_replace(
            self._raw_buffer,
            self.ARS_config.autoreplace_from,
            self.ARS_config.autoreplace_to,
        )
        new_part = ""
        if current.startswith(self._last_processed):
            new_part = current[len(self._last_processed):]
        self._last_processed = current
        return new_part

    def on_complete(self) -> str:
        return self._last_processed

    def reset(self):
        self._raw_buffer = ""
        self._last_processed = ""
