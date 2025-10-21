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

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from utils.tools.one_shot_api_request import APIRequestHandler

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
        return chathistory
    
    @staticmethod
    def clean_history(chathistory,unnecessary_items=['info']):
        exclude = set(unnecessary_items)
        return [
            {key: value for key, value in item.items() if key not in exclude}
            for item in chathistory
        ]
    
    @staticmethod
    def to_readable_str(chathistory,
                        names={}
                        ):
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
            lines.append(f"{message['content']}")
        return '\n'.join(lines)

class ChatHistoryTextView(QWidget):
    """A dialog window for displaying full chat history with right-aligned controls."""
    
    def __init__(self, chat_history, user_name, ai_name):
        super().__init__()
        self.chat_history = chat_history
        self.user_name = user_name
        self.ai_name = ai_name

        if chat_history and isinstance(chat_history[0], dict):
            first_msg = chat_history[0]
            info = first_msg.get('info', {})
            name_data = info.get('name', {}) if isinstance(info, dict) else {}
            
            if isinstance(name_data, dict):
                if name_data.get('user'):
                    self.user_name = name_data['user']
                if name_data.get('assistant'):
                    self.ai_name = name_data['assistant']
        
        self.setWindowTitle("聊天历史-文本")
        self.setMinimumSize(1280, 720)  # 增加最小宽度以适应右侧面板
        
        # 显示选项默认值
        self.show_reasoning = False
        self.show_tools = True
        self.show_metadata = False
        self.use_markdown = True
        
        self._init_ui()
        self._load_chat_history()
    
    def _init_ui(self):
        """初始化UI组件，控制面板在右侧"""
        main_layout = QHBoxLayout()  # 使用水平布局
        
        # 创建文本浏览区域（左侧）
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        main_layout.addWidget(self.text_browser, 3)  # 文本区域占3/4宽度
        
        # 创建右侧面板布局
        controls_layout = QVBoxLayout()
        controls_layout.setAlignment(Qt.AlignTop)
        
        # 添加"显示选项"分组框（右侧）
        options_group = QGroupBox("显示选项")
        options_layout = QVBoxLayout()
        
        # 添加思考链选项
        reasoning_group = QGroupBox("思考链")
        reasoning_layout = QVBoxLayout()
        self.reasoning_cb = QCheckBox("显示思考链")
        self.reasoning_cb.stateChanged.connect(self._toggle_reasoning)
        reasoning_layout.addWidget(self.reasoning_cb)
        reasoning_group.setLayout(reasoning_layout)
        options_layout.addWidget(reasoning_group)
        
        # 添加工具调用选项
        tools_group = QGroupBox("工具调用")
        tools_layout = QVBoxLayout()
        self.tools_cb = QCheckBox("显示工具调用")
        self.tools_cb.setChecked(True)
        self.tools_cb.stateChanged.connect(self._toggle_tools)
        tools_layout.addWidget(self.tools_cb)
        tools_group.setLayout(tools_layout)
        options_layout.addWidget(tools_group)
        
        # 添加元数据显示选项
        metadata_group = QGroupBox("元数据")
        metadata_layout = QVBoxLayout()
        self.metadata_cb = QCheckBox("显示消息元数据")
        self.metadata_cb.stateChanged.connect(self._toggle_metadata)
        metadata_layout.addWidget(self.metadata_cb)
        metadata_group.setLayout(metadata_layout)
        options_layout.addWidget(metadata_group)
        
        # 添加格式选项（右下角）
        format_group = QGroupBox("显示格式")
        format_layout = QVBoxLayout()
        
        self.markdown_rb = QRadioButton("Markdown格式")
        self.markdown_rb.setChecked(True)
        self.markdown_rb.toggled.connect(self._toggle_format)
        
        self.plaintext_rb = QRadioButton("纯文本格式")
        self.plaintext_rb.toggled.connect(self._toggle_format)
        
        format_layout.addWidget(self.markdown_rb)
        format_layout.addWidget(self.plaintext_rb)
        format_group.setLayout(format_layout)
        options_layout.addWidget(format_group)
        
        # 添加重载按钮
        reload_btn = QPushButton("刷新视图")
        reload_btn.clicked.connect(self._load_chat_history)
        options_layout.addWidget(reload_btn)
        
        # 添加间距
        options_layout.addSpacing(20)

        options_group.setLayout(options_layout)
        controls_layout.addWidget(options_group)
        
        # 创建右侧容器
        controls_container = QWidget()
        controls_container.setLayout(controls_layout)
        
        main_layout.addWidget(controls_container, 1)  # 右侧面板占1/4宽度
        
        self.setLayout(main_layout)
    
    def _toggle_reasoning(self, state):
        self.show_reasoning = (state == Qt.Checked)
        self._load_chat_history()
    
    def _toggle_tools(self, state):
        self.show_tools = (state == Qt.Checked)
        self._load_chat_history()
    
    def _toggle_metadata(self, state):
        self.show_metadata = (state == Qt.Checked)
        self._load_chat_history()
    
    def _toggle_format(self):
        self.use_markdown = self.markdown_rb.isChecked()
        self._load_chat_history()
    
    def _load_chat_history(self):
        """根据选项加载和格式化聊天历史"""
        buffer = []
        
        for index, msg in enumerate(self.chat_history):
            # 获取发送者名称
            role = msg.get('role', '')
            name = self._get_sender_name(role)
            
            # 过滤工具调用消息（如果不显示）
            if role == 'tool' and not self.show_tools:
                continue
                
            # 添加消息头部标识
            if self.use_markdown:
                buffer.append(f"\n\n**{name}**")
            else:
                buffer.append(f"\n\n{name}")
            
            # 添加思考链（如果存在且需要显示）
            if self.show_reasoning and 'reasoning_content' in msg:
                reasoning_content = msg['reasoning_content'].replace('### AI 思考链\n---', '').strip()
                if reasoning_content:
                    if self.use_markdown:
                        buffer.append(f"\n```  \n Think: {reasoning_content}  \n  ```  \n---  \n  ")
                    else:
                        buffer.append(f"\n```  \n Think: {reasoning_content}  \n  ```  \n---  \n  ")
            
            # 添加消息内容
            content = msg.get('content', '')
            if content:
                buffer.append(f"\n\n{content}")
            
            # 添加元数据（如果存在且需要显示）
            if self.show_metadata and 'info' in msg:
                info = msg['info']
                if info:
                    if self.use_markdown:
                        buffer.append("\n\n<small>")
                        buffer.append("\n \n ")
                        if msg['role'] == 'system':
                            buffer.append("系统提示设置")
                        else:
                            parts = []
                            if info.get('model'):
                                parts.append(f"模型: {info['model']}")
                            if info.get('time'):
                                parts.append(f"时间: {info['time']}")
                            if info.get('id'):
                                parts.append(f"ID: {info['id']}")
                            buffer.append(" | ".join(parts))
                        buffer.append("</small>")
                    else:
                        buffer.append("\n[元数据]")
                        if msg['role'] == 'system':
                            buffer.append("系统提示设置")
                        else:
                            if info.get('model'):
                                buffer.append(f"  模型: {info['model']}")
                            if info.get('time'):
                                buffer.append(f"  时间: {info['time']}")
                            if info.get('id'):
                                buffer.append(f"  消息ID: {info['id']}")
            
            # 添加消息分隔线（不是最后一条消息）
            if index < len(self.chat_history) - 1:
                buffer.append("\n" + ("---" if self.use_markdown else "─"*10))
        
        # 根据格式设置文本
        full_text = '\n'.join(buffer).strip()
        if self.use_markdown:
            self.text_browser.setMarkdown(full_text)
        else:
            self.text_browser.setPlainText(full_text)
    
    def _get_sender_name(self, role):
        if role == 'system':
            return '系统提示'
        elif role == 'user':
            return self.user_name
        elif role == 'assistant':
            return self.ai_name
        elif role == 'tool':
            return f"{self.ai_name} called tool"
        return role

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
        # 先断开旧的连接（若存在）
        if self.api_handler:
            try:
                if hasattr(self.api_handler, "request_completed"):
                    self.api_handler.request_completed.disconnect(self._handle_title_response)
            except Exception:
                pass
            try:
                if hasattr(self.api_handler, "error_occurred"):
                    self.api_handler.error_occurred.disconnect(self._on_api_error)
            except Exception:
                pass

        self.api_handler = api_handler

        # 安全连接
        if self.api_handler:
            if hasattr(self.api_handler, "request_completed"):
                try:
                    self.api_handler.request_completed.connect(self._handle_title_response)
                except Exception as e:
                    self.warning_signal.emit(f"无法连接 API 的 request_completed 信号：{e}")
            else:
                self.warning_signal.emit("API handler 不包含 request_completed 信号，无法异步获取结果。")

            if hasattr(self.api_handler, "error_occurred"):
                try:
                    self.api_handler.error_occurred.connect(self._on_api_error)
                except Exception as e:
                    self.warning_signal.emit(f"无法连接 API 的 error_occurred 信号：{e}")
            else:
                self.warning_signal.emit("API handler 不包含 error_occurred 信号，无法感知错误。")

            self.log_signal.emit("已绑定 API 处理器。")

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
        unsupported = r'[\n<>:"/\\|?*{}```math```,，。.!！:：;；\'" ]'
        text = re.sub(unsupported, "", text)
        text = text.strip()
        if not text:
            text = "New Chat"
        if len(text) > max_length:
            text = text[:max_length]
        return text

class ChatHistoryEditor(QWidget):
    # 定义编辑完成的信号，传递新的聊天历史
    editCompleted = pyqtSignal(list)

    def __init__(self, title_generator: TitleGenerator, chathistory: List[Dict[str, Any]], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("聊天历史编辑器")
        self._title_generator: TitleGenerator = title_generator
        self._original_history: List[Dict[str, Any]] = copy.deepcopy(chathistory or [])
        self._history: List[Dict[str, Any]] = copy.deepcopy(chathistory or [])
        self._syncing: bool = False
        self._current_task_id: Optional[str] = None
        self._gen_running: bool = False

        self._build_ui()
        self._connect_signals()
        self._get_or_create_system_item()  # 确保结构完整
        self._load_history_to_form()
        self._update_json_editor_from_history()

    # ---------- UI ----------
    def _build_ui(self) -> None:
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        
        width = int(screen_geometry.width() * 0.6)
        height = int(screen_geometry.height() * 0.6)
        
        left = (screen_geometry.width() - width) // 2
        top = (screen_geometry.height() - height) // 2
        
        self.setGeometry(left, top, width, height)

        main_layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget(self)

        # 表单编辑页
        form_page = QWidget(self)
        form_layout = QVBoxLayout(form_page)

        sys_group = QGroupBox("系统提示（system.content）", self)
        sys_layout = QVBoxLayout(sys_group)
        self.sys_content_edit = QTextEdit(self)
        self.sys_content_edit.setPlaceholderText("例如：你是{{char}}。你正在和{{user}}聊天。")
        sys_layout.addWidget(self.sys_content_edit)
        form_layout.addWidget(sys_group)

        name_group = QGroupBox("角色名称（info.name）", self)
        name_form = QFormLayout(name_group)
        self.user_name_edit = QLineEdit(self)
        self.assistant_name_edit = QLineEdit(self)
        name_form.addRow("User 名称：", self.user_name_edit)
        name_form.addRow("Assistant 名称：", self.assistant_name_edit)
        form_layout.addWidget(name_group)

        avatar_group = QGroupBox("头像路径（info.avatar）", self)
        avatar_form = QFormLayout(avatar_group)
        # user avatar
        self.user_avatar_edit = QLineEdit(self)
        self.user_avatar_btn = QPushButton("选择...", self)
        urow = QHBoxLayout()
        urow.addWidget(self.user_avatar_edit, 1)
        urow.addWidget(self.user_avatar_btn)
        # assistant avatar
        self.assistant_avatar_edit = QLineEdit(self)
        self.assistant_avatar_btn = QPushButton("选择...", self)
        arow = QHBoxLayout()
        arow.addWidget(self.assistant_avatar_edit, 1)
        arow.addWidget(self.assistant_avatar_btn)
        # add rows
        avatar_form.addRow("User 头像路径：", self._wrap_row(urow))
        avatar_form.addRow("Assistant 头像路径：", self._wrap_row(arow))
        form_layout.addWidget(avatar_group)

        # 标题编辑与生成
        title_group = QGroupBox("会话标题（info.title）", self)
        title_layout = QVBoxLayout(title_group)
        title_row = QHBoxLayout()
        self.title_edit = QLineEdit(self)
        self.title_edit.setPlaceholderText("会话标题...")
        self.btn_gen_title_api = QPushButton("AI生成(调用API)", self)
        self.btn_gen_title_local = QPushButton("本地生成", self)
        title_row.addWidget(self.title_edit, 1)
        title_row.addWidget(self.btn_gen_title_api)
        title_row.addWidget(self.btn_gen_title_local)
        title_layout.addLayout(title_row)

        opt_row = QHBoxLayout()
        self.include_system_chk = QCheckBox("包含系统提示参与生成", self)
        self.maxlen_spin = QSpinBox(self)
        self.maxlen_spin.setRange(4, 100)
        self.maxlen_spin.setValue(20)
        opt_row.addWidget(self.include_system_chk)
        opt_row.addWidget(QLabel("最大长度：", self))
        opt_row.addWidget(self.maxlen_spin)
        opt_row.addStretch(1)
        title_layout.addLayout(opt_row)

        # 日志
        self.log_view = QPlainTextEdit(self)
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("生成日志输出...")
        self.log_view.setMaximumHeight(120)
        title_layout.addWidget(self.log_view)

        form_layout.addWidget(title_group)

        # 操作
        action_row = QHBoxLayout()
        self.btn_save = QPushButton("保存并关闭", self)
        self.btn_reset = QPushButton("放弃修改并恢复", self)
        action_row.addStretch(1)
        action_row.addWidget(self.btn_reset)
        action_row.addWidget(self.btn_save)
        form_layout.addLayout(action_row)

        self.tabs.addTab(form_page, "表单编辑")

        # JSON 编辑页
        json_page = QWidget(self)
        json_layout = QVBoxLayout(json_page)
        self.json_edit = QPlainTextEdit(self)
        self.json_edit.setPlaceholderText("在此直接编辑 chathistory 的 JSON ...")
        json_layout.addWidget(self.json_edit)

        json_btn_row = QHBoxLayout()
        self.btn_json_apply_to_form = QPushButton("载入JSON到表单", self)
        self.btn_json_format = QPushButton("整理格式", self)
        self.btn_json_refresh_from_form = QPushButton("从表单刷新更改", self)
        json_btn_row.addWidget(self.btn_json_apply_to_form)
        json_btn_row.addWidget(self.btn_json_format)
        json_btn_row.addWidget(self.btn_json_refresh_from_form)
        json_btn_row.addStretch(1)
        json_layout.addLayout(json_btn_row)

        status_row = QHBoxLayout()
        self.json_status_label = QLabel("就绪", self)
        self.json_status_label.setStyleSheet("color: #888;")
        status_row.addWidget(self.json_status_label)
        status_row.addStretch(1)
        json_layout.addLayout(status_row)

        self.tabs.addTab(json_page, "JSON编辑")
        main_layout.addWidget(self.tabs)

    def _wrap_row(self, layout: QHBoxLayout) -> QWidget:
        w = QWidget(self)
        w.setLayout(layout)
        return w

    # ---------- 信号连接 ----------
    def _connect_signals(self) -> None:
        # 表单 -> 数据
        self.sys_content_edit.textChanged.connect(self._on_sys_content_changed)
        self.user_name_edit.textChanged.connect(self._on_user_name_changed)
        self.assistant_name_edit.textChanged.connect(self._on_assistant_name_changed)
        self.user_avatar_edit.textChanged.connect(self._on_user_avatar_changed)
        self.assistant_avatar_edit.textChanged.connect(self._on_assistant_avatar_changed)
        self.title_edit.textChanged.connect(self._on_title_changed)
        self.user_avatar_btn.clicked.connect(lambda: self._pick_avatar(self.user_avatar_edit))
        self.assistant_avatar_btn.clicked.connect(lambda: self._pick_avatar(self.assistant_avatar_edit))

        # 标题生成
        self.btn_gen_title_api.clicked.connect(self._on_generate_title_api)
        self.btn_gen_title_local.clicked.connect(self._on_generate_title_local)

        # 操作
        self.btn_save.clicked.connect(self._on_save_clicked)
        self.btn_reset.clicked.connect(self._on_reset_clicked)

        # JSON 编辑
        self.btn_json_apply_to_form.clicked.connect(self._on_json_apply_to_form)
        self.btn_json_format.clicked.connect(self._on_json_format)
        self.btn_json_refresh_from_form.clicked.connect(self._update_json_editor_from_history)
        self.json_edit.textChanged.connect(self._on_json_text_changed)

        # TitleGenerator 日志/结果
        # 注意：title_generated 的参数顺序为 (task_id, title)
        self._title_generator.title_generated.connect(self._on_title_generated)
        self._title_generator.log_signal.connect(self._on_log_signal)
        self._title_generator.warning_signal.connect(lambda s: self._append_log(s, "warn"))
        self._title_generator.error_signal.connect(self._on_error_signal)

    # ---------- 数据与UI同步 ----------
    def _get_or_create_system_item(self) -> Tuple[int, Dict[str, Any]]:
        idx = -1
        sys_item = None
        for i, item in enumerate(self._history):
            if isinstance(item, dict) and item.get("role") == "system":
                idx = i
                sys_item = item
                break
        if sys_item is None:
            sys_item = {
                "role": "system",
                "content": "你是{{char}}。你正在和{{user}}聊天。",
                "info": {
                    "id": "system_prompt",
                    "name": {"user": "", "assistant": ""},
                    "avatar": {"user": "", "assistant": ""},
                    "chat_id": str(uuid.uuid4()),
                    "title": ""
                }
            }
            idx = 0
            self._history.insert(0, sys_item)

        info = sys_item.setdefault("info", {})
        info.setdefault("name", {}).setdefault("user", "")
        info.setdefault("name", {}).setdefault("assistant", "")
        info.setdefault("avatar", {}).setdefault("user", "")
        info.setdefault("avatar", {}).setdefault("assistant", "")
        info.setdefault("title", info.get("title", ""))
        return idx, sys_item

    def _load_history_to_form(self) -> None:
        self._syncing = True
        _, sys_item = self._get_or_create_system_item()
        info = sys_item.get("info", {})
        name = info.get("name", {})
        avatar = info.get("avatar", {})

        self.sys_content_edit.setPlainText(sys_item.get("content", "") or "")
        self.user_name_edit.setText(name.get("user", "") or "")
        self.assistant_name_edit.setText(name.get("assistant", "") or "")
        self.user_avatar_edit.setText(avatar.get("user", "") or "")
        self.assistant_avatar_edit.setText(avatar.get("assistant", "") or "")
        self.title_edit.setText(info.get("title", "") or "")
        self._syncing = False

    def _update_json_editor_from_history(self) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            text = json.dumps(self._history, ensure_ascii=False, indent=2)
            self.json_edit.setPlainText(text)
            self.json_status_label.setText("JSON 已更新")
            self.json_status_label.setStyleSheet("color: #888;")
        finally:
            self._syncing = False

    def _apply_form_to_history(self) -> None:
        self._update_json_editor_from_history()

    # ---------- 表单事件 ----------
    def _on_sys_content_changed(self) -> None:
        if self._syncing:
            return
        _, sys_item = self._get_or_create_system_item()
        sys_item["content"] = self.sys_content_edit.toPlainText()
        self._update_json_editor_from_history()

    def _on_user_name_changed(self, text: str) -> None:
        if self._syncing:
            return
        _, sys_item = self._get_or_create_system_item()
        sys_item["info"]["name"]["user"] = text
        self._update_json_editor_from_history()

    def _on_assistant_name_changed(self, text: str) -> None:
        if self._syncing:
            return
        _, sys_item = self._get_or_create_system_item()
        sys_item["info"]["name"]["assistant"] = text
        self._update_json_editor_from_history()

    def _on_user_avatar_changed(self, text: str) -> None:
        if self._syncing:
            return
        _, sys_item = self._get_or_create_system_item()
        sys_item["info"]["avatar"]["user"] = text
        self._update_json_editor_from_history()

    def _on_assistant_avatar_changed(self, text: str) -> None:
        if self._syncing:
            return
        _, sys_item = self._get_or_create_system_item()
        sys_item["info"]["avatar"]["assistant"] = text
        self._update_json_editor_from_history()

    def _on_title_changed(self, text: str) -> None:
        if self._syncing:
            return
        _, sys_item = self._get_or_create_system_item()
        sys_item["info"]["title"] = text
        self._update_json_editor_from_history()

    def _pick_avatar(self, target_edit: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择头像图片", "", "图像文件 (*.png *.jpg *.jpeg *.bmp *.gif);;所有文件 (*.*)")
        if path:
            target_edit.setText(path)

    # ---------- 标题生成 ----------
    def _on_generate_title_api(self) -> None:
        self._set_generating(True)
        self._current_task_id = str(uuid.uuid4())
        self._title_generator.create_chat_title(
            chathistory=copy.deepcopy(self._history),
            task_id=self._current_task_id,
            use_local=False,
            max_length=int(self.maxlen_spin.value()),
            include_system_prompt=self.include_system_chk.isChecked()
        )

    def _on_generate_title_local(self) -> None:
        title = self._title_generator.generate_title_from_history_local(
            chathistory=copy.deepcopy(self._history),
            max_length=int(self.maxlen_spin.value())
        )
        if not isinstance(title, str) or not title.strip():
            self._append_log("[本地] 生成标题失败：未找到合适的消息。", "warn")
            return
        self._append_log(f"[本地] 生成标题：{title}", "log")
        self._syncing = True
        self.title_edit.setText(title)
        self._syncing = False
        self._on_title_changed(title)

    def _on_title_generated(self, task_id: str, title: str) -> None:
        # 注意参数顺序：(task_id, title)
        if self._current_task_id and task_id != self._current_task_id:
            return
        text = (title or "").strip()
        self._syncing = True
        self.title_edit.setText(text)
        self._syncing = False
        self._on_title_changed(text)
        self._set_generating(False)
        self._current_task_id = None

    def _set_generating(self, generating: bool) -> None:
        self._gen_running = generating
        self.btn_gen_title_api.setEnabled(not generating)
        self.btn_gen_title_local.setEnabled(not generating)
        self._append_log("正在生成标题..." if generating else "标题生成完成。", "log")

    # ---------- JSON 编辑 ----------
    def _on_json_apply_to_form(self) -> None:
        text = self.json_edit.toPlainText().strip()
        if not text:
            self.json_status_label.setText("JSON 为空")
            self.json_status_label.setStyleSheet("color: #d9534f;")
            return
        try:
            data = json.loads(text)
            if not isinstance(data, list):
                raise ValueError("JSON 根应为列表(list)。")
            self._history = data
            self._get_or_create_system_item()
            self._load_history_to_form()
            self.json_status_label.setText("JSON 已应用到表单")
            self.json_status_label.setStyleSheet("color: #5cb85c;")
        except Exception as e:
            self.json_status_label.setText(f"JSON 解析失败：{e}")
            self.json_status_label.setStyleSheet("color: #d9534f;")

    def _on_json_format(self) -> None:
        try:
            text = self.json_edit.toPlainText()
            data = json.loads(text)
            self._syncing = True
            self.json_edit.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))
            self._syncing = False
            self.json_status_label.setText("JSON 已格式化")
            self.json_status_label.setStyleSheet("color: #5cb85c;")
        except Exception as e:
            self.json_status_label.setText(f"格式化失败：{e}")
            self.json_status_label.setStyleSheet("color: #d9534f;")

    def _on_json_text_changed(self) -> None:
        if self._syncing:
            return
        text = self.json_edit.toPlainText().strip()
        if not text:
            self.json_status_label.setText("JSON 为空")
            self.json_status_label.setStyleSheet("color: #d9534f;")
            return
        try:
            json.loads(text)
            self.json_status_label.setText("JSON 格式良好")
            self.json_status_label.setStyleSheet("color: #5cb85c;")
        except Exception as e:
            self.json_status_label.setText(f"JSON 非法：{e}")
            self.json_status_label.setStyleSheet("color: #d9534f;")

    # ---------- 保存/重置 ----------
    def _on_save_clicked(self) -> None:
        self._apply_form_to_history()
        self.editCompleted.emit(copy.deepcopy(self._history))
        self._append_log("已保存并通过 editCompleted 发出。", "log")
        self.close()
        self.deleteLater()

    def _on_reset_clicked(self) -> None:
        self._history = copy.deepcopy(self._original_history)
        self._load_history_to_form()
        self._update_json_editor_from_history()
        self._append_log("已恢复到初始内容。", "warn")

    # ---------- 日志 ----------
    def _append_log(self, text: str, level: str = "log") -> None:
        prefix = {"log": "", "warn": "[警告] ", "error": "[错误] "}.get(level, "")
        self.log_view.appendPlainText(prefix + text)

    def _on_log_signal(self, s: str) -> None:
        self._append_log(s, "log")
        if "Title generation error" in s or "error" in s.lower():
            if self._gen_running:
                self._append_log("检测到 API 错误，已停止等待。", "warn")
                self._set_generating(False)
                self._current_task_id = None

    def _on_error_signal(self, s: str) -> None:
        self._append_log(s, "error")
        if self._gen_running:
            self._set_generating(False)
            self._current_task_id = None

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
        return chathistory

    # 保存聊天记录
    def save_chathistory(self, chathistory, file_path=None):
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

class HistoryListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 性能与体验优化（可选）
        self.setUniformItemSizes(True)  # 每项统一高度，加速布局计算
        self.setAlternatingRowColors(True)
        self._history_signature = None  # 用于跳过重复刷新

    def populate_history(self, history_data):
        """
        高效填充历史记录：
        - 增量更新：只改动变化的项
        - 暂停重绘/信号，减少 UI 开销
        - 保留当前选中项
        """
        # 若数据完全一致，则跳过
        sig = tuple(
            (item.get('file_path'), item.get('modification_time'), item.get('title'))
            for item in history_data or []
        )
        if sig == self._history_signature:
            return
        self._history_signature = sig

        # 记录当前选中项（按 file_path）
        selected_fp = None
        cur = self.currentItem()
        if cur:
            data = cur.data(Qt.UserRole)
            if isinstance(data, dict):
                selected_fp = data.get('file_path')

        # 暂停信号与重绘
        self.blockSignals(True)
        self.setUpdatesEnabled(False)
        sorting_prev = self.isSortingEnabled()
        self.setSortingEnabled(False)  # 防止排序影响插入顺序

        try:
            # 新数据的顺序与精简映射
            new_order = []
            new_map = {}
            for d in (history_data or []):
                fp = d.get('file_path')
                if not fp:
                    continue  # 跳过无效数据
                lean = {
                    'file_path': fp,
                    'title': d.get('title', 'Untitled Chat'),
                    'modification_time': d.get('modification_time', 0),
                }
                new_order.append(fp)
                new_map[fp] = lean

            # 旧项映射：file_path -> QListWidgetItem
            old_map = {}
            for row in range(self.count()):
                item = self.item(row)
                data = item.data(Qt.UserRole)
                fp = data.get('file_path') if isinstance(data, dict) else None
                if fp:
                    old_map[fp] = item

            # 删除不再存在的项（从底部开始避免重排成本）
            to_remove_rows = sorted(
                (self.row(item) for fp, item in old_map.items() if fp not in new_map),
                reverse=True
            )
            for row in to_remove_rows:
                it = self.takeItem(row)
                del it  # 提示 GC 回收

            # 按新顺序逐个处理：更新/移动/新增
            for target_row, fp in enumerate(new_order):
                data = new_map[fp]
                if fp in old_map:
                    item = old_map[fp]
                    # 文本变化才更新，减少不必要的刷新
                    if item.text() != data['title']:
                        item.setText(data['title'])
                    # 更新存储数据
                    item.setData(Qt.UserRole, data)
                    # 若位置不对，移动到目标位置
                    cur_row = self.row(item)
                    if cur_row != target_row:
                        self.takeItem(cur_row)
                        self.insertItem(target_row, item)
                else:
                    # 新增项
                    item = QListWidgetItem(data['title'])
                    item.setData(Qt.UserRole, data)
                    self.insertItem(target_row, item)

            # 恢复选中项（若仍存在）
            if selected_fp and selected_fp in new_map:
                for row in range(self.count()):
                    item = self.item(row)
                    data = item.data(Qt.UserRole)
                    if isinstance(data, dict) and data.get('file_path') == selected_fp:
                        self.setCurrentRow(row)
                        break
            else:
                # 无选中项则选择第一项（可按需调整）
                if self.count() and self.currentRow() < 0:
                    self.setCurrentRow(0)

        finally:
            self.setSortingEnabled(sorting_prev)
            self.setUpdatesEnabled(True)
            self.blockSignals(False)
    
    def get_selected_file_path(self):
        """获取当前选中项的文件路径"""
        current_item = self.currentItem()
        if current_item:
            item_data = current_item.data(Qt.UserRole)
            return item_data.get('file_path')
        return None

    def get_selected_item_data(self):
        """获取当前选中项的完整数据"""
        current_item = self.currentItem()
        if current_item:
            return current_item.data(Qt.UserRole)
        return None
