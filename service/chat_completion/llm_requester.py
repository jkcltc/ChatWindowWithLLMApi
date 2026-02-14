"""
LLMRequester - Qt-decoupled LLM request handler.

This module provides a Qt-independent, signal-based LLM request handler using
psygnal for event emission. It follows the single responsibility principle by
focusing solely on executing single-shot requests and processing responses,
while delegating tool call orchestration to higher-level managers.

Architecture Overview:
    WorkflowManager (tool call loop orchestration)
        ↓
    LLMRequester (single request execution)
        ↓
    StreamParser + ReasoningParser (protocol parsing)

Key Features:
    - Qt-free: Runs in any Python environment using psygnal signals
    - Streaming-first: Native support for streaming and non-streaming responses
    - State management: Tracks request lifecycle from IDLE to COMPLETED/FAILED
    - Tool call support: Accumulates partial tool calls from streaming responses
    - Reasoning extraction: Handles chain-of-thought content from local models

Example Usage:
    >>> from service.chat_completion.llm_requester import LLMRequester, RequestConfig
    >>> config = RequestConfig(api_key="sk-...", base_url="https://api.example.com")
    >>> requester = LLMRequester(config=config)
    >>> requester.signals.stream_content.connect(lambda rid, text: print(text, end=""))
    >>> requester.send_request({"model": "gpt-4", "messages": [...], "stream": True})

Dependencies:
    - requests: For HTTP session management
    - psygnal: For Qt-compatible signal emission

"""
import time
from enum import Enum
import threading
from typing import Dict, Any, List, Optional, Callable, Union,TYPE_CHECKING
from dataclasses import dataclass, field
import traceback
import requests
from psygnal import Signal,SignalInstance


from .stream_parser import DeltaObject, DeltaType, SimpleSSEParser,decode_content
from .reasoning_parser import StreamingReasoningParser,SimpleReasoningParser


if TYPE_CHECKING:
    from config.settings import ProviderConfig

class RequestState(Enum):
    """请求状态"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RequestConfig:
    """请求配置"""
    api_key: str = ""
    base_url: str = ""
    provider_type: str = "openai_compatible"
    timeout_connect: float = 30.0
    timeout_read: float = 180.0
    max_retries: int = 3


@dataclass  
class RequestResult:
    """请求结果"""
    request_id: str
    content: str = ""
    reasoning_content: str = ""
    tool_calls: Optional[List[Dict]] = None
    finish_reason: Optional[str] = None
    model: Optional[str] = None
    usage: Optional[Dict] = None
    info: Dict[str, Any] = field(default_factory=dict)
    messages: List[Dict] = field(default_factory=list)
    
    def to_chat_history(self) -> List[Dict]:
        """转换为聊天历史格式"""
        message = {
            'role': 'assistant',
            'content': self.content,
            'reasoning_content': self.reasoning_content,
            'info': {
                'id': self.request_id,
                'model': self.model,
                'time': time.strftime("%Y-%m-%d %H:%M:%S"),
                **(self.usage or {})
            }
        }
        
        if self.tool_calls:
            message['tool_calls'] = self.tool_calls
            
        return [message]


class RequesterSignals:
    """
    请求处理器信号定义（使用 psygnal）
    
    content/reasoning 携带 request_id 作为第一个参数

    tool call 携带 toolcall id 作为第一个参数

    """
    # 基础流式输出
    stream_content = Signal(str, str)       # (request_id, content_delta)
    stream_reasoning = Signal(str, str)     # (request_id, reasoning_delta)
    stream_tool_delta = Signal(str, dict)   # (toolcall_id, tool_call_delta)
    
    # 状态通知
    started = Signal(str)                   # (request_id)
    finished = Signal(str, dict)            # (request_id, result_dict)
    failed = Signal(str, str)               # (request_id, error_message)
    """api error"""
    paused = Signal(str)                    # (request_id)
    
    # 特殊事件
    tool_calls_detected = Signal(str, list) # (request_id, list_of_tool_calls)
    finish_reason_received = Signal(str, str, str)  # (request_id, raw_reason, readable_reason)
    
    # 日志和调试
    log = Signal(str)                       # (log_message)
    warning = Signal(str)                   # (warning_message)
    error=Signal(str)                       # (error_message)
    """internal error"""

    def disconnect_all(self):
        """
        断开当前实例上所有信号的所有槽连接。
        """
        # 遍历实例的所有属性
        for name, attr in vars(self.__class__).items():
            if isinstance(attr, Signal):
                instance_signal:SignalInstance = getattr(self, name)
                instance_signal.disconnect()


class LLMRequester:
    """
    LLM 单次请求执行器
    
    设计原则：
    1. 无状态：每次请求独立，不维护对话历史
    2. 去 Qt 化：使用 psygnal，可在任何 Python 环境运行
    3. 职责单一：只负责"发请求-收响应"，不处理工具调用循环
    4. 流式优先：原生支持流式输出
    
    使用示例：
        requester = LLMRequester()
        requester.signals.stream_content.connect(lambda rid, text: print(text, end=''))
        requester.signals.finished.connect(lambda rid, result: print("Done!"))
        
        requester.send_request({
            'model': 'gpt-4',
            'messages': [{'role': 'user', 'content': 'Hello'}],
            'stream': True
        })
    """
    
    # 结束原因映射
    FINISH_REASON_MAP = {
        "stop": "对话正常结束。",
        "length": "对话因长度限制提前结束。",
        "content_filter": "对话因内容过滤提前结束。",
        "function_call": "AI 发起了工具调用。",
        "tool_calls": "AI 发起了工具调用。",
        "tool_call": "AI 发起了工具调用。",
        "null": "未完成或进行中",
        None: "对话结束，未返回完成原因。"
    }
    
    def __init__(self, session:requests.Session, config: Optional[RequestConfig] = None):
        """
        初始化请求处理器
        
        Args:
            config: 请求配置，如果为 None 则使用默认配置
        """
        self.config = config or RequestConfig()
        self.signals = RequesterSignals()
        
        # 会话管理（复用连接池）
        # 不传罢工
        self._session = session

        # 请求状态
        self._state = RequestState.IDLE
        self._pause_flag = threading.Event()
        self._current_request_id: Optional[str] = None
        self._current_response: Optional[requests.Response] = None
        
        # 流式处理组件
        self._reasoning_parser: Optional[StreamingReasoningParser] = None
        
        # 工具调用累积
        self._tool_calls_buffer: Dict[int, Dict] = {}

        self._already_executed = None
        
    def _log(self, message: str):
        """内部日志"""
        self.signals.log.emit(f"[LLMRequester] {message}")
        
    @property
    def state(self) -> RequestState:
        """当前请求状态"""
        return self._state
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._state == RequestState.RUNNING
    
    def set_provider(self, provider: "ProviderConfig"):
        """
        设置 API 提供商
        
        Args:
            provider: ProviderConfig 对象, 包含 api_key, base_url, provider_type
        """
        self.config.api_key = provider.key
        self.config.base_url = provider.url.rstrip('/')
        self.config.provider_type = provider.provider_type
        
    def pause(self):
        """
        暂停当前请求
        别忘了requester.signals.disconnect_all()
        """
        self._pause_flag.set()
        if self._current_request_id:
            self.signals.paused.emit(self._current_request_id)
        
        if self._current_response:
               self._current_response.close()
       

    def send_request(
        self,
        params: Dict[str, Any],
        extra_headers: Optional[Dict[str, str]] = None,
        create_thread:bool=True
    ) -> Optional[threading.Thread|RequestResult]:
        """
        发送请求（主要）
        
        在后台线程中执行请求，通过信号返回结果
        
        Args:
            params: OpenAI 格式的请求参数
            extra_headers: 额外的请求头
            
        Returns:
            执行请求的线程对象，没什么用，纯好玩
        """
        print("send_request!!")
        if self._already_executed:
            """死人在说话"""
            raise RuntimeError("Requester already executed")
        self._already_executed = True
        if create_thread:
            return self.send_request_multithreading(params, extra_headers)
        else:
            return self.send_request_sync(params, extra_headers)

    def send_request_multithreading(
        self,
        params: Dict[str, Any],
        extra_headers: Optional[Dict[str, str]] = None
    ) -> Optional[threading.Thread]:  
        thread = threading.Thread(
            target=self._execute_request_sync,
            args=(params, extra_headers),
            daemon=True
        )
        thread.start()
        return thread
    
    def send_request_sync(
        self,
        params: Dict[str, Any],
        extra_headers: Optional[Dict[str, str]] = None
    ) -> Optional[RequestResult]:
        """
        发送请求（阻塞）
        
        Args:
            params: OpenAI 格式的请求参数
            extra_headers: 额外的请求头
            
        Returns:
            请求结果，失败时返回 None
        """
        # 同步执行请求，不使用额外线程
        return self._execute_request_sync(params, extra_headers)
    
    def _execute_request_sync(
        self,
        params: Dict[str, Any],
        extra_headers: Optional[Dict[str, str]] = None
    ) -> Optional[RequestResult]:
        """同步发送请求的内部实现"""
        # 重置状态
        self._state = RequestState.RUNNING
        self._pause_flag.clear()
        self._current_request_id = f"req_{int(time.time() * 1000)}"
        self._current_response = None
        self._tool_calls_buffer.clear()
        
        # 初始化思维链解析器（本地模型需要）
        is_local = self.config.provider_type == 'local'
        if is_local:
            self._reasoning_parser = StreamingReasoningParser()
        else:
            self._reasoning_parser = None
        
        self.signals.started.emit(self._current_request_id)
        
        try:
            # 构建请求
            url = f"{self.config.base_url}/chat/completions"
            headers = self._build_headers(extra_headers)
            
            is_stream = params.get('stream', False)
            
            if is_stream:
                result = self._handle_stream_request(url, headers, params)
            else:
                result = self._handle_non_stream_request(url, headers, params)
            
            self._state = RequestState.COMPLETED
            self.signals.finished.emit(self._current_request_id, result.__dict__)
            if result:
                return result
            else:
                self.signals.warning('服务器返回了空响应，检查服务状态或参数设置。')
                return None
            
                
        except Exception as e:
            # 发生异常时，先看是不是因为用户按了暂停
            # 如果是，说明流式请求被用户主动终止
            # 无论报错，直接忽略
            if self._pause_flag.is_set():
                self._log(f"请求被用户中断，忽略异常: {e}")
                self._state = RequestState.IDLE
                return None

            # 只有在非暂停状态下的异常，才是真正的故障
            error_msg = self._format_error(e)
            self._state = RequestState.FAILED
            if isinstance(e, (
                requests.exceptions.RequestException,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.HTTPError
            )):
                self.signals.failed.emit(
                    self._current_request_id,
                    f"服务器错误：{error_msg}"
                )
            else:
                self.signals.error.emit(
                    f"请求失败，内部错误: {error_msg}{traceback.format_exc()}"
                )
            return None
    
    def _build_headers(self, extra_headers: Optional[Dict] = None) -> Dict[str, str]:
        """构建请求头"""
        # 给默认值，用户整活自己覆盖去
        headers = {
            'User-Agent': "ChatWindowWithLLMApi-CWLA",
            'Content-Type': 'application/json',
            'Accept-Charset': 'utf-8' ,
            'Authorization': f'Bearer {self.config.api_key}'
        }

        if extra_headers:
            headers.update(extra_headers)
            
        return headers
    
    def _handle_stream_request(
        self, 
        url: str, 
        headers: Dict[str, str], 
        request_data: Dict
    ) -> Optional[RequestResult]:
        """处理流式请求"""
        response = None
        result = RequestResult(request_id=self._current_request_id)
        
        try:
            # 发起请求
            response = self._session.post(
                url,
                json=request_data,
                headers=headers,
                stream=True,
                timeout=(self.config.timeout_connect, self.config.timeout_read)
            )
            self._current_response = response
            
            # 检查 HTTP 状态
            if response.status_code != 200:
                error_text = decode_content(response.content)
                raise requests.HTTPError(
                    f"HTTP {response.status_code}: {error_text}",
                    response=response
                )
            
            # 解析 SSE 流
            is_first_chunk = True
            
            for delta in SimpleSSEParser.parse_stream(response, logger=self._log):
                # 检查暂停
                if self._pause_flag.is_set():
                    response.close()
                    self._log("Request paused by user")
                    break
                
                # 处理 delta
                if delta.delta_type == DeltaType.DONE:
                    break
                    
                self._process_delta(delta, result, is_first_chunk)
                is_first_chunk = False
            
            # 完成思维链解析
            if self._reasoning_parser:
                parse_result = self._reasoning_parser.finalize()
                result.content = parse_result.content
                result.reasoning_content = parse_result.reasoning_content
            
            # 处理工具调用
            if self._tool_calls_buffer:
                result.tool_calls = list(self._tool_calls_buffer.values())
                self.signals.tool_calls_detected.emit(
                    self._current_request_id,
                    result.tool_calls
                )
            
            # 确定 finish_reason
            if not result.finish_reason:
                result.finish_reason = "stop" if not self._pause_flag.is_set() else "paused"
            
            self._emit_finish_reason(result.finish_reason)
            
            return result
            
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"无法连接到服务器: {e}")
        except requests.exceptions.Timeout as e:
            raise TimeoutError(f"请求超时: {e}")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"网络请求错误: {e}")
        finally:
            if response:
                response.close()
    
    def _handle_non_stream_request(
        self,
        url: str,
        headers: Dict[str, str],
        request_data: Dict
    ) -> Optional[RequestResult]:
        """处理非流式请求"""
        response = None
        
        
        try:
            response = self._session.post(
                url,
                json=request_data,
                headers=headers,
                timeout=(self.config.timeout_connect, 60)
            )
            response.raise_for_status()
            
            data = response.json()
            result = RequestResult(
                request_id=data.get('id', self._current_request_id),
                model=data.get('model')
            )
            self._current_response = response
            # 解析响应
            if 'choices' in data and data['choices']:
                choice = data['choices'][0]
                message = choice.get('message', {})
                
                result.content = message.get('content', '')
                result.reasoning_content = message.get('reasoning_content', '') or message.get('reasoning', '')
                result.finish_reason = choice.get('finish_reason')
                result.tool_calls = message.get('tool_calls')
                result.usage = data.get('usage')
                
                # 处理本地模型的思维链
                if self.config.provider_type == 'local' and result.content:
                    
                    parse_result = SimpleReasoningParser.parse(result.content)
                    result.content = parse_result.content
                    result.reasoning_content = parse_result.reasoning_content or result.reasoning_content
            
            # 发送累积的信号
            if result.content:
                self.signals.stream_content.emit(result.request_id, result.content)
            if result.reasoning_content:
                self.signals.stream_reasoning.emit(result.request_id, result.reasoning_content)
            if result.tool_calls:
                self.signals.tool_calls_detected.emit(result.request_id, result.tool_calls)
            
            self._emit_finish_reason(result.finish_reason)
            
            return result
            
        finally:
            if response:
                response.close()
    
    def _process_delta(self, delta: DeltaObject, result: RequestResult, is_first_chunk: bool):
        """处理单个 delta"""
        # 更新 request_id（从第一个响应中获取）
        if is_first_chunk and delta.raw_data and 'id' in delta.raw_data:
            result.request_id = delta.raw_data['id']
            self._current_request_id = result.request_id
        
        # 更新模型信息
        if delta.raw_data and 'model' in delta.raw_data:
            result.model = delta.raw_data['model']
        # 但话又说回来了，如果本地解析器给CoT解析了，我就不用解析了
        if delta.reasoning_content and self._reasoning_parser:
            self._reasoning_parser = None  # 禁用本地解析器

        # 处理内容
        if delta.content:
            if self._reasoning_parser:
                # 本地模型：使用状态机解析
                
                parse_result = self._reasoning_parser.feed(delta.content)
                if parse_result['reasoning_delta']:
                    result.reasoning_content += parse_result['reasoning_delta']
                    self.signals.stream_reasoning.emit(
                        result.request_id,
                        parse_result['reasoning_delta']
                    )

                if parse_result['content_delta']:
                    result.content += parse_result['content_delta']
                    self.signals.stream_content.emit(
                        result.request_id,
                        parse_result['content_delta']
                    )

            else:
                # API 模型：直接发送
                result.content += delta.content
                self.signals.stream_content.emit(result.request_id, delta.content)
        
        # 处理思维链（API 返回的 reasoning_content）
        if delta.reasoning_content:
            result.reasoning_content += delta.reasoning_content
            self.signals.stream_reasoning.emit(result.request_id, delta.reasoning_content)
        
        # 处理工具调用
        if delta.tool_calls:
            self._accumulate_tool_calls(delta.tool_calls, result)
        
        # 更新 finish_reason
        if delta.finish_reason:
            result.finish_reason = delta.finish_reason
    
    def _accumulate_tool_calls(self, tool_calls: List[Dict], result: RequestResult):
        """累积工具调用数据"""
        for tc in tool_calls:
            idx = tc.get('index', 0)
            
            if idx not in self._tool_calls_buffer:
                self._tool_calls_buffer[idx] = {
                    'id': tc.get('id', ''),
                    'type': tc.get('type', 'function'),
                    'function': {'name': '', 'arguments': ''}
                }
            
            # 更新 ID
            if tc.get('id'):
                self._tool_calls_buffer[idx]['id'] = tc['id']
            
            # 更新函数信息
            func = tc.get('function', {})
            name_delta = func.get('name', '')
            if name_delta:
                self._tool_calls_buffer[idx]['function']['name'] += name_delta

            args_delta = func.get('arguments', '')
            if args_delta:
                self._tool_calls_buffer[idx]['function']['arguments'] += args_delta
                # 发送工具调用增量
                self.signals.stream_tool_delta.emit(
                    self._tool_calls_buffer[idx]['id'],
                    {
                        'index': idx,
                        'id': self._tool_calls_buffer[idx]['id'],
                        'name': self._tool_calls_buffer[idx]['function']['name'],
                        'arguments_delta': func['arguments'],
                        'arguments_full': self._tool_calls_buffer[idx]['function']['arguments']
                    }
                )
    
    def _emit_finish_reason(self, finish_reason: Optional[str]):
        """发送结束原因信号"""
        readable = self.FINISH_REASON_MAP.get(finish_reason, f"未知结束类型: {finish_reason}")
        self.signals.finish_reason_received.emit(
            self._current_request_id,
            str(finish_reason),
            readable
        )
    
    def _format_error(self, error: Exception) -> str:
        """格式化错误信息"""
        error_type = type(error).__name__
        error_msg = str(error)
        
        # 尝试提取更详细的错误信息
        if hasattr(error, 'response') and error.response is not None:
            try:
                error_data = error.response.json()
                if 'error' in error_data:
                    error_msg = f"{error_msg} - {error_data['error']}"
            except:
                pass
        
        return f"[{error_type}] {error_msg}"
    
    
    def close(self):
        """关闭请求处理器，释放资源"""
        try:
            if self._current_response:
                self._current_response.close()
        except Exception as e:
            self.signals.warning.emit(f"Error closing response: {e}")
        finally:
            self._current_response = None
        self._state = RequestState.IDLE

