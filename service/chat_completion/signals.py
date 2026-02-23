from psygnal import Signal,SignalInstance
from typing import Optional,Union,Iterable
class RequesterSignals:
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

    def disconnect_all(self):
        """
        断开当前实例上所有信号的所有槽连接。
        """
        # 里头只剩信号了
        # 我就不信还能取到什么别的怪东西
        for name, attr in vars(self).items():
            if isinstance(attr, SignalInstance):
                attr.disconnect()

    
    def bus_connect(self, 
                    other, 
                    exclude: Optional[Union[str, Iterable[str]]] = None, 
                    include: Optional[Union[str, Iterable[str]]] = None):
        """
        将当前总线的信号连接到另一个总线实例。支持黑名单和白名单过滤。

        Args:
            other: 目标对象（RequesterSignals 或 Qt 镜像对象）。
            exclude: 不需要连接的信号名称列表（黑名单）。优先级高于 include。
            include: 仅需要连接的信号名称列表（白名单）。如果不传则默认连接所有（除非在 exclude 中）。
        """
        # 1. 标准化参数为集合 set
        def to_set(val):
            if val is None: return set()
            if isinstance(val, str): return {val}
            return set(val)

        exclude_set = to_set(exclude)
        include_set = to_set(include)

        # 2. 遍历自身所有属性
        for name in dir(self):
            # 跳过私有属性
            if name.startswith("_"):
                continue

            # 3. 过滤逻辑
            # 如果在黑名单中，跳过
            if name in exclude_set:
                continue

            # 如果指定了白名单，且当前名字不在白名单中，跳过
            if include_set and name not in include_set:
                continue

            # 4. 获取属性并检查类型
            attr_self = getattr(self, name)

            # 必须是 psygnal 的信号实例
            if isinstance(attr_self, SignalInstance):
                if hasattr(other, name):
                    attr_other = getattr(other, name)
                    # 检查对方是不是也是 psygnal 的信号实例
                    if isinstance(attr_other, SignalInstance):
                        attr_self.connect(attr_other)


