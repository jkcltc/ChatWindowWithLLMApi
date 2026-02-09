from typing import Any, Dict, List, Optional
from PyQt6.QtCore import QObject, pyqtSignal
from service.chat_completion import APIRequestHandler
import time
import re
import uuid
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
