import concurrent.futures
import json
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import heapq

from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *

from service.chat_completion import APIRequestHandler
from core.session.session_model import ChatSession


class ChatHistoryTools:
    @staticmethod
    def locate_chat_index(chathistory, request_id):
        for i, msg in enumerate(chathistory):
            info = msg.get('info', {})
            if str(info.get('id')) == str(request_id):
                return i
        return None

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


class ChatHistoryVersionPatcher:
    """
    聊天历史版本补丁管理器。
    
    负责将旧版本的聊天历史数据结构迁移到最新版本。
    
    版本历史：
    - V0: 最初的无版本格式（0.25.1 之前）
    - V1: 通过 patch_history_0_25_1 升级后的格式（info 中包含 name, avatar, chat_id, title, tools）
    - V2: ChatSession 数据结构（将 name, avatar, chat_id, title, tools 从 history[0].info 提取到 ChatSession 顶层字段）
    """

    CURRENT_VERSION = 'V2'

    # 有序的版本列表，用于确定升级路径
    _VERSION_ORDER = ['V0', 'V1', 'V2']

    # 版本到升级函数的映射：key 为源版本，value 为 (目标版本, 升级函数)
    # 升级函数签名：(data: dict) -> dict
    # data 是整个 ChatSession 的序列化表示（对于 V0/V1，是以 history 为核心的结构）

    def __init__(self):
        self._patchers = {
            'V0': ('V1', self._patch_v0_to_v1),
            'V1': ('V2', self._patch_v1_to_v2),
        }

    def detect_version(self, data: Any) -> str:
        """
        检测数据的版本。
        
        Args:
            data: 可能是旧格式的 list（V0/V1 的 history）或新格式的 dict（V2 的 ChatSession）
            
        Returns:
            版本字符串: 'V0', 'V1', 'V2'
        """
        # V2: ChatSession 序列化后是 dict，且有 _version 字段
        if isinstance(data, dict):
            version = data.get('_version', None)
            if version and version in self._VERSION_ORDER:
                return version
            # 如果是 dict 但没有 _version，检查是否有 history 字段（可能是不完整的 V2）
            if 'history' in data and 'chat_id' in data:
                return 'V2'
            # 不认识的 dict 格式
            return 'V0'

        # V0 或 V1: 旧格式是一个 list
        if isinstance(data, list):
            if len(data) == 0:
                return 'V0'

            first_item = data[0]
            if not isinstance(first_item, dict):
                return 'V0'

            info = first_item.get('info')
            if info is None:
                return 'V0'

            # V1 的特征：第一条消息的 info 中包含 chat_id, title, tools 等字段
            if 'chat_id' in info and 'title' in info:
                return 'V1'

            return 'V0'

        return 'V0'

    def validate_history_version(self, data: Any) -> Tuple[bool, str, Optional[str]]:
        """
        验证历史数据的版本，并返回验证结果。
        
        Args:
            data: 待验证的数据
            
        Returns:
            Tuple of (is_current: bool, detected_version: str, message: Optional[str])
            - is_current: 是否已经是最新版本
            - detected_version: 检测到的版本
            - message: 如果不是最新版本，返回说明信息；否则为 None
        """
        detected = self.detect_version(data)
        if detected == self.CURRENT_VERSION:
            return True, detected, None
        else:
            return (
                False,
                detected,
                f"数据版本为 {detected}，需要升级到 {self.CURRENT_VERSION}"
            )

    def patch(
        self,
        data: Any,
        names: Optional[Dict[str, str]] = None,
        avatar: Optional[Dict[str, str]] = None,
        title: str = 'New Chat',
    ) -> dict:
        """
        将任意版本的聊天历史数据升级到最新版本 (V2 ChatSession dict)。
        
        Args:
            data: 旧格式的 list（V0/V1）或 dict（V2）
            names: 可选的 name 字典 {"user": ..., "assistant": ...}，用于 V0 升级
            avatar: 可选的 avatar 字典 {"user": ..., "assistant": ...}，用于 V0 升级
            title: 标题，用于 V0 升级时的默认标题
            
        Returns:
            符合 V2 (ChatSession) 结构的 dict
        """
        detected = self.detect_version(data)

        # 对于 V0 和 V1，先将 list 包装成统一的内部表示
        if detected in ('V0', 'V1'):
            # 内部用 dict 表示，携带额外的迁移参数
            data = {
                '_history_list': data,
                '_migration_params': {
                    'names': names,
                    'avatar': avatar,
                    'title': title,
                },
                '_version': detected,
            }
        elif detected == 'V2':
            # 已经是最新版本，直接返回
            if isinstance(data, dict):
                return data

        current = detected
        current_idx = self._VERSION_ORDER.index(current)
        target_idx = self._VERSION_ORDER.index(self.CURRENT_VERSION)

        while current_idx < target_idx:
            if current not in self._patchers:
                raise ValueError(
                    f"没有从 {current} 升级的补丁，无法继续迁移"
                )
            next_version, patcher_fn = self._patchers[current]
            data = patcher_fn(data)
            current = next_version
            current_idx = self._VERSION_ORDER.index(current)

        return data

    # ==================== 内部补丁方法 ====================

    @staticmethod
    def _patch_v0_to_v1(data: dict) -> dict:
        """
        将 V0 格式升级到 V1 格式。
        
        V0 -> V1 的变更：
        - 确保每条消息都有 info 字段
        - 第一条消息的 info 中添加 name, avatar, chat_id, title, tools
        - system/developer 角色的 id 设为 'system_prompt'
        
        等价于旧的 patch_history_0_25_1。
        """
        history_list = data.get('_history_list', [])
        params = data.get('_migration_params', {})
        names = params.get('names')
        avatar = params.get('avatar')
        title = params.get('title', 'New Chat')

        if not history_list:
            # 空列表，创建默认的 system 消息
            history_list = [
                {
                    "role": "system",
                    "content": "",
                    "info": {
                        "id": "system_prompt",
                        "name": names or {"user": "", "assistant": ""},
                        "avatar": avatar or {"user": "", "assistant": ""},
                        "chat_id": str(uuid.uuid4()),
                        "title": title,
                        "tools": [],
                    }
                }
            ]
        else:
            request_id = 100001
            for i, item in enumerate(history_list):
                info = item.get('info')
                if info is None:
                    info = {'id': f'patch_{request_id}'}
                    item['info'] = info
                    request_id += 1

                if i == 0:
                    if names and 'name' not in info:
                        info['name'] = names
                    if avatar and 'avatar' not in info:
                        info['avatar'] = avatar
                    role = item.get('role')
                    if role in ('system', 'developer'):
                        info['id'] = 'system_prompt'
                    if 'chat_id' not in info:
                        info['chat_id'] = str(uuid.uuid4())
                    if 'title' not in info:
                        info['title'] = title
                    if 'tools' not in info:
                        info['tools'] = []

        return {
            '_history_list': history_list,
            '_migration_params': params,
            '_version': 'V1',
        }

    @staticmethod
    def _patch_v1_to_v2(data: dict) -> dict:
        """
        将 V1 格式升级到 V2 (ChatSession dict) 格式。
        
        V1 -> V2 的变更：
        - 将 history[0].info 中的 name, avatar, chat_id, title, tools 提取到顶层
        - 清理 history 中每条消息的 info，只保留 id, time, model 等消息级别的元数据
        - 添加 _version = 'V2'
        """
        history_list = data.get('_history_list', [])
        params = data.get('_migration_params', {})

        # 从第一条消息的 info 中提取会话级别的元数据
        chat_id = str(uuid.uuid4())
        title = params.get('title', 'New Chat')
        name = {"user": "", "assistant": ""}
        avatar_data = {"user": "", "assistant": ""}
        tools = []

        if history_list:
            first_info = history_list[0].get('info', {})
            chat_id = first_info.pop('chat_id', chat_id)
            title = first_info.pop('title', title)
            name = first_info.pop('name', name)
            avatar_data = first_info.pop('avatar', avatar_data)
            tools = first_info.pop('tools', tools)

        # 清理每条消息的 info，只保留消息级别的字段
        cleaned_history = []
        for item in history_list:
            msg = {
                'role': item['role'],
                'content': item.get('content', ''),
            }

            old_info = item.get('info', {})
            new_info: Dict[str, Any] = {}

            # 保留消息级别的元数据
            if 'id' in old_info:
                new_info['id'] = old_info['id']
            if 'time' in old_info:
                new_info['time'] = old_info['time']
            if 'model' in old_info:
                new_info['model'] = old_info['model']

            # 保留 usage 相关的字段
            for key in ('completion_tokens', 'prompt_tokens', 'total_tokens'):
                if key in old_info:
                    new_info[key] = old_info[key]

            msg['info'] = new_info

            # 对于 assistant 消息，保留 reasoning_content
            if item['role'] == 'assistant':
                if 'reasoning_content' in item:
                    msg['reasoning_content'] = item['reasoning_content']

            cleaned_history.append(msg)

        # 确保 name 和 avatar 是正确格式
        if isinstance(name, dict):
            name = {
                "user": name.get("user", ""),
                "assistant": name.get("assistant", ""),
            }
        else:
            name = {"user": "", "assistant": ""}

        if isinstance(avatar_data, dict):
            avatar_data = {
                "user": avatar_data.get("user", ""),
                "assistant": avatar_data.get("assistant", ""),
            }
        else:
            avatar_data = {"user": "", "assistant": ""}

        return {
            'history': cleaned_history,
            'chat_id': chat_id,
            'new_chat_rounds': 0,
            'new_background_rounds': 0,
            'title': title,
            'name': name,
            'avatar': avatar_data,
            'tools': tools,
            '_version': 'V2',
        }

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

class ChathistoryFileManager:
    '''
    聊天历史文件管理器
    该类负责管理聊天历史记录的文件操作，包括加载、保存、删除聊天记录，
    以及批量加载历史聊天记录。支持多个版本的聊天记录格式（V0/V1/V2）。
    Attributes:
        history_path (str): 聊天历史文件的存储路径，默认为 'data/history'
        patcher (ChatHistoryVersionPatcher): 聊天历史版本补丁器，用于处理不同版本的格式转换
    Methods:
        load_chathistory: 从指定文件路径加载单个聊天历史记录
        save_chathistory: 保存聊天会话到指定的文件夹或文件路径
        delete_chathistory: 安全地删除指定的聊天历史文件
        load_past_chats: 并行加载并验证指定数量的历史聊天记录，支持缓存机制
    '''

    def __init__(self, history_path='data/history'):
        self.history_path = history_path
        self.patcher= ChatHistoryVersionPatcher()

    # 载入记录
    def load_chathistory(self, file_path) -> ChatSession:
        chathistory = {}
        if not(file_path and os.path.exists(file_path)):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        with open(file_path, "r", encoding="utf-8") as file:
            chathistory = json.load(file)
        if not chathistory:
            raise ValueError(f"文件为空: {file_path}")

        return ChatSession.from_dict(self.patcher.patch(chathistory))

    # 保存聊天记录
    def save_chathistory(self, chat_session:ChatSession,folder_path='', file_path='') -> str:

        chathistory = chat_session.to_json()

        if not folder_path and not file_path:
            raise ValueError("必须指定文件夹或文件路径")

        # 指定文件名时不走从聊天记录自动生成文件名的逻辑
        if file_path:
            # 分离路径和文件名，只清洗文件名部分
            dir_path = os.path.dirname(file_path)
            file_name = os.path.basename(file_path)
        
        # 指定文件夹，需要自动生成文件名
        elif folder_path:
            dir_path = folder_path
            file_name = chat_session.chat_id+".json"

        
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

        if not(file_path and file_name):  # 检查 file_path 是否有效, file_name 不为空
            raise ValueError("Internal Error : empty file_path | empty file_path")
        # 确保目录存在
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(chathistory) 

        return file_path

    def delete_chathistory(self, file_path: str):
        # 1. 基础参数检查
        if not file_path:
            raise ValueError("File path is empty")

        # 2. 路径解析 (处理符号链接等)
        normalized_path = os.path.realpath(os.path.abspath(file_path))

        # 3. 安全守卫：必须存在，必须是文件，必须是 json
        # (这部分不能省，这是防止误删的关键)
        if not os.path.exists(normalized_path):
            raise FileNotFoundError(f"File not found: {normalized_path}")

        if not os.path.isfile(normalized_path):
            raise IsADirectoryError(f"Target is not a file: {normalized_path}")

        if Path(normalized_path).suffix.lower() != '.json':
            raise ValueError(f"Security restrict: Cannot delete non-json file: {normalized_path}")

        # 4. 直接执行，出错让它自己爆
        # 如果文件被占用，os.remove 会自动抛出 OSError (PermissionError)，上层捕获即可
        os.remove(normalized_path)

    def load_past_chats(self, history_path: str = '', file_count: int = 100) -> List[Dict[str, Any]]:
        """
        并行获取并验证历史聊天记录（支持 V0/V1/V2 混存格式）
        """
        # 路径准备
        if not history_path:
            history_path = self.history_path
        os.makedirs(history_path, exist_ok=True)

        def load_json_from_file(path: str):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

        # 读取/初始化元数据缓存
        cache_path = os.path.join(history_path, ".chat_index.json")
        try:
            with open(cache_path, "r", encoding="utf-8") as cf:
                meta_cache: Dict[str, Dict[str, Any]] = json.load(cf)
        except Exception:
            meta_cache = {}

        # ------------------------------------------------------------------ #
        #  文件筛选
        # ------------------------------------------------------------------ #
        def select_latest_jsons(base: str, n: int) -> List[Tuple[str, str, float]]:
            """高效获取按修改时间降序的前 n 个 JSON 文件 (path, name, mtime)"""
            entries = []
            with os.scandir(base) as it:
                for e in it:
                    try:
                        if not e.is_file():
                            continue
                        name = e.name
                        if not name.endswith(".json") or name.startswith("."):
                            continue
                        st = e.stat()
                        entries.append((st.st_mtime, e.path, name))
                    except FileNotFoundError:
                        continue

            if len(entries) <= n:
                entries.sort(key=lambda t: t[0], reverse=True)
                return [(p, nm, mt) for mt, p, nm in entries]

            top = heapq.nlargest(n, entries, key=lambda t: t[0])
            top.sort(key=lambda t: t[0], reverse=True)
            return [(p, nm, mt) for mt, p, nm in top]

        # ------------------------------------------------------------------ #
        #  消息级校验（兼容 OpenAI Chat Completion API 全部 role）
        # ------------------------------------------------------------------ #
        _VALID_ROLES = frozenset(("system", "user", "assistant", "tool"))

        def validate_message(item: dict) -> bool:
            if not isinstance(item, dict):
                return False

            role = item.get("role")
            if role not in _VALID_ROLES:
                return False

            if role in ("system", "user"):
                # V2 user content 可以是 str 或 list（多模态）
                content = item.get("content")
                if not isinstance(content, (str, list)):
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

            else:  # tool
                if "tool_call_id" not in item or "content" not in item:
                    return False
                if not isinstance(item["content"], (str, list)):
                    return False

            return True

        # ------------------------------------------------------------------ #
        #  文件级校验（自动区分 V0/V1 list 与 V2 dict）
        # ------------------------------------------------------------------ #
        def validate_json_structure(data) -> bool:
            if isinstance(data, list):
                # V0 / V1：顶层直接是消息列表
                return all(validate_message(m) for m in data)

            if isinstance(data, dict):
                # V2：ChatSession dict，history 是消息列表
                history = data.get("history")
                if not isinstance(history, list):
                    return False
                return all(validate_message(m) for m in history)

            return False

        # ------------------------------------------------------------------ #
        #  标题提取（按版本走不同路径，不做完整 patch）
        # ------------------------------------------------------------------ #
        def extract_title(data, version: str) -> str:
            if version == "V2":
                # V2 title 是 ChatSession 顶层字段
                return data.get("title") or "Untitled Chat"

            # V0 / V1：title 存放在 system message 的 info 里
            if isinstance(data, list):
                for msg in data:
                    if msg.get("role") == "system":
                        info = msg.get("info")
                        if isinstance(info, dict):
                            title = info.get("title")
                            if title:
                                return title
            return "Untitled Chat"

        # ------------------------------------------------------------------ #
        #  单文件解析
        # ------------------------------------------------------------------ #
        def parse_one(
            path: str, name: str, mtime: float
        ) -> Tuple[bool, str, str, float, str, str, str]:
            """返回: (ok, name, path, mtime, err_msg, title, version)"""
            try:
                data = load_json_from_file(path)

                if not validate_json_structure(data):
                    return False, name, path, mtime, "Invalid data structure", "", ""

                version = self.patcher.detect_version(data)
                title = extract_title(data, version)
                return True, name, path, mtime, "", title, version

            except json.JSONDecodeError:
                return False, name, path, mtime, "Invalid JSON format", "", ""
            except FileNotFoundError:
                return False, name, path, mtime, "File not found", "", ""
            except Exception as e:
                return False, name, path, mtime, str(e), "", ""

        # ================================================================== #
        #  主流程
        # ================================================================== #

        # 1) 挑选最新的 file_count 个文件
        selected = select_latest_jsons(history_path, file_count)

        # 2) 缓存命中 → 直接使用；未命中 → 加入待解析列表
        past_chats: List[Dict[str, Any]] = []
        to_parse: List[Tuple[str, str, float]] = []

        def cache_valid(rec: Dict[str, Any], m: float) -> bool:
            return (
                isinstance(rec, dict)
                and abs(rec.get("mtime", -1) - m) < 1e-6
                and "title" in rec
            )

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

        # 3) 并发解析未命中的文件
        if to_parse:
            max_workers = min(32, max(1, len(to_parse)))
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(parse_one, p, n, m)
                    for p, n, m in to_parse
                ]

                for future in concurrent.futures.as_completed(futures):
                    ok, name, path, mtime, msg, title, version = future.result()
                    if ok:
                        past_chats.append({
                            "file_path": path,
                            "title": title,
                            "modification_time": mtime,
                        })
                        # 写入缓存（附带 version 字段）
                        meta_cache[name] = {
                            "mtime": mtime,
                            "title": title,
                            "version": version,
                        }
                    else:
                        print(f"Failed to parse {name}: {msg}")

        # 4) 写回缓存（失败不影响主流程）
        try:
            with open(cache_path, "w", encoding="utf-8") as cf:
                json.dump(meta_cache, cf, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to update cache: {e}")

        # 5) 按修改时间降序输出
        past_chats.sort(key=lambda x: x["modification_time"], reverse=True)
        return past_chats
    

