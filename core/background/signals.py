from psygnal import Signal
from common.signal_bus import BaseSignalBus


class BackgroundSignalBus(BaseSignalBus):
    """背景生成信号总线（psygnal）。"""

    log = Signal(str)
    warning = Signal(str)
    error = Signal(str)
    poll_success = Signal(str)
