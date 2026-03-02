from psygnal import Signal
from common.signal_bus import BaseSignalBus

class RequesterSignals(BaseSignalBus):
    """
    LLM响应信号总线（使用 psygnal）
    
    content/reasoning 携带 request_id 作为第一个参数

    tool call 携带 toolcall id 作为第一个参数

    """
    # 基础流式输出
    stream_content = Signal(str, str)       # (request_id, content_delta)
    stream_reasoning = Signal(str, str)     # (request_id, reasoning_delta)
    stream_tool_delta = Signal(str, dict)   # (toolcall_id, tool_call_delta)

    # 拼接结果输出
    full_content = Signal(str, str)         # (request_id, full_content)
    full_reasoning = Signal(str, str)      # (request_id, full_reasoning)
    full_tool_call = Signal(str, str)     # (toolcall_id, full_tool_call_argument_content)
    
    # 状态通知
    started = Signal(str)                   # (request_id)
    finished = Signal(str, list)            # (request_id, result_list)
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
