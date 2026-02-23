from psygnal import Signal
from service.chat_completion.signals import RequesterSignals

class RequestFlowManagerSignalBus(RequesterSignals):
    request_status = Signal(dict)
    """状态更新信号，发射当前流式解析的状态信息"""

    ask_for_tool_permission = Signal(str, list, list)
    """工具权限请求信号，参数: (request_id, allowed_tools, dangerous_tools)"""

    request_toolcall_resend = Signal(str)
    """工具调用组装请求信号，参数: (request_id, tool_messages)"""

    update_message = Signal(str, list)
    """消息更新信号，用于工具调用时临时上传AI message，参数: (request_id, messages)"""

class ChatFlowManagerSignalBus(RequesterSignals):
    request_status = Signal(dict)
    """状态更新信号，发射当前流式解析的状态信息"""

    ask_for_tool_permission = Signal(str, list, list)
    """工具权限请求信号，参数: (request_id, allowed_tools, dangerous_tools)"""
    
    BGG_finish = Signal(str)
    """背景生成完成信号，参数: path"""

    LCI_finish = Signal(str)
    """LCI完成信号，回传: 日志"""

    tts = Signal(str, str)
    """TTS信号，参数: (request_id, text)"""