# core/session/session_manager.py
from typing import List, Dict, Optional, TYPE_CHECKING,Callable,Any
from dataclasses import dataclass, field
import copy
import threading
import time
from PyQt6.QtCore import pyqtSignal, QObject,QTimer
from .chat_history_manager import ChathistoryFileManager
from .session_model import ChatSession,ChatMessage

if TYPE_CHECKING:
    from .system_prompt_manager import SystemPromptPreset
    
_NOTHING = object()
class AutosaveWorker:
    """
    后台自动保存工作线程，负责节流（cooldown）与异步持久化。

    与旧版区别：
      - request(payload) 接收一个快照对象
      - save_fn(payload) 在后台线程只操作快照，不读外部共享状态
      - 多次 request 在冷却期内合并，只保留最新 payload
    """

    def __init__(
        self,
        save_fn: Callable[[Any], bool],          # ← 改：接收 payload
        cooldown_s: float = 0.150,
        thread_name: str = "autosave-worker",
    ):
        self._save_fn = save_fn
        self._cooldown_s = cooldown_s

        # ---- 状态 ----
        self._cooldown_until: float = 0.0
        self._pending_payload = _NOTHING          # ← 改：替代 bool 标记

        # ---- 线程同步 ----
        self._cv = threading.Condition()
        self._stop = False
        self._kick = False

        # ---- 后台线程 ----
        self._thread = threading.Thread(
            target=self._loop,
            name=thread_name,
            daemon=True,
        )
        self._thread.start()

    # ==================== 公开接口 ====================

    def request(self, payload) -> None:                # ← 改：接收 payload
        """
        请求一次自动保存（可从任意线程调用）。

        多次调用只保留最新 payload，冷却期内不会重复写盘。
        """
        with self._cv:
            # 始终覆盖为最新快照
            self._pending_payload = payload            # ← 改

            now = time.monotonic()
            # 不在冷却期 → 立即唤醒保存
            # 在冷却期   → payload 已存，等冷却结束后补保存
            self._kick = True
            self._cv.notify()

    def flush(self, payload=_NOTHING) -> None:         # ← 改：可选 payload
        """
        阻塞直到所有 pending 保存完成。
        """
        with self._cv:
            if payload is not _NOTHING:
                self._pending_payload = payload
            self._kick = True
            self._cooldown_until = 0.0                 # 跳过冷却
            self._cv.notify()

        while True:
            with self._cv:
                if self._pending_payload is _NOTHING and not self._kick:
                    return
            time.sleep(0.01)

    def reset(self) -> None:
        """重置内部状态（清空 pending 快照和冷却计时器）。"""
        with self._cv:
            self._cooldown_until = 0.0
            self._pending_payload = _NOTHING           # ← 改

    def shutdown(self, timeout: float = 1.0) -> None:
        with self._cv:
            self._stop = True
            self._cv.notify_all()
        self._thread.join(timeout=timeout)

    @property
    def is_alive(self) -> bool:
        return self._thread.is_alive()

    # ==================== 内部实现 ====================

    def _take_payload(self):
        """在持有 _cv 的前提下，取出并清空 pending payload。"""
        p = self._pending_payload
        self._pending_payload = _NOTHING
        return p

    def _loop(self) -> None:
        while True:
            # ---- 阶段 1：等待唤醒 ----
            with self._cv:
                while not self._kick and not self._stop:
                    self._cv.wait()

                if self._stop:
                    return

                self._kick = False

            now = time.monotonic()

            # ---- 阶段 2：不在冷却期 → 立即保存 ----
            if now >= self._cooldown_until:
                with self._cv:
                    payload = self._take_payload()

                if payload is not _NOTHING:
                    self._save_fn(payload)

                with self._cv:
                    self._cooldown_until = time.monotonic() + self._cooldown_s

            # ---- 阶段 3：冷却期循环 ----
            while True:
                with self._cv:
                    if self._stop:
                        return

                    remain = self._cooldown_until - time.monotonic()
                    if remain > 0:
                        self._cv.wait(timeout=remain)
                        continue

                    # 冷却结束
                    payload = self._take_payload()

                    if payload is not _NOTHING:
                        do_save = True
                    else:
                        self._cooldown_until = 0.0
                        do_save = False

                if do_save:
                    self._save_fn(payload)
                    with self._cv:
                        self._cooldown_until = time.monotonic() + self._cooldown_s
                    continue

                break

class _SessionManager(QObject):
    """什么时候资源竞争报错了再用"""
    # 信号定义 - 用于与UI通信
    log = pyqtSignal(str)
    warning = pyqtSignal(str)
    error = pyqtSignal(str)
    notify = pyqtSignal(str)

    # 数据变更信号
    history_loaded = pyqtSignal(ChatSession)

    def __init__(self, history_path: str = ""):
        """
        初始化会话管理器
        
        Args:
            history_path: 历史记录存储路径，默认为应用配置中的 history_path
        """
        super().__init__()
        if not history_path:
            from config import APP_RUNTIME
            history_path = APP_RUNTIME.paths.history_path

        self.history_path = history_path
        self.current_chat = ChatSession()
        self.chathistory_file_manager = ChathistoryFileManager(self.history_path)
        self._cached_history_path = ""

        self._session_lock = threading.RLock()

        # autosave 委托给 AutosaveWorker
        self._autosave_worker = AutosaveWorker(
            save_fn=self._do_autosave_once,
            cooldown_s=0.150,
        )

    # ==================== 锁 & 生命周期 ====================

    @property
    def session_lock(self) -> threading.RLock:
        return self._session_lock

    def shutdown(self):
        """应用退出时调用"""
        self._autosave_worker.shutdown(timeout=1.0)

    def deleteLater(self):
        try:
            self.shutdown()
        finally:
            super().deleteLater()

    # ==================== autosave ====================

    def request_autosave(self):
        """可从任意线程调用，触发一次（节流）自动保存"""
        self._autosave_worker.request()

    def _snapshot_session(self) -> "ChatSession":
        with self._session_lock:
            return copy.deepcopy(self.current_chat)

    def _do_autosave_once(self) -> bool:
        """实际保存回调，由 AutosaveWorker 在后台线程中调用"""
        session = self._snapshot_session()

        if session.chat_rounds <= 1:
            self.log.emit("初始消息触发了自动保存，已跳过。")
            return False

        try:
            self.chathistory_file_manager.save_chathistory(
                chat_session=session,
                folder_path=self.history_path,
            )
            return True
        except Exception as e:
            self.error.emit(f"保存聊天记录失败: {e}")
            return False
        

    @property
    def history(self) -> List[Dict]:
        """
        获取当前聊天历史
        
        Returns:
            List[Dict]: 聊天消息列表，返回的是内部引用
        
        Note:
            外部不要直接修改返回值，如需修改请加锁或调用相关方法
        """
        with self._session_lock:
            return self.current_chat.history

    @history.setter
    def history(self, value: List[Dict]):
        """
        设置聊天历史
        
        Args:
            value: 新的聊天消息列表
        """
        with self._session_lock:
            self.current_chat.history = value
        self.request_autosave()

    @property
    def chat_rounds(self) -> int:
        """
        获取当前会话轮次
        
        Returns:
            int: 对话轮次数
        """
        with self._session_lock:
            return self.current_chat.chat_rounds

    def get_system_message(self) -> Optional[Dict]:
        """
        获取系统消息（第一条role为system的消息）
        
        Returns:
            Optional[Dict]: 系统消息字典，如果没有则返回None
        """
        with self._session_lock:
            if self.current_chat.history and self.current_chat.history[0].get("role") == "system":
                return self.current_chat.history[0]
        return None

    def get_all_role_messages(self, role: str = "") -> List["ChatMessage"]:
        """
        获取指定角色的所有消息
        
        Args:
            role: 角色名称，如"user"、"assistant"、"system"
        
        Returns:
            List[ChatMessage]: 符合条件的消息列表
        """
        with self._session_lock:
            if role:
                return [msg for msg in self.current_chat.history if msg.get("role") == role]
        return []

    def get_last_message(self, role: str = "") -> Optional[Dict]:
        """
        获取最后一条消息
        
        Args:
            role: 角色名称过滤器，为空则返回最后一条，为None也返回最后一条
        
        Returns:
            Optional[Dict]: 最后一条符合条件的消息，没有则返回None
        """
        with self._session_lock:
            if not self.current_chat.history:
                return None

            if role is None:
                return self.current_chat.history[-1]

            for msg in reversed(self.current_chat.history):
                if msg.get("role") == role:
                    return msg
        return None

    # ==================== 文件操作 ====================

    def load_chathistory(self, file_path: str = None) -> "ChatSession":
        """
        从文件加载聊天记录
        
        Args:
            file_path: 聊天记录文件路径
        
        Returns:
            ChatSession: 加载的会话对象
        """
        self._cached_history_path = file_path
        loaded_chat_session = self.chathistory_file_manager.load_chathistory(file_path)
        if loaded_chat_session == ChatSession():
            self.error.emit("failed loading session : empty load result")
            return loaded_chat_session

        with self._session_lock:
            self.current_chat = loaded_chat_session

        self.history_loaded.emit(self.current_chat)
        return self.current_chat

    def save_chathistory(self, file_path: str = None, chat_session: "ChatSession" = None) -> bool:
        """手动保存聊天记录（同步）"""
        if not file_path or not chat_session or chat_session.chat_rounds <= 1:
            self.error.emit("保存聊天记录失败: 文件路径或会话为空")
            return False

        try:
            self.chathistory_file_manager.save_chathistory(
                chat_session=chat_session,
                file_path=file_path,
            )
            return True
        except Exception as e:
            self.error.emit(f"保存聊天记录失败: {e}")
            return False

    def autosave(self, chat_session: "ChatSession" = None) -> bool:
        """
        同步自动保存（保留原 API）
        
        Args:
            chat_session: 要保存的会话对象，为None则保存current_chat的快照
        
        Returns:
            bool: 保存是否成功
        
        Note:
            request_autosave() 推荐用于频繁调用（它会进后台线程并节流）
        """
        if chat_session is None:
            return self._do_autosave_once()

        if chat_session.chat_rounds <= 1:
            self.log.emit("初始消息触发了自动保存，已跳过。")
            return False

        try:
            self.chathistory_file_manager.save_chathistory(
                chat_session=chat_session,
                folder_path=self.history_path,
            )
            return True
        except Exception as e:
            self.error.emit(f"保存聊天记录失败: {e}")
            return False

    # ==================== 历史记录管理 ====================

    @property
    def past_session_list(self) -> List[Dict]:
        """
        获取历史会话列表
        
        Returns:
            List[Dict]: 历史会话信息列表
        """
        return self.chathistory_file_manager.load_past_chats(self.history_path)

    def delete_chathistory(self, file_path: str) -> bool:
        """
        删除聊天记录文件
        
        Args:
            file_path: 要删除的文件路径
        
        Returns:
            bool: 删除是否成功
        """
        try:
            self.chathistory_file_manager.delete_chathistory(file_path)
            self.log.emit(f"聊天记录删除成功：{file_path}")
            return True
        except Exception as e:
            self.error.emit(f"聊天记录删除失败: {e}")
            return False

    def is_saved_current_history(self, file_path: str) -> bool:
        """
        检查当前历史是否已保存（与文件内容比较）
        
        Args:
            file_path: 要比较的文件路径
        
        Returns:
            bool: 当前会话与文件内容是否相同
        """
        if file_path == self._cached_history_path:
            return True
        try:
            loaded = self.chathistory_file_manager.load_chathistory(file_path)
        except Exception as e:
            self.error.emit(f"聊天记录校对：载入旧历史失败。错误原因： {e}")
            return False
        if loaded is None:
            return False

        with self._session_lock:
            cur = self.current_chat
            return self._is_equal(cur, loaded)

    def _is_equal(self, cs1: "ChatSession", cs2: "ChatSession") -> bool:
        """比较两个聊天记录的内容是否在同一 id 树下"""
        if cs1.chat_rounds != cs2.chat_rounds:
            return False
        return cs1.chat_id == cs2.chat_id

    def load_sys_pmt_from_past_record(self, file_path=None) -> str:
        """
        从历史记录加载系统提示词
        
        Args:
            file_path: 历史记录文件路径
        
        Returns:
            str: 系统提示词内容，失败返回空字符串
        """
        if file_path:
            try:
                past_chathistory: ChatSession = self.chathistory_file_manager.load_chathistory(file_path)
                if past_chathistory:
                    return past_chathistory.history[0]["content"]
            except Exception as e:
                self.error.emit(f"failed loading chathistory from {file_path}, error code:{e}")
                return ""
        else:
            self.error.emit("didn't get any valid input to load sys pmt")
            return ""

    # ==================== 会话数据操作 ====================

    def clear_history(self) -> None:
        """清空当前历史记录"""
        self._do_autosave_once()

        # 重置 autosave 状态，避免清空后又补保存
        self._autosave_worker.reset()

        with self._session_lock:
            self.current_chat = ChatSession()

    def create_new_session(self, preset: "SystemPromptPreset") -> "ChatSession":
        """
        创建新会话
        
        Args:
            preset: 系统提示词预设
        
        Returns:
            ChatSession: 新创建的会话对象
        """
        self.clear_history()
        with self._session_lock:
            self.current_chat.apply_preset(preset)
            session = self.current_chat
        self.request_autosave()
        return session

    def update_message_by_id(self, msg_id: str, new_content: str) -> bool:
        """
        根据消息ID更新消息内容
        
        Args:
            msg_id: 消息唯一标识
            new_content: 新的消息内容
        
        Returns:
            bool: 更新是否成功
        """
        try:
            with self._session_lock:
                index = self.current_chat.get_msg_index(msg_id)
                self.current_chat.history[index]["content"] = new_content
            self.request_autosave()
            return True
        except Exception as e:
            self.error.emit(f"编辑消息失败: {e}")
            return False

    def fallback_chat(self, msg_id: str):
        """
        回退到指定消息（包含目标消息）
        
        Args:
            msg_id: 回退目标消息的ID
        """
        with self._session_lock:
            self.current_chat.truncate_to_message(msg_id, include_target=True)
        self.request_autosave()

    def fallback_history_for_resend(self, msg_id: str = "") -> List[Dict]:
        """
        为重发准备历史记录
        
        先回退到指定消息，再截断到最后一条用户消息
        
        Args:
            msg_id: 回退目标消息ID，为空则不回退直接截断
        
        Returns:
            List[Dict]: 处理后的历史记录列表
        """
        if msg_id:
            self.fallback_chat(msg_id)
        with self._session_lock:
            self.current_chat.truncate_to_user()
            if self.current_chat.chat_rounds <= 1:
                self.error.emit("无法重发，当前会话仅剩一条用户消息")
            hist = self.current_chat.history
        self.request_autosave()
        return hist

    # ==================== 运行时会话属性变更 ====================

    def set_title(self, title: str):
        """
        设置会话标题
        
        Args:
            title: 新的标题
        """
        with self._session_lock:
            self.current_chat.title = title
        self.request_autosave()

    def set_avatar(self, avatar: Dict[str, str]) -> None:
        """
        设置会话头像
        
        Args:
            avatar: 头像配置字典
        """
        with self._session_lock:
            self.current_chat.avatars = avatar
        self.request_autosave()

    def set_tools(self, tool: List[str]) -> None:
        """
        设置会话工具列表
        
        Args:
            tool: 工具名称列表
        """
        with self._session_lock:
            self.current_chat.tools = tool
        self.request_autosave()

    def set_system_content(self, content: str) -> None:
        """
        设置系统消息内容
        
        Args:
            content: 新的系统提示词内容
        """
        with self._session_lock:
            if self.current_chat.history and self.current_chat.history[0].get("role") == "system":
                self.current_chat.history[0]["content"] = content
        self.request_autosave()

    def apply_updates(
        self,
        amount: int = 0,
        lci: bool = False,
        bgg: bool = False,
        avatar: Optional[Dict[str, str]] = None,
        tools: Optional[List[str]] = None,
    ):
        """
        应用会话流更新
        :param amount: 会话轮次增量，调用者：工作流
        :param lci:    是否应用到当前会话轮次，调用者：工作流
        :param bgg:    是否应用到背景轮次，调用者：工作流
        :param avatar: 头像更新，调用者：UI
        :param tools:  工具更新，调用者：UI
        """
        with self._session_lock:
            if lci:
                self.current_chat.increment_chat_rounds(amount)
            if bgg:
                self.current_chat.increment_background_rounds(amount)
            if avatar:
                self.current_chat.avatars = avatar
            if tools:
                self.current_chat.tools = tools

        self.request_autosave()

    @property
    def should_generate_title(self) -> bool:
        """
        判断是否需要生成标题
        
        业务规则：对话轮次>=2 且 标题为默认值
        
        Returns:
            bool: 是否需要生成标题
        """
        with self._session_lock:
            session = self.current_chat
            has_enough_context = session.chat_rounds >= 2
            needs_naming = session.is_title_default
        return has_enough_context and needs_naming

class SessionManager(QObject):
    """会话管理器，负责管理当前会话和历史记录"""

    log = pyqtSignal(str)
    warning = pyqtSignal(str)
    error = pyqtSignal(str)
    notify = pyqtSignal(str)

    history_loaded = pyqtSignal(ChatSession)

    def __init__(self, history_path: str = ""):
        """
        初始化会话管理器（无锁版本）
        
        Args:
            history_path: 历史记录存储路径，默认为应用配置中的 history_path
        """
        super().__init__()
        if not history_path:
            from config import APP_RUNTIME
            history_path = APP_RUNTIME.paths.history_path

        self.history_path = history_path
        self.current_chat = ChatSession()
        self.chathistory_file_manager = ChathistoryFileManager(self.history_path)


        # autosave：让 worker 保存"快照"，不要在后台线程读 current_chat
        self._autosave_worker = AutosaveWorker(
            save_fn=self._do_autosave_once,    # 签名改为 (session) -> bool
            cooldown_s=0.150,
        )

    def shutdown(self):
        """应用退出时调用，干净停止后台线程"""
        self._autosave_worker.shutdown(timeout=1.0)

    def deleteLater(self):
        """重写deleteLater，确保先关闭worker再释放对象"""
        try:
            self.shutdown()
        finally:
            super().deleteLater()

    # ==================== autosave ====================

    def _snapshot_session(self) -> "ChatSession":
        """
        创建当前会话的快照（深拷贝）
        
        Returns:
            ChatSession: 当前会话的深拷贝副本
        """
        return copy.deepcopy(self.current_chat)

    def request_autosave(self):
        """
        请求一次自动保存（异步节流）
        
        创建会话快照并提交给后台worker，不阻塞调用线程
        """
        snap = self._snapshot_session()
        self._autosave_worker.request(snap)

    def _do_autosave_once(self, session: "ChatSession") -> bool:
        """
        执行一次自动保存
        
        Args:
            session: 要保存的会话快照
            
        Returns:
            bool: 保存是否成功
        """
        if session.chat_rounds <= 1:
            self.log.emit("初始消息触发了自动保存，已跳过。")
            return False
        try:
            self.chathistory_file_manager.save_chathistory(
                chat_session=session,
                folder_path=self.history_path,
            )
            return True
        except Exception as e:
            self.error.emit(f"保存聊天记录失败: {e}")
            return False

    # ==================== 基本访问 ====================

    @property
    def history(self) -> List[Dict]:
        """
        获取当前聊天历史
        
        Returns:
            List[Dict]: 聊天消息列表
        """
        return self.current_chat.history

    @history.setter
    def history(self, value: List[Dict]):
        """
        设置聊天历史
        
        Args:
            value: 新的聊天消息列表
        """
        self.current_chat.history = value
        self.request_autosave()

    @property
    def chat_rounds(self) -> int:
        """
        获取当前会话轮次
        
        Returns:
            int: 对话轮次数
        """
        return self.current_chat.chat_rounds

    def get_system_message(self) -> Optional[Dict]:
        """
        获取系统消息（第一条role为system的消息）
        
        Returns:
            Optional[Dict]: 系统消息字典，如果没有则返回None
        """
        if self.current_chat.history and self.current_chat.history[0].get("role") == "system":
            return self.current_chat.history[0]
        return None

    def get_all_role_messages(self, role: str = "") -> List["ChatMessage"]:
        """
        获取指定角色的所有消息
        
        Args:
            role: 角色名称，如"user"、"assistant"、"system"
        
        Returns:
            List[ChatMessage]: 符合条件的消息列表
        """
        if role:
            return [msg for msg in self.current_chat.history if msg.get("role") == role]
        return []

    def get_last_message(self, role: str = "") -> Optional[Dict]:
        """
        获取最后一条消息
        
        Args:
            role: 角色名称过滤器，为空则返回最后一条
        
        Returns:
            Optional[Dict]: 最后一条符合条件的消息，没有则返回None
        """
        if not self.current_chat.history:
            return None
        if not role:
            return self.current_chat.history[-1]
        for msg in reversed(self.current_chat.history):
            if msg.get("role") == role:
                return msg
        return None

    # ==================== 文件操作 ====================

    def load_chathistory(self, file_path: str = None) -> "ChatSession":
        """
        从文件加载聊天记录
        
        Args:
            file_path: 聊天记录文件路径
        
        Returns:
            ChatSession: 加载的会话对象
        """
        loaded_chat_session = self.chathistory_file_manager.load_chathistory(file_path)
        if loaded_chat_session == ChatSession():
            self.error.emit("failed loading session : empty load result")
            return loaded_chat_session

        self.current_chat = loaded_chat_session
        self.history_loaded.emit(self.current_chat)
        return self.current_chat

    def save_chathistory(self, file_path: str = None, chat_session: "ChatSession" = None) -> bool:
        """
        手动保存聊天记录（同步）
        
        Args:
            file_path: 保存文件路径
            chat_session: 要保存的会话对象
        
        Returns:
            bool: 保存是否成功
        """
        if not file_path or not chat_session or chat_session.chat_rounds <= 1:
            self.error.emit("保存聊天记录失败: 文件路径或会话为空")
            return False
        try:
            self.chathistory_file_manager.save_chathistory(
                chat_session=chat_session,
                file_path=file_path,
            )
            return True
        except Exception as e:
            self.error.emit(f"保存聊天记录失败: {e}")
            return False

    def autosave(self, chat_session: "ChatSession" = None) -> bool:
        """
        同步自动保存：保存快照/指定 session
        
        Args:
            chat_session: 要保存的会话对象，为None则保存当前会话快照
        
        Returns:
            bool: 保存是否成功
        """
        session = chat_session if chat_session is not None else self._snapshot_session()
        return self._do_autosave_once(session)

     # ==================== 历史记录管理 ====================

    @property
    def past_session_list(self) -> List[Dict]:
        """
        获取历史会话列表
        
        Returns:
            List[Dict]: 历史会话信息列表
        """
        return self.chathistory_file_manager.load_past_chats(self.history_path)

    def delete_chathistory(self, file_path: str) -> bool:
        """
        删除聊天记录文件
        
        Args:
            file_path: 要删除的文件路径
        
        Returns:
            bool: 删除是否成功
        """
        try:
            self.chathistory_file_manager.delete_chathistory(file_path)
            self.log.emit(f"聊天记录删除成功：{file_path}")
            return True
        except Exception as e:
            self.error.emit(f"聊天记录删除失败: {e}")
            return False

    def is_saved_current_history(self, file_path: str) -> bool:
        """
        检查当前历史是否已保存（与文件内容比较）
        
        Args:
            file_path: 要比较的文件路径
        
        Returns:
            bool: 当前会话与文件内容是否相同
        """
        try:
            loaded = self.chathistory_file_manager.load_chathistory(file_path)
        except Exception as e:
            self.error.emit(f"聊天记录校对：载入旧历史失败。错误原因： {e}")
            return False
        if loaded is None:
            return False


    def _is_equal(self, cs1: "ChatSession", cs2: "ChatSession") -> bool:
        """比较两个聊天记录的内容是否在同一 id 树下"""
        if cs1.chat_rounds != cs2.chat_rounds:
            return False
        return cs1.chat_id == cs2.chat_id

    def load_sys_pmt_from_past_record(self, file_path=None) -> str:
        """
        从历史记录加载系统提示词
        
        Args:
            file_path: 历史记录文件路径
        
        Returns:
            str: 系统提示词内容，失败返回空字符串
        """
        if file_path:
            try:
                past_chathistory: ChatSession = self.chathistory_file_manager.load_chathistory(file_path)
                if past_chathistory:
                    return past_chathistory.history[0]["content"]
            except Exception as e:
                self.error.emit(f"failed loading chathistory from {file_path}, error code:{e}")
                return ""
        else:
            self.error.emit("didn't get any valid input to load sys pmt")
            return ""
    
    # ==================== 会话数据操作 ====================

    def clear_history(self) -> None:
        snap = self._snapshot_session()
        self._do_autosave_once(snap)

        self._autosave_worker.reset()
        self.current_chat = ChatSession()

    def create_new_session(self, preset: "SystemPromptPreset") -> "ChatSession":
        """
        创建新会话
        
        Args:
            preset: 系统提示词预设
        
        Returns:
            ChatSession: 新创建的会话对象
        """
        self.clear_history()
        self.current_chat.apply_preset(preset)
        self.request_autosave()
        return self.current_chat

    def update_message_by_id(self, msg_id: str, new_content: str) -> bool:
        """
        根据消息ID更新消息内容
        
        Args:
            msg_id: 消息唯一标识
            new_content: 新的消息内容
        
        Returns:
            bool: 更新是否成功
        """
        try:
            index = self.current_chat.get_msg_index(msg_id)
            self.current_chat.history[index]["content"] = new_content
            self.request_autosave()
            return True
        except Exception as e:
            self.error.emit(f"编辑消息失败: {e}")
            return False

    def fallback_chat(self, msg_id: str):
        """
        回退到指定消息（包含目标消息）
        
        Args:
            msg_id: 回退目标消息的ID
        """
        self.current_chat.truncate_to_message(msg_id, include_target=True)
        self.request_autosave()

    def fallback_history_for_resend(self, msg_id: str = "") -> List[Dict]:
        """
        为重发准备历史记录
        
        先回退到指定消息，再截断到最后一条用户消息
        
        Args:
            msg_id: 回退目标消息ID，为空则不回退直接截断
        
        Returns:
            List[Dict]: 处理后的历史记录列表
        """
        if msg_id:
            self.fallback_chat(msg_id)
        self.current_chat.truncate_to_user()
        if self.current_chat.chat_rounds <= 1:
            self.error.emit("无法重发，当前会话仅剩一条用户消息")
        hist = self.current_chat.history
        self.request_autosave()
        return hist

    def set_title(self, title: str):
        """
        设置会话标题
        
        Args:
            title: 新的标题
        """
        self.current_chat.title = title
        self.request_autosave()

    def set_avatar(self, avatar: Dict[str, str]) -> None:
        """
        设置会话头像
        
        Args:
            avatar: 头像配置字典
        """
        self.current_chat.avatars = avatar
        self.request_autosave()

    def set_tools(self, tool: List[str]) -> None:
        """
        设置会话工具列表
        
        Args:
            tool: 工具名称列表
        """
        self.current_chat.tools = tool
        self.request_autosave()

    def set_system_content(self, content: str) -> None:
        """
        设置系统消息内容
        
        Args:
            content: 新的系统提示词内容
        """
        if self.current_chat.history and self.current_chat.history[0].get("role") == "system":
            self.current_chat.history[0]["content"] = content
        self.request_autosave()

    def apply_updates(self, amount=0, lci=False, bgg=False, avatar=None, tools=None):
        """
        应用会话流更新
        
        Args:
            amount: 会话轮次增量
            lci: 是否应用到当前会话轮次
            bgg: 是否应用到背景轮次
            avatar: 头像更新
            tools: 工具更新
        """
        if lci:
            self.current_chat.increment_chat_rounds(amount)
        if bgg:
            self.current_chat.increment_background_rounds(amount)
        if avatar:
            self.current_chat.avatars = avatar
        if tools:
            self.current_chat.tools = tools
        self.request_autosave()

    @property
    def should_generate_title(self) -> bool:
        """
        判断是否需要生成标题
        
        业务规则：对话轮次>=2 且 标题为默认值
        
        Returns:
            bool: 是否需要生成标题
        """
        session = self.current_chat
        return (session.chat_rounds >= 2) and session.is_title_default

@dataclass
class ChatSessionMap:
    """多会话映射管理"""
    chat_sessions: Dict[str, SessionManager] = field(default_factory=dict)
    
    def get_or_create(self, session_id: str) -> SessionManager:
        """
        获取或创建会话管理器
        
        Args:
            session_id: 会话唯一标识
        
        Returns:
            SessionManager: 对应的会话管理器实例
        """
        if session_id not in self.chat_sessions:
            self.chat_sessions[session_id] = SessionManager()
        return self.chat_sessions[session_id]
    
    def remove(self, session_id: str) -> bool:
        """
        移除指定会话
        
        Args:
            session_id: 要移除的会话ID
        
        Returns:
            bool: 移除是否成功（会话存在则返回True）
        """
        if session_id in self.chat_sessions:
            del self.chat_sessions[session_id]
            return True
        return False
