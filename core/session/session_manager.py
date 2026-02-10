# core/session/session_manager.py
# No Qt Now！
from typing import List, Dict, Optional, TYPE_CHECKING,Callable,Any
from dataclasses import dataclass, field
import copy
import threading
import time
from .chat_history_manager import ChathistoryFileManager
from .session_model import ChatSession,ChatMessage
from psygnal import Signal

if TYPE_CHECKING:
    from .system_prompt_manager import SystemPromptPreset
    
_NOTHING = object()
_NOTHING = object()

class AutosaveWorker:
    def __init__(
        self,
        save_fn: Callable[[Any], bool],
        cooldown_s: float = 0.150,
        thread_name: str = "autosave-worker",
    ):
        self._save_fn = save_fn
        self._cooldown_s = cooldown_s

        self._cooldown_until: float = 0.0
        self._pending_payload = _NOTHING

        self._cv = threading.Condition()
        self._stop = False
        self._kick = False

        # 新增：标记后台线程是否正在执行 save_fn
        self._saving = False

        self._thread = threading.Thread(
            target=self._loop,
            name=thread_name,
            daemon=True,
        )
        self._thread.start()

    def request(self, payload) -> None:
        with self._cv:
            self._pending_payload = payload
            self._kick = True
            self._cv.notify()

    def flush(self, payload=_NOTHING) -> None:
        """
        阻塞直到：所有 pending 都已保存完成，且没有正在进行中的保存。
        """
        with self._cv:
            if payload is not _NOTHING:
                self._pending_payload = payload

            # 强制立即处理：打断冷却
            self._kick = True
            self._cooldown_until = 0.0
            self._cv.notify()

            while True:
                if self._stop:
                    return
                if self._pending_payload is _NOTHING and not self._saving:
                    return
                self._cv.wait(timeout=0.5)

    def reset(self) -> None:
        with self._cv:
            self._cooldown_until = 0.0
            self._pending_payload = _NOTHING
            self._cv.notify_all()

    def shutdown(self, timeout: float = 1.0) -> None:
        with self._cv:
            self._stop = True
            self._cv.notify_all()
        self._thread.join(timeout=timeout)

    @property
    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def _take_payload(self):
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
                    if payload is _NOTHING:
                        self._cooldown_until = 0.0
                        self._cv.notify_all()
                        continue
                    self._saving = True

                try:
                    self._save_fn(payload)
                finally:
                    with self._cv:
                        self._saving = False
                        self._cooldown_until = time.monotonic() + self._cooldown_s
                        self._cv.notify_all()

            # ---- 阶段 3：冷却期循环 ----
            while True:
                with self._cv:
                    if self._stop:
                        return

                    # 冷却期内 request() 可能多次 notify
                    self._kick = False

                    remain = self._cooldown_until - time.monotonic()
                    if remain > 0:
                        self._cv.wait(timeout=remain)
                        continue

                    payload = self._take_payload()
                    if payload is _NOTHING:
                        self._cooldown_until = 0.0
                        self._cv.notify_all()
                        break

                    self._saving = True

                try:
                    self._save_fn(payload)
                finally:
                    with self._cv:
                        self._saving = False
                        self._cooldown_until = time.monotonic() + self._cooldown_s
                        self._cv.notify_all()


class SessionManager:
    """会话管理器，负责管理当前会话和历史记录"""

    log = Signal(str)
    warning = Signal(str)
    error = Signal(str)
    notify = Signal(str)

    history_loaded = Signal(ChatSession)

    def __init__(self, history_path: str = ""):
        """
        初始化会话管理器（无锁版本）

        Args:
            history_path: 历史记录存储路径，默认为应用配置中的 history_path
        """
        if not history_path:
            from config import APP_RUNTIME
            history_path = APP_RUNTIME.paths.history_path

        self.history_path = history_path
        self.current_chat = ChatSession()
        self.chathistory_file_manager = ChathistoryFileManager(self.history_path)

        # autosave：让 worker 保存"快照"，不要在后台线程读 current_chat
        self._autosave_worker = AutosaveWorker(
            save_fn=self._do_autosave_once,   # (session) -> bool
            cooldown_s=0.150,
        )

    def shutdown(self):
        """应用退出时调用，干净停止后台线程"""
        try:
            self._autosave_worker.shutdown(timeout=1.0)
        except Exception:
            # shutdown 不应影响进程退出；按需你也可以 error.emit
            pass

    def __del__(self):
        # 兜底，尽量释放后台线程
        try:
            self.shutdown()
        except Exception:
            pass

    # ==================== autosave ====================

    def _snapshot_session(self) -> "ChatSession":
        """创建当前会话的快照（深拷贝）"""
        return copy.deepcopy(self.current_chat)

    def request_autosave(self):
        """
        请求一次自动保存（异步节流）

        创建会话快照并提交给后台worker，不阻塞调用线程
        """
        snap = self._snapshot_session()
        self._autosave_worker.request(snap)

    def _do_autosave_once(self, session: "ChatSession") -> bool:
        """执行一次自动保存（保存快照）"""
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
        """获取当前聊天历史"""
        return self.current_chat.history

    @history.setter
    def history(self, value: List[Dict]):
        """设置聊天历史"""
        self.current_chat.history = value
        self.request_autosave()

    @property
    def chat_rounds(self) -> int:
        """获取当前会话轮次"""
        return self.current_chat.chat_rounds

    @property
    def chat_id(self) -> str:
        """获取当前会话的唯一标识符"""
        return self.current_chat.chat_id

    def get_system_message(self) -> Optional[Dict]:
        """获取系统消息（第一条role为system的消息）"""
        if self.current_chat.history and self.current_chat.history[0].get("role") == "system":
            return self.current_chat.history[0]
        return None

    def get_all_role_messages(self, role: str = "") -> List["ChatMessage"]:
        """获取指定角色的所有消息"""
        if role:
            return [msg for msg in self.current_chat.history if msg.get("role") == role]
        return []

    def get_last_message(self, role: str = "") -> Optional[Dict]:
        """获取最后一条消息（可按role过滤）"""
        if not self.current_chat.history:
            return None
        if not role:
            return self.current_chat.history[-1]
        for msg in reversed(self.current_chat.history):
            if msg.get("role") == role:
                return msg
        return None
    
    def get_recent_messages(self, n: int = 10) -> List[Dict]:
        """获取最近的n条消息"""
        return self.current_chat.history[-n:]
    
    def get_last_n_message_length(self, n: int = 10) -> int:
        """获取最近的n条消息的长度"""
        return self.current_chat.get_last_n_length(n)
    

    # ==================== 文件操作 ====================

    def load_chathistory(self, file_path: str = None) -> "ChatSession":
        """从文件加载聊天记录"""
        loaded_chat_session = self.chathistory_file_manager.load_chathistory(file_path)
        if loaded_chat_session == ChatSession():
            self.error.emit("failed loading session : empty load result")
            return loaded_chat_session

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
        """同步自动保存：保存快照/指定 session"""
        session = chat_session if chat_session is not None else self._snapshot_session()
        return self._do_autosave_once(session)

    # ==================== 历史记录管理 ====================

    @property
    def past_session_list(self) -> List[Dict]:
        """获取历史会话列表"""
        return self.chathistory_file_manager.load_past_chats(self.history_path)

    def delete_chathistory(self, file_path: str) -> bool:
        """删除聊天记录文件"""
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
        """
        try:
            loaded = self.chathistory_file_manager.load_chathistory(file_path)
        except Exception as e:
            self.error.emit(f"聊天记录校对：载入旧历史失败。错误原因： {e}")
            return False
        if loaded is None:
            return False
        return self._is_equal(self.current_chat, loaded)

    def _is_equal(self, cs1: "ChatSession", cs2: "ChatSession") -> bool:
        """比较两个聊天记录的内容是否在同一 id 树下"""
        if cs1.chat_rounds != cs2.chat_rounds:
            return False
        return cs1.chat_id == cs2.chat_id

    def load_sys_pmt_from_past_record(self, file_path=None) -> str:
        """从历史记录加载系统提示词"""
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
        """创建新会话"""
        self.clear_history()
        self.current_chat.apply_preset(preset)
        self.request_autosave()
        return self.current_chat

    def update_message_by_id(self, msg_id: str, new_content: str) -> bool:
        """根据消息ID更新消息内容"""
        try:
            index = self.current_chat.get_msg_index(msg_id)
            self.current_chat.history[index]["content"] = new_content
            self.request_autosave()
            return True
        except Exception as e:
            self.error.emit(f"编辑消息失败: {e}")
            return False

    def fallback_chat(self, msg_id: str):
        """回退到指定消息（包含目标消息）"""
        self.current_chat.truncate_to_message(msg_id, include_target=True)
        self.request_autosave()

    def fallback_history_for_resend(self, msg_id: str = "") -> List[Dict]:
        """为重发准备历史记录"""
        if msg_id:
            self.fallback_chat(msg_id)
        self.current_chat.truncate_to_user()
        if self.current_chat.chat_rounds <= 1:
            self.error.emit("消息回退失败：消息数不足")
            raise ValueError("消息回退失败：消息数不足")
        hist = self.current_chat.history
        self.request_autosave()
        return hist

    def set_title(self, title: str):
        """设置会话标题"""
        self.current_chat.title = title
        self.request_autosave()

    def set_avatar(self, avatar: Dict[str, str]) -> None:
        """设置会话头像"""
        self.current_chat.avatars = avatar
        self.request_autosave()

    def set_tools(self, tool: List[str]) -> None:
        """设置会话工具列表"""
        self.current_chat.tools = tool
        self.request_autosave()

    def set_system_content(self, content: str) -> None:
        """设置系统消息内容"""
        if self.current_chat.history and self.current_chat.history[0].get("role") == "system":
            self.current_chat.history[0]["content"] = content
        self.request_autosave()

    def apply_updates(self, amount=0, lci=False, bgg=False, avatar=None, tools=None):
        """应用会话流更新"""
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
        """判断是否需要生成标题"""
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
