from common.signal_bus import BaseSignalBus
from core.session.signals import ChatFlowManagerSignalBus,SessionManagerSignalBus


class MainBus(
    ChatFlowManagerSignalBus,
    SessionManagerSignalBus,
    metaclass=type(BaseSignalBus)
):
    pass

