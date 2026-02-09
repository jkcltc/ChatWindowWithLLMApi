import concurrent.futures
import json
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import heapq


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
    

