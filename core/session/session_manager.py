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
import uuid
from core.utils import MainThreadDispatcher as MTD
from .signals import SessionManagerSignalBus
import functools

if TYPE_CHECKING:
    from .system_prompt_manager import SystemPromptPreset
from config.settings import AppPaths,NameSettings,APP_SETTINGS,APP_RUNTIME
    
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

    def __init__(self):
        """
        初始化会话管理器（无锁版本）

        Args:
            history_path: 历史记录存储路径，默认为应用配置中的 history_path
        """

        self.history_path = APP_RUNTIME.paths.history_path
        self.default_avatar_path = APP_RUNTIME.paths.avatar_path
        self.default_names =APP_SETTINGS.names

        self.current_chat = ChatSession()
        self.chathistory_file_manager = ChathistoryFileManager(self.history_path)

        self.signals = SessionManagerSignalBus()

        # autosave：让 worker 保存"快照"，不要在后台线程读 current_chat
        self._autosave_worker = AutosaveWorker(
            save_fn=self._do_autosave_once,   # (session) -> bool
            cooldown_s=0.150,
        )

    @property
    def log(self):
        return self.signals.log

    @property
    def warning(self):
        return self.signals.warning
    
    @property
    def error(self):
        return self.signals.error


    def shutdown(self):
        """应用退出时调用，干净停止后台线程"""
        try:
            self._autosave_worker.shutdown(timeout=1.0)
        except Exception:
            pass

    def __del__(self):
        # 兜底，尽量释放后台线程
        try:
            self.shutdown()
        except Exception:
            pass

    # ==================== autosave ====================

    def _snapshot_session(self) -> "ChatSession":
        """创建当前会话的快照"""
        # 10ms @ 500 msg, 9800X3D
        # return copy.deepcopy(self.current_chat)
        
        # 允许迭代时内容变更以换取性能
        # 6 us @ 5000 msg, 9800X3D
        snap = copy.copy(self.current_chat)
        snap.history = list(self.current_chat.history)
        
        return snap

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
        except RuntimeError as e:
            import traceback
            if "changed size" in str(e):
                self.log.emit(
                    f'保存聊天时发生竞态错误:{e}。\n{traceback.format_exc()}'
                )
            else:
                self.error.emit(
                    f"保存聊天发生未知运行时错误: {e}\n{traceback.format_exc()}"
                )
            return False
        except Exception as e:
            import traceback
            self.error.emit(
                f"保存聊天记录失败: {e}。\n{traceback.format_exc()}"
            )
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
    def title(self) -> str:
        """获取当前会话的标题"""
        return self.current_chat.title
    
    @property
    def chat_id(self) -> str:
        """获取当前会话的唯一标识符"""
        return self.current_chat.chat_id
    
    @property
    def name(self)->dict:
        return self.current_chat.name

    @property
    def avatars(self) -> dict:
        return self.current_chat.avatars

    @property
    def avatar(self) -> dict:
        return self.current_chat.avatars
    
    @property
    def tools(self):
        return self.current_chat.tools
    
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

    def get_last_message(self, role: str = "") -> "ChatMessage":
        """获取最后一条消息（可按role过滤）"""
        return self.current_chat.get_last_message(role=role)
    
    def get_recent_messages(self, n: int = 10) -> List[Dict]:
        """获取最近的n条消息"""
        return self.current_chat.history[-n:]
    
    def get_last_n_message_length(self, n: int = 10) -> int:
        """获取最近的n条消息的长度"""
        return self.current_chat.get_last_n_length(n)

    def edit_by_index(self, index: int, new_content: str) -> None:
        try:
            self.current_chat.edit_by_index(index, new_content)
            self.signals.history_changed(self.chat_id,self.history)
            self.request_autosave()
        except Exception as e:
            self.error.emit(f"编辑消息失败: {e}")
    
    def edit_by_id(self, id: int, new_content: str) -> None:
        index = None
        index = self.current_chat.get_msg_index(id)
        if index is None:
            self.error.emit(f"未找到消息ID: {id}")
            return
        try:
            self.current_chat.edit_by_index(index, new_content)
            self.signals.history_changed(self.chat_id,self.history)
            self.request_autosave()
        except Exception as e:
            self.error.emit(f"编辑消息失败: {e}")


    # ==================== 文件操作 ====================

    def load_chathistory(self, file_path: str = None) -> "ChatSession":
        """从文件加载聊天记录并覆盖"""
        try:
            loaded_chat_session = self.chathistory_file_manager.load_chathistory(file_path)
        except Exception as e:
            self.error.emit(f"载入旧历史失败。错误原因 - {e}")
            return
        if not loaded_chat_session:
            self.error.emit("载入旧历史失败。空结果。")
        if loaded_chat_session == ChatSession():
            self.error.emit("failed loading session : empty load result")
            return loaded_chat_session

        return loaded_chat_session

    def save_chathistory(self, file_path: str = None, chat_session: "ChatSession" = None) -> bool:
        """手动保存聊天记录（同步）"""
        if not file_path:
            file_path = chat_session.chat_id + ".json"
        if not chat_session or chat_session.chat_rounds <= 1:
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

    def is_saved_current_history(self, file_path: str) -> "ChatSession":
        """
        检查当前历史是否已保存（与文件内容比较）
        """
        try:
            print(file_path)
            loaded = self.chathistory_file_manager.load_chathistory(file_path)
        except Exception as e:
            self.signals.error.emit(f"聊天记录校对：载入旧历史失败。错误原因： {e}")
            return ChatSession()

        if loaded is None:
            return ChatSession()
        
        if self._is_equal(self.current_chat, loaded):
            return loaded

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
        self.autosave()

        self._autosave_worker.reset()
        self.current_chat = ChatSession()
        # 空的session，运算量应该不大
        self.signals.session_changed.emit(self.current_chat)

    def _refresh_preset(self):
        self.signals.avatar_changed.emit(self.chat_id,self.current_chat.avatars)
        self.signals.name_changed.emit(self.chat_id,self.current_chat.name)
        self.signals.tool_changed.emit(self.chat_id,self.current_chat.tools)

    def update_system_preset(self, preset: "SystemPromptPreset") -> "ChatSession":
        # preset 包含了系统提示词、头像、名字、工具
        self.current_chat.apply_preset(preset)
        self._refresh_preset()
        self.request_autosave()
        return self.current_chat

    def create_new_session(self, preset: "SystemPromptPreset") -> "ChatSession":
        """创建新会话"""
        self.clear_history()

        avatar = preset.info.get("avatars",{})
        # 设置默认的有效头像和名字
        if avatar:
            self.set_avatar(avatar)
        else:
            self.set_avatar(self.default_avatar_path)
        name=preset.info.get("name",{})
        if name:
            self.set_name(name)
        else:
            self.set_name(self.default_names)

        self.update_system_preset(preset)
        return self.current_chat

    def change_session_by_path(self,path:str) -> "ChatSession":
        self.autosave()
        self.clear_history()
        cs = self.load_chathistory(path)
        if cs:
            self.current_chat = cs
        else:
            return
        self.signals.session_changed.emit(self.current_chat)
        return self.current_chat

    def set_session(self,session:ChatSession) -> "ChatSession":
        self.current_chat = session
        self.signals.session_changed.emit(self.current_chat)
        self.request_autosave()

    def fallback_chat(self, msg_id: str):
        """回退到指定消息（包含目标消息）"""
        self.current_chat.truncate_to_message(msg_id, include_target=True)
        self.request_autosave()
    
    def fallback_history_for_edit(self) -> str:
        self.fallback_history_for_resend()
        content = self.history[-1]["content"]
        muti = self.history[-1].get('info',{}).get('multimodal',[])
        self.history.pop()
        self.request_autosave()
        self.signals.history_changed.emit(self.chat_id, self.history)
        return content,muti
    
    def fallback_history_for_resend(self, msg_id: str = "") -> List[Dict]:
        """为重发准备历史记录"""
        if msg_id:
            self.fallback_chat(msg_id)
        self.current_chat.truncate_to_user()
        if self.current_chat.chat_rounds <= 1:
            self.error.emit("消息回退失败：消息数不足")
        hist = self.current_chat.history
        self.request_autosave()
        self.signals.history_changed.emit(self.chat_id, self.history)
        return hist

    def set_title(self, title: str):
        """设置会话标题"""
        self.current_chat.title = title
        self.request_autosave()
        self.signals.title_changed.emit(self.chat_id,title)

    def set_avatar(self, avatar: Dict[str, str]) -> None:
        """设置会话头像"""

        self.current_chat.avatars = avatar
        self.signals.avatar_changed.emit(self.chat_id,self.current_chat.avatars)
        self.request_autosave()
    
    def set_role_avatar(self,role:str,avatar:str) -> None:
        self.current_chat.avatars[role]=avatar
        self.signals.avatar_changed.emit(self.chat_id,self.current_chat.avatars)
        self.request_autosave()

    def set_name(self, name: Dict[str, str]) -> None:
        """设置会话名称"""
        self.current_chat.name = name
        self.request_autosave()
        self.signals.name_changed.emit(self.chat_id,self.current_chat.name)

    def set_tools(self, tool: List[str]) -> None:
        """设置会话工具列表"""
        self.current_chat.tools = tool
        self.request_autosave()
        self.signals.tool_changed.emit(self.chat_id,self.current_chat.tools)

    def set_system_content(self, content: str) -> None:
        """设置系统消息内容"""
        # system prompt 目前不显示
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
            self.signals.avatar_changed.emit(self.chat_id,self.current_chat.avatars)
        if tools:
            self.current_chat.tools = tools
            self.signals.tool_changed.emit(self.chat_id,self.current_chat.tools)
        self.request_autosave()

    def create_new_message(self,role:str,content: str, multimodal=None,info:dict=None):
        new_msg = {
            'role': role,
            'content': content,
            'info': {
                "id": "CWLA_"+str(uuid.uuid4()),
                "time": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        if multimodal:
            new_msg['info']['multimodal'] = multimodal
        if info:
            for key, value in info.items():
                new_msg['info'][key] = value
        return new_msg
    
    def add_new_message(self,role:str,content: str, multimodal=None,info:dict=None):
        new_msg = self.create_new_message(role,content,multimodal,info)
        self.current_chat.history.append(new_msg)
        self.signals.history_changed.emit(self.chat_id,self.history)
        self.request_autosave()

    def add_messages(self,messages:list[dict]):
        self.current_chat.history.extend(messages)
        self.signals.history_changed.emit(self.chat_id,self.history)
        self.request_autosave()

   # ==================== 业务支持 ====================
    @property
    def should_generate_title(self) -> bool:
        """判断是否需要生成标题"""
        session = self.current_chat
        return (session.chat_rounds >= 2) and session.is_title_default
    
    def get_filtered_context_data(
            self, 
            generated_items: List[Dict], 
            anchor_id: str,business_tag='lci'
        ) -> Optional[Dict]:

        related_ids = []
        seen = set()
        
        for item in generated_items:
            business_meta = item.get('info', {}).get(business_tag, {})
            related = business_meta.get('related', [])
            
            if isinstance(related, str):
                related = [related]
            elif not isinstance(related, list):
                continue
            
            for rid in related:
                if rid and ('CWLA_req' in rid or 'CWLA_user' in rid):
                    if rid not in seen:
                        seen.add(rid)
                        related_ids.append(rid)
        
        try:
            anchor_idx = self.current_chat.get_msg_index(anchor_id)
        except ValueError:
            self.error.emit('Anchor ID not found in chat history')
            return None
        
        id_index_pairs = []
        missing_id = None
        
        for rid in related_ids:
            try:
                idx = self.current_chat.get_msg_index(rid)
                id_index_pairs.append((rid, idx))
            except ValueError:
                missing_id = rid
                break
        
        if missing_id:
            return {
                'related_ids': related_ids,
                'anchor_id': anchor_id,
                'missing_id': missing_id,
                'is_continuous': False,
                'sorted_pairs': [],
                'original_text': ''
            }
        
        # 存在且升序，允许间歇插入消息，如system/tool
        indices = [idx for _, idx in id_index_pairs]
        is_continuous = all(indices[i] < indices[i+1] for i in range(len(indices)-1))
        sorted_pairs = sorted(id_index_pairs, key=lambda x: x[1])
        
        
        texts = []
        for rid, idx in sorted_pairs:
            msg = self.current_chat.history[idx]
            role = msg.get('role', '')
            if role not in ('user', 'assistant'):
                continue
                
            content = msg.get('content', '')
            if isinstance(content, list):
                text_parts = [
                    str(part.get('text', ''))
                    for part in content
                    if isinstance(part, dict) and part.get('type') == 'text'
                ]
                texts.append(' '.join(filter(None, text_parts)))
            else:
                texts.append(str(content))
        
        return {
            'related_ids': related_ids,
            'anchor_id': anchor_id,
            'missing_id': None,
            'is_continuous': is_continuous,
            'sorted_pairs': sorted_pairs,
            'original_text': '\n'.join(texts)
        }
    
    def insert_items_by_anchor(
            self, 
            items: List[Dict], 
            anchor_id: str,
            business_tag:str="lci"
        ) -> bool:

        try:
            anchor_idx = self.current_chat.get_msg_index(anchor_id)
            insert_pos = anchor_idx + 1
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            
            for i, item in enumerate(items):
                item.setdefault('info', {})
                item['info'].setdefault('id', f"{business_tag}_{uuid.uuid4().hex[:8]}")
                item['info'].setdefault('time', current_time)
                item['info'][business_tag] = item.get('info', {}).get(business_tag, {})
                item['role'] = 'system'
                
                self.current_chat.history.insert(insert_pos + i, item)
            
            return True
            
        except Exception as e:
            if hasattr(self, 'error'):
                self.error.emit(f"插入{business_tag}消息失败: {e}")
            return False

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
