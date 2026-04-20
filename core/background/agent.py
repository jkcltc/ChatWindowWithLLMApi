from __future__ import annotations

from typing import TYPE_CHECKING

from .signals import BackgroundSignalBus
from .worker import BackgroundWorker

if TYPE_CHECKING:
    from core.session.session_model import ChatSession
    from config.settings import BackgroundSettings

class BackgroundAgent:
    """背景生成代理（Qt-free）。"""

    def __init__(self):
        self.signals = BackgroundSignalBus()
        self._processing = False

        self.worker = BackgroundWorker()

        self._setup_connections()

    @property
    def is_processing(self) -> bool:
        return self._processing

    def _setup_connections(self):
        # Worker 信号 -> Agent 信号
        self.worker.signals.poll_success.connect(self._on_generate_success)
        self.worker.signals.error.connect(self._on_generate_error)
        self.worker.signals.warning.connect(self.signals.warning.emit)
        self.worker.signals.log.connect(self.signals.log.emit)

    def _on_generate_success(self, image_path: str):
        self._processing = False
        self.signals.log.emit("BackgroundAgent unlocked after success")
        self.signals.poll_success.emit(image_path)

    def _on_generate_error(self, message: str):
        self._processing = False
        self.signals.log.emit("BackgroundAgent unlocked after error")
        self.signals.error.emit(message)

    # ==================== 公开方法 ====================
    def generate(self, chat_session: "ChatSession",cfg:'BackgroundSettings' = None):
        """
        生成背景图
        需要传 ChatSession，其他参数全从 APP_SETTINGS.background 读
        """
        # 保底自检
        if self._processing:
            self.signals.warning.emit('[BackgroundAgent] 正在处理中，忽略重复请求')
            return False

        if not cfg.enabled:
            return False

        if cfg.lock:
            # 锁定模式，不自动生成
            return False
        
        history = chat_session.history
        
        if len(history)<=1:
            import traceback
            message = '\n'.join(traceback.format_stack())
            self.signals.warning.emit(f'初始消息触发了图像生成：{message}')
            return

        self._processing = True
        self.signals.log.emit("BackgroundAgent locked: generate start")
        try:
            self.worker.generate(history,cfg=cfg)
        except Exception as e:
            self._processing = False
            self.signals.error.emit(f"BackgroundAgent generate exception: {e}")
        return True
    
    def force_generate(self, chathistory: list):
        """强制生成，忽略 enabled 和 lock 状态"""
        if self._processing:
            return False
        
        if len(chathistory)<=1:
            import traceback
            message = '\n'.join(traceback.format_stack())
            self.signals.warning.emit(f'初始消息触发了图像生成：{message}')
            return

        self._processing = True
        self.signals.log.emit("BackgroundAgent locked: force_generate start")
        try:
            self.worker.generate(chathistory)
        except Exception as e:
            self._processing = False
            self.signals.error.emit(f"BackgroundAgent force_generate exception: {e}")
        return True
