from core.session.signals import ChatFlowManagerSignalBus,SessionManagerSignalBus

class MainBus(
    ChatFlowManagerSignalBus,
    SessionManagerSignalBus,
    ...
    ):
    pass