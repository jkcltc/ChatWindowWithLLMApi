import concurrent.futures
import json
import os
import re
import time
import uuid
import copy
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import heapq

from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *

from service.chat_completion import APIRequestHandler

class ChatHistoryTools:
    @staticmethod
    def locate_chat_index(chathistory, request_id):
        for i, msg in enumerate(chathistory):
            info = msg.get('info', {})
            if str(info.get('id')) == str(request_id):
                return i
        return None
    
    @staticmethod
    def patch_history_0_25_1(chathistory, names=None, avatar=None, title='New Chat'):
        # chathistory 保证非空
        import uuid

        request_id = 100001

        for i, item in enumerate(chathistory):
            info = item.get('info')
            if info is None:
                info = {'id': f'patch_{request_id}'}
                item['info'] = info
                request_id += 1

            if i == 0:
                if names and not 'name' in info:
                    info['name'] = names
                if avatar and not 'avatar' in info:
                    info['avatar'] = avatar
                role = item.get('role')
                if role in ('system', 'developer'):
                    info['id'] = 'system_prompt'
                if not 'chat_id' in info:
                    info['chat_id'] = str(uuid.uuid4())
                if not 'title' in info:
                    info['title'] = title
                if not 'tools' in info:
                    info['tools'] = []
        return chathistory
    
    @staticmethod
    def clean_history(chathistory,unnecessary_items=['info']):
        exclude = set(unnecessary_items)
        return [
            {key: value for key, value in item.items() if key not in exclude}
            for item in chathistory
        ]
    
    @staticmethod
    def to_readable_str(chathistory:list[dict],
                        names={}
                        ):
        """
        将聊天历史转换为LLM友好的对话脚本文本。
        1. 忽略 'system' 角色消息。
        2. 自动兼容普通字符串 content 和多模态 list content
        3. 使用 names 字典映射角色显示名称。

        输出:
        -------------------------------------------

        user:
        你好，帮我写一段代码。

        assistant:
        好的，请问您需要使用什么编程语言？
        -------------------------------------------
        """
        lines = []
        names=names
        default={'user':'user','assistant':'assistant','tool':'tool'}
        for key in default.keys():
            if not key in names:
                names[key]=default[key]
        for message in chathistory:
            if message['role']=='system':
                continue
            lines.append(f"\n{names[message['role']]}:")

            # 初始值
            content=''

            # 不用get，没content不是我的问题
            content_meta=message["content"]

            #多模态的content内是个list
            if isinstance(content_meta,list):
                # 复合消息中可能有间断的text消息
                # 对话模板真的会读这个吗
                for items in content_meta:
                    if items['type']=='text':
                        content+=items['text']
            elif isinstance(content_meta,str):
                content=content_meta
            else:
                # 什么怪东西传进来了
                raise ValueError(f"content type error:{content_meta}")

            lines.append(content)
        return '\n'.join(lines)

class TitleGenerator(QObject):
    """标题生成器：支持本地/调用API生成标题，并与编辑器联动"""

    log_signal = pyqtSignal(str)
    warning_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    title_generated = pyqtSignal(str, str)

    def __init__(self, api_handler: Optional['APIRequestHandler'] = None):
        super().__init__()
        self.api_handler = None
        self.provider: Optional[str] = None
        self.model: Optional[str] = None
        self.api_config: Optional[Dict[str, Any]] = None

        self.task_id: Optional[str] = None
        self.add_date_prefix: bool = True
        self.date_prefix_format: str = "[%Y-%m-%d]"
        self._last_max_length: int = 20

        # 绑定（带防护）
        if api_handler is not None:
            self.bind_api_handler(api_handler)

    # ---------- API 处理器绑定/配置 ----------
    def bind_api_handler(self, api_handler: 'APIRequestHandler'):
        """绑定 API 处理器，自动连接完成与错误信号"""
        # 先断开旧的连接
        if self.api_handler:
            self.api_handler.request_completed.disconnect(self._handle_title_response)
            self.api_handler.error_occurred.disconnect(self._on_api_error)

        self.api_handler = api_handler

        # 安全连接
        if self.api_handler:
            self.api_handler.request_completed.connect(self._handle_title_response)
            self.api_handler.error_occurred.connect(self._on_api_error)

    def set_provider(self, provider: str, model: str, api_config: Optional[Dict[str, Any]] = None):
        """设置 API 提供商与配置信息"""
        self.provider = provider
        self.model = model
        self.api_config = api_config or {}
        if self.api_handler and hasattr(self.api_handler, "set_provider"):
            try:
                self.api_handler.set_provider(provider, model, self.api_config)
                self.log_signal.emit(f"API 提供商/模型已设置：{provider}/{model}")
            except Exception as e:
                self.warning_signal.emit(f"设置 API 提供商失败：{e}")
        else:
            # 不阻断，仅日志提示
            self.warning_signal.emit("API handler 未绑定或不支持 set_provider，已跳过设置。")

    # ---------- 本地生成 ----------
    def generate_title_from_history_local(self, chathistory: List[Dict[str, Any]], max_length: int = 20) -> str:
        """从聊天历史本地生成标题（启发式：取首条用户消息）"""
        title = ""
        first_user_msg = next((msg for msg in chathistory if isinstance(msg, dict) and msg.get("role") == "user"), None)
        if first_user_msg:
            title = (first_user_msg.get("content") or "").strip()

        if not title:
            # 若无用户消息，尝试取第一条助手消息
            first_assistant_msg = next((msg for msg in chathistory if isinstance(msg, dict) and msg.get("role") == "assistant"), None)
            if first_assistant_msg:
                title = (first_assistant_msg.get("content") or "").strip()

        if not title:
            title = "New Chat"

        cleaned = self._sanitize_title(title, max_length)

        if self.add_date_prefix and not cleaned.startswith("["):
            cleaned = time.strftime(self.date_prefix_format, time.localtime()) + cleaned

        return cleaned

    # ---------- 创建标题（本地/调用API） ----------
    def create_chat_title(
        self,
        chathistory: List[Dict[str, Any]],
        task_id: Optional[str] = None,
        use_local: bool = False,
        max_length: int = 20,
        include_system_prompt: bool = False
    ):
        """创建聊天标题；若使用 API，需要 API handler 支持 send_request(messages)"""
        if not isinstance(chathistory, list):
            self.error_signal.emit("chathistory 非列表，无法生成标题。")
            self._emit_fail(task_id, "生成失败")
            return

        self.task_id = task_id or str(uuid.uuid4())
        self._last_max_length = max_length

        # 基础校验
        first_user_msg = next((msg for msg in chathistory if isinstance(msg, dict) and msg.get("role") == "user"), None)
        if not first_user_msg or not (first_user_msg.get("content") or "").strip():
            self.warning_signal.emit("未找到有效的用户消息，已使用本地兜底生成。")
            title = self.generate_title_from_history_local(chathistory, max_length=max_length)
            self.title_generated.emit(self.task_id, title)
            return

        if use_local or not self.api_handler or not hasattr(self.api_handler, "send_request"):
            self.log_signal.emit("使用本地逻辑生成标题。")
            title = self.generate_title_from_history_local(chathistory, max_length=max_length)
            self.title_generated.emit(self.task_id, title)
            return

        # 组装提示词（中英双语，尽量降低模型偏差）
        user_content = first_user_msg.get("content", "")
        system_msg = next((msg for msg in chathistory if isinstance(msg, dict) and msg.get("role") == "system"), None)
        system_content = system_msg.get("content", "") if (include_system_prompt and system_msg) else ""

        prompt_parts = []
        if include_system_prompt and system_content:
            prompt_parts = [
                f"请结合以下'AI角色'和'用户输入'，生成一个不超过{max_length}字的简短标题。",
                "要求：仅输出标题本身，不要加引号、句号或其他标点；标题语言应与用户输入一致；要能体现AI对用户输入的处理意图。",
                f"AI角色:\n{system_content}",
                f"用户输入:\n{user_content}",
                "标题："
            ]
        else:
            prompt_parts = [
                f"为下面的用户输入生成一个不超过{max_length}字的简短标题。",
                "要求：仅输出标题本身，不要加引号、句号或其他标点；标题语言应与用户输入一致。",
                f"用户输入:\n{user_content}",
                "标题："
            ]

        message = [{"role": "user", "content": "\n\n".join(prompt_parts)}]

        try:
            self.log_signal.emit("调用 API 请求生成标题...")
            # 仅把核心消息交给 handler；provider/model/api_config 由 set_provider 预设
            self.api_handler.send_request(message)
        except Exception as e:
            self._on_api_error(f"发送 API 请求失败：{e}")

    # ---------- API 响应处理 ----------
    def _handle_title_response(self, response: str, *args, **kwargs):
        """处理 API 返回的响应，兼容多种结构"""
        try:
            raw = response
            text = (raw or "").strip()
            # 只取第一行，去引号
            text = text.splitlines()[0].strip().strip('"').strip("'")
            # 去尾部标点和空白
            text = re.sub(r"[，。！？!?\.\s]+$", "", text)

            # 清洗不支持字符并限长（不含日期前缀）
            cleaned = self._sanitize_title(text, self._last_max_length)

            if self.add_date_prefix and not cleaned.startswith("["):
                cleaned = time.strftime(self.date_prefix_format, time.localtime()) + cleaned

            self.log_signal.emit(f"API 返回标题：{cleaned}")
            self.title_generated.emit(self.task_id or "", cleaned)
        except Exception as e:
            self._on_api_error(f"处理 API 响应异常：{e}")

    def _on_api_error(self, msg: Any):
        """统一 API 错误处理：日志 + 发出失败标题"""
        s = msg if isinstance(msg, str) else str(msg)
        self.warning_signal.emit(f"标题生成错误: \n{s}")
        self._emit_fail(self.task_id, "生成失败")

    def _emit_fail(self, task_id: Optional[str], title: str):
        """失败退路：也要发出 title_generated 以便 UI 解锁"""
        self.title_generated.emit(task_id or "", title)

    # ---------- 内部工具 ----------
    def _sanitize_title(self, text: str, max_length: int) -> str:
        """去除不支持字符/多余空白，限制最大长度"""
        if not isinstance(text, str):
            text = str(text or "")
        # 移除换行与常见不支持字符
        unsupported = r'[\n<>:"/\\|?*{}`,，。.!！:：;；\'"]'
        text = re.sub(unsupported, "", text)
        text = text.strip()
        if not text:
            text = "New Chat"
        if len(text) > max_length:
            text = text[:max_length]
        return text

class ChathistoryFileManager(QObject):
    '''
    ChathistoryFileManager(history_path: str = 'history', title_generator: TitleGenerator() = None)
    A Qt-aware helper class responsible for loading, saving, deleting and enumerating chat history
    files stored in JSON format. Designed for use in PyQt/PySide GUI applications, this manager
    emits Qt signals for logging, warnings and errors and encapsulates file-system safety checks,
    simple filename sanitization, JSON schema validation and a small metadata cache to speed up
    directory listing.
    Signals
    -------
    log_signal(str)
        Emitted for informational messages (e.g. successful saves or deletions).
    warning_signal(str)
        Emitted for recoverable issues (e.g. skipped files, missing files).
    error_signal(str)
        Emitted for unrecoverable problems (e.g. invalid path, permission errors).
    Constructor
    -----------
    history_path: str
        Default directory where chat histories are stored (used by autosave and listing).
    title_generator: TitleGenerator
        Optional object used to generate titles for histories when not provided in file metadata.
        Can be bound later via bind_title_generator().
    Behavior summary
    ----------------
    - Chat histories are JSON files. A valid chat history is represented as a list of dicts where
      each item has a "role" key in {"user","system","assistant","tool"} and contents consistent
      with the role (see validate_json_structure in load_past_chats).
    - The first item in a valid chat history is expected to be the system prompt/info dictionary
      and may contain metadata under the "info" key, e.g. info['chat_id'] and info['title'].
    - Files are read/written with UTF-8 encoding. The manager attempts to create directories as needed.
    - Basic filename sanitation is applied for saving: a set of unsupported characters (newlines,
      angle brackets, slashes, spaces, punctuation, etc.) are removed from the base filename and the
      extension is normalized to ".json".
    - A small metadata cache file ".chat_index.json" inside the history_path is used to avoid
      reparsing each JSON file every time; entries contain at least {"mtime": float, "title": str}.
    - load_past_chats enumerates JSON files in a directory, selects the newest N files efficiently,
      optionally parses files concurrently using a ThreadPoolExecutor (I/O-bound), validates their
      structure, extracts titles (prefers info['title'] when available) and returns a list of
      metadata dicts sorted by modification time.
    - delete_chathistory performs input validation, resolves paths to absolute and real paths,
      restricts deletions to files with allowed extensions ('.json' by default), and refuses to
      delete directories.
    Public methods
    --------------
    bind_title_generator(title_generator: TitleGenerator) -> None
        Bind or replace the title generator used when autosave needs to produce a title.
    load_chathistory(file_path: Optional[str] = None) -> List[dict]
        Prompt the user (via QFileDialog) if file_path is not provided; otherwise load and return
        the parsed JSON content. Emits warning_signal if loading fails. Returns an empty list on failure.
    save_chathistory(chathistory: List[dict], file_path: Optional[str] = None) -> None
        If file_path is None, prompts the user for a save location and regenerates a new chat_id
        (UUID) into chathistory[0]['info']['chat_id'] to avoid ID collisions while preserving
        a user-provided name. Calls internal writer which applies filename sanitation and writes
        JSON (indent=4, ensure_ascii=False). Emits log_signal on success and error_signal on failure,
        and displays a QMessageBox on write errors.
    delete_chathistory(file_path: str) -> None
        Validate input, resolve to an absolute real path and ensure the file has an allowed extension.
        Ensure the target is a file (not a directory) and attempt to delete it. Emits appropriate
        log/warning/error signals for success/failure.
    _aut write helper_
    _write_chathistory_to_file(chathistory: List[dict], file_path: str) -> None
        Internal method that sanitizes file names, ensures the directory exists, writes the JSON
        safely and emits signals / message boxes on failure. Ensures stored filenames end with ".json".
    autosave_save_chathistory(chathistory: List[dict]) -> None
        Save automatically to the configured history_path. The default filename is taken from
        chathistory[0]['info']['chat_id'] and autosave will call save_chathistory() with that path.
        Only performs save if there is more than one message (i.e. not an empty/initial-only history).
    load_sys_pmt_from_past_record(chathistory: Optional[List[dict]] = None,
                                  file_path: Optional[str] = None) -> str
        Retrieve the system prompt/content from either the provided current chathistory or by loading
        a past record at file_path. Returns the system content string when available, otherwise emits
        error_signal and returns an empty string.
    load_past_chats(application_path: str = '', file_count: int = 100) -> List[Dict[str, Any]]
        Enumerate and return up to `file_count` latest valid chat JSON files in `application_path`
        (defaults to the instance's history_path). Each returned dict contains:
          - "file_path": full path to the file
          - "title": extracted title (or "Untitled Chat")
          - "modification_time": float mtime used for sorting
        Uses a lightweight cache file ".chat_index.json" to skip re-parsing unchanged files, and
        parses uncached files concurrently. Emits warning_signal for skipped/invalid files and
        warning_signal if cache update fails.
    is_equal(hist1: List[dict], hist2: List[dict]) -> bool
        Compare two chat histories for identity based on length and the chat_id in the first
        element's info dict. Returns True if they appear to be the same conversation, False otherwise.
    Validation rules (as applied by load_past_chats)
    -----------------------------------------------
    - The JSON root must be a list.
    - Each list item must be a dict with a "role" key equal to one of {"user","system","assistant","tool"}.
    - "user" and "system" items must have a string "content".
    - "assistant" items must have at least one of "content" (string or None) or "tool_calls" (list).
    - "tool" items must include "tool_call_id" and a string "content".
    Thread-safety and concurrency
    -----------------------------
    - The class is intended to be used from the GUI thread for methods that trigger dialogs or
      emit QMessageBox. load_past_chats offloads JSON parsing to a ThreadPoolExecutor because
      parsing is I/O-bound; signals are emitted from the calling thread (the executor callbacks are
      awaited in the same thread before emitting).
    - Access to the on-disk cache is not synchronized beyond simple atomic file write; if multiple
      processes may modify the same history directory simultaneously, external synchronization is
      recommended.
    Error handling and user feedback
    --------------------------------
    - Non-fatal issues (bad files, skipped files, cache write failures) produce warning_signal.
    - Fatal or unusual errors that prevent an operation (invalid path format, permission errors)
      produce error_signal and, when applicable, a QMessageBox to alert the user.
    - Methods generally prefer to fail gracefully (returning empty lists or doing nothing) rather
      than raising exceptions to the caller; however, unexpected exceptions in worker threads are
      caught and surfaced via warning/error signals.
    Example (conceptual)
    --------------------
    mgr = ChathistoryFileManager(history_path='~/.my_app/history', title_generator=my_title_gen)
    mgr.log_signal.connect(lambda s: print('LOG:', s))
    mgr.warning_signal.connect(lambda s: print('WARN:', s))
    mgr.error_signal.connect(lambda s: print('ERR:', s))
    past = mgr.load_past_chats(file_count=20)
    if past:
        # open the latest chat, etc.
        pass
    Notes
    -----
    - This manager expects chat JSON files to follow the application's chosen schema. If your
      persisted files differ, adjust validate_json_structure and extract_chat_title accordingly.
    - Filename sanitation is intentionally conservative to maximize cross-platform compatibility.
    '''
    log_signal = pyqtSignal(str)
    warning_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, history_path='history', title_generator=TitleGenerator()):
        super().__init__()
        self.history_path = history_path
        self.title_generator = title_generator
        self.history_map = {}  # 记录历史文件的id和路径对应关系

    def bind_title_generator(self, title_generator: TitleGenerator):
        self.title_generator = title_generator

    # 载入记录
    def load_chathistory(self, file_path=None) -> list:
        # 弹出文件选择窗口
        chathistory = []
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(
                None, "导入聊天记录", "", "JSON files (*.json);;All files (*)"
            )
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    chathistory = json.load(file)
            except json.JSONDecodeError as e:
                self.error_signal.emit(f'JSON解析错误: {e}')
                return []
            except Exception as e:
                self.error_signal.emit(f'文件读取错误: {e}')
                return []
        else:
            self.warning_signal.emit(f'failed loading chathistory from {file_path}')
            return []
        chathistory=ChatHistoryTools.patch_history_0_25_1(
                    chathistory,
                    names={
                        'user':'',
                        'assistant':''
                        },
                    avatar={
                    'user':'',
                    'assistant':''
                    }
                )
        return chathistory

    # 保存聊天记录
    def save_chathistory(self, chathistory, file_path=None):
        if len(chathistory) == 1 or len(chathistory) == 0:
            self.warning_signal.emit(f'save_chathistory|false activity:空记录')
            QMessageBox.warning(None, '警告', '空记录，保存已取消')
            return
        if not file_path:
            # 弹出文件保存窗口
            file_path, _ = QFileDialog.getSaveFileName(
                None, "保存聊天记录", "", "JSON files (*.json);;All files (*)"
            )
            # 更新历史的UUID，防止重复，用户自定义的名字保留
            chathistory[0]['info']['chat_id'] = str(uuid.uuid4())
        self._write_chathistory_to_file(chathistory, file_path)

    def delete_chathistory(self, file_path: str):
        # 输入验证
        if not file_path or not isinstance(file_path, str):
            self.warning_signal.emit(f"Invalid file path provided: {file_path}")
            return
        
        # 路径规范化检查
        try:
            # 转换为绝对路径并解析符号链接
            normalized_path = os.path.realpath(os.path.abspath(file_path))
        except Exception as e:
            self.error_signal.emit(f"Invalid path format: {e}")
            return
        
        
        # 文件扩展名检查
        allowed_extensions = {'.json'}  # 根据实际需求调整
        file_extension = Path(normalized_path).suffix.lower()
        if allowed_extensions and file_extension not in allowed_extensions:
            self.error_signal.emit(f"File type not allowed: {file_extension}")
            return
        
        # 执行删除操作
        if os.path.exists(normalized_path):
            try:
                # 额外检查：确保是文件而不是目录
                if not os.path.isfile(normalized_path):
                    self.error_signal.emit("Cannot delete directories")
                    return
                    
                os.remove(normalized_path)
                self.log_signal.emit(f"Deleted chat history file: {normalized_path}")
            except Exception as e:
                self.error_signal.emit(f"Failed to delete file {normalized_path}: {e}")
        else:
            self.warning_signal.emit(f"File not found for deletion: {normalized_path}")

    # 写入聊天记录到本地
    def _write_chathistory_to_file(self, chathistory: list, file_path: str):
        # 分离路径和文件名，只清洗文件名部分
        dir_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        
        # 清洗文件名（不包括扩展名）
        unsupported_chars = ["\n", '<', '>', ':', '"', '/', '\\', '|', '?', '*', '{', '}', ',', '，', '。', ' ', '!', '！']
        name_without_ext, ext = os.path.splitext(file_name)
        
        for char in unsupported_chars:
            name_without_ext = name_without_ext.replace(char, '')
        
        # 重新组合路径
        cleaned_file_name = name_without_ext + (ext if ext else '.json')
        if not cleaned_file_name.endswith('.json'):
            cleaned_file_name += '.json'
        
        file_path = os.path.join(dir_path, cleaned_file_name) if dir_path else cleaned_file_name

        if file_path and file_name:  # 检查 file_path 是否有效, file_name 不为空
            self.log_signal.emit(f'saving chathistory to {file_path}')
            try:
                # 确保目录存在
                if dir_path and not os.path.exists(dir_path):
                    os.makedirs(dir_path, exist_ok=True)
                    
                with open(file_path, "w", encoding="utf-8") as file:
                    json.dump(chathistory, file, ensure_ascii=False, indent=4)
            except Exception as e:
                self.error_signal.emit(f'failed saving chathistory {chathistory}')
                QMessageBox.critical(None, "保存失败", f"保存聊天记录时发生错误：{e}")
        else:
            QMessageBox.warning(None, "取消保存", "未选择保存路径，聊天记录未保存。")

    # 自动保存
    def autosave_save_chathistory(self, chathistory):
        '''
        自动保存聊天记录到默认路径
        文件名称如果没有保存在info里，就用本地生成的标题
        仅在自动保存时，chat_id同时作为文件名和对话ID
        '''
        file_id = chathistory[0]['info']['chat_id']
        # file_title = chathistory[0]['info'].get('title', '')

        file_path = os.path.join(self.history_path, file_id)
        if file_path and len(chathistory) > 1:
            self.save_chathistory(chathistory, file_path=file_path)

    # 读取过去system prompt
    def load_sys_pmt_from_past_record(self, chathistory=[], file_path=None):
        """
        从当前或过去的聊天记录中加载系统提示
        Args:
            chathistory (list): 当前聊天记录
            file_path (str): 过去聊天记录的完整路径

        """
        if chathistory:
            return chathistory[0]["content"]
        elif file_path:
            past_chathistory = self.load_chathistory(file_path)
            if past_chathistory and isinstance(past_chathistory, list) and len(past_chathistory) > 0 and past_chathistory[0]["role"] == "system":
                return past_chathistory[0]["content"]
            else:
                self.error_signal.emit(f'failed loading chathistory from {file_path}')
                return ''
        else:
            self.error_signal.emit(f"didn't get any valid input to load sys pmt")
            return ''

    # 获取聊天记录清单
    def load_past_chats(self, application_path: str = '', file_count: int = 100) -> List[Dict[str, Any]]:
        """
        并行获取并验证历史聊天记录（优化版：减少 IO、避免重复计算）
        """
        # 路径准备
        if not application_path:
            application_path = self.history_path
        os.makedirs(application_path, exist_ok=True)

        def load_json_from_file(path: str):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

        # 读取/初始化元数据缓存（减少重复解析）
        cache_path = os.path.join(application_path, ".chat_index.json")
        try:
            with open(cache_path, "r", encoding="utf-8") as cf:
                meta_cache: Dict[str, Dict[str, Any]] = json.load(cf)
        except Exception:
            meta_cache = {}

        def select_latest_jsons(base: str, n: int) -> List[Tuple[str, str, float]]:
            """高效获取按修改时间降序的前 n 个 JSON 文件 (path, name, mtime)"""
            entries = []
            with os.scandir(base) as it:
                for e in it:
                    try:
                        if not e.is_file():
                            continue
                        name = e.name
                        # 跳过缓存与隐藏文件
                        if not name.endswith(".json") or name.startswith("."):
                            continue
                        st = e.stat()
                        entries.append((st.st_mtime, e.path, name))
                    except FileNotFoundError:
                        continue

            if len(entries) <= n:
                entries.sort(key=lambda t: t[0], reverse=True)
                return [(p, name, mtime) for mtime, p, name in entries]

            top = heapq.nlargest(n, entries, key=lambda t: t[0])
            top.sort(key=lambda t: t[0], reverse=True)  # 保持降序输出
            return [(p, name, mtime) for mtime, p, name in top]

        def extract_chat_title(chat_data: List[Dict[str, Any]]) -> str:
            """从聊天数据中提取标题"""
            for message in chat_data:
                if message.get("role") == "system":
                    info = message.get("info") or {}
                    title = info.get("title")
                    if title:
                        return title
            return "Untitled Chat"

        def validate_json_structure(data) -> bool:
            """验证JSON数据结构，支持工具调用格式"""
            if not isinstance(data, list):
                return False

            role_set = {"user", "system", "assistant", "tool"}

            for item in data:
                if not isinstance(item, dict):
                    return False

                role = item.get("role")
                if role not in role_set:
                    return False

                if role in ("user", "system"):
                    content = item.get("content")
                    if not isinstance(content, str):
                        return False

                elif role == "assistant":
                    has_content = "content" in item
                    has_tool_calls = "tool_calls" in item
                    if not (has_content or has_tool_calls):
                        return False
                    if has_content and not isinstance(item["content"], (str, type(None))):
                        return False
                    if has_tool_calls and not isinstance(item["tool_calls"], list):
                        return False

                else:  # role == "tool"
                    if "tool_call_id" not in item or "content" not in item:
                        return False
                    if not isinstance(item["content"], str):
                        return False

            return True

        def parse_one(path: str, name: str, mtime: float) -> Tuple[bool, str, str, float, str, str]:
            """返回: ok, name, path, mtime, err_msg, title"""
            try:
                data = load_json_from_file(path)
                if not validate_json_structure(data):
                    return False, name, path, mtime, "Invalid data structure", ""
                title = extract_chat_title(data)
                return True, name, path, mtime, "", title
            except json.JSONDecodeError:
                return False, name, path, mtime, "Invalid JSON format", ""
            except FileNotFoundError:
                return False, name, path, mtime, "File not found", ""
            except Exception as e:
                return False, name, path, mtime, str(e), ""

        # 1) 仅挑选最新 file_count 个
        selected = select_latest_jsons(application_path, file_count)

        # 2) 命中缓存的直接使用，未命中的再并发解析
        past_chats: List[Dict[str, Any]] = []
        to_parse: List[Tuple[str, str, float]] = []

        def cache_valid(rec: Dict[str, Any], m: float) -> bool:
            # mtime 精度可能不同，给一点容差
            return isinstance(rec, dict) and abs(rec.get("mtime", -1) - m) < 1e-6 and "title" in rec

        for path, name, mtime in selected:
            rec = meta_cache.get(name)
            if rec and cache_valid(rec, mtime):
                past_chats.append({
                    "file_path": path,
                    "title": rec["title"],
                    "modification_time": mtime,
                })
            else:
                to_parse.append((path, name, mtime))

        # 3) 并发解析未命中的文件（IO 为主，线程池足够；数量小就不用开太多线程）
        if to_parse:
            max_workers = min(32, max(1, len(to_parse)))
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(parse_one, p, n, m) for p, n, m in to_parse]

                for future in concurrent.futures.as_completed(futures):
                    ok, name, path, mtime, msg, title = future.result()
                    if ok:
                        past_chats.append({
                            "file_path": path,
                            "title": title,
                            "modification_time": mtime,
                        })
                        # 更新缓存
                        meta_cache[name] = {"mtime": mtime, "title": title}
                    else:
                        self.warning_signal.emit(f"Skipped {name}: {msg}")

        # 4) 写回缓存（失败不影响主流程）
        try:
            with open(cache_path, "w", encoding="utf-8") as cf:
                json.dump(meta_cache, cf, ensure_ascii=False)
        except Exception as e:
            self.warning_signal.emit(f"Failed to update cache: {e}")

        # 5) 最终按时间排序输出
        past_chats.sort(key=lambda x: x["modification_time"], reverse=True)
        return past_chats

    def is_equal(self, hist1: List[Dict[str, Any]], hist2: List[Dict[str, Any]]) -> bool:
        """比较两个聊天记录的内容是否是同一序列"""
        if len(hist1) != len(hist2):
            return False
        if hist1[0]['info']['chat_id'] == hist2[0]['info']['chat_id']:
            return True
        else:
            return False
