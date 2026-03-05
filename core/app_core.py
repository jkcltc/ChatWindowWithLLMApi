from config import APP_SETTINGS,APP_RUNTIME
from .signals import MainBus
from .session.session_manager import SessionManager
from .session.chat_flow import ChatFlowManager
from common.info_module import LogManager

class CWLACore:
    """
    存放业务，负责与 UI 层交互。
    但它现在基本上就一仓库。
    """
    def __init__(self):

        self.signals = MainBus()

        self.session_manager = SessionManager()
        self.cfm = ChatFlowManager(self.session_manager)

        self.cfm.signals.bus_connect(self.signals)
        self.session_manager.signals.bus_connect(self.signals)

        self.logger=LogManager(
            name='CWLA',
            file_path=APP_RUNTIME.paths.log_path
        )

        self.signals.log.connect        (self.logger.info)
        self.signals.warning.connect    (self.logger.warning)
        self.signals.error.connect      (self.logger.error)