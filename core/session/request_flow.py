from PyQt6.QtCore import QObject, pyqtSignal
from psygnal import Signal

import requests
import threading
import traceback
import uuid

from typing import TYPE_CHECKING

from core.tool_call.tool_core import get_tool_registry
from core.session.preprocessor import Preprocessor
from service.web_search import WebSearchFacade,RagFilter,WebRagPresetVars
from service.chat_completion.llm_requester import RequesterSignals,OneTimeLLMRequester,RequestConfig
from config import APP_SETTINGS,APP_RUNTIME

from utils.str_tools import StrTools
from utils.status_analysis import StatusAnalyzer

if TYPE_CHECKING:
    from config.settings import AutoReplaceSettings
    from requests import Session as requests_session
    from .data import ChatCompletionPack
    from .session_model import ChatMessage,ChatSession


def _create_qt_bus_class(psygnal_cls, class_name="QtSignalBus"):
    """
    根据 Psygnal 信号类定义，动态生成一个镜像的 QObject 信号总线类。
    """

    qt_signals = {}

    for name, attr in psygnal_cls.__dict__.items():
        if isinstance(attr, Signal):
            qt_signals[name] = pyqtSignal(*getattr(attr, '_types', ()))

    return type(class_name, (QObject,), qt_signals)

# 用类型提示骗代码补全
QRequesterSignals:RequesterSignals = _create_qt_bus_class(RequesterSignals, "QRequesterSignals")

class MidProcessor:
    """
    中间处理器，负责重写流式文本
    """
    def __init__(self,ARS_config:"AutoReplaceSettings"):
        # 获取Request 信号总线
        self.output_signals= RequesterSignals()

        # 附属业务设置
        self.ARS_config =ARS_config

        # 文本处理
        self._raw_buffer = ""          # 原始的累积文本
        self._last_processed = ""      # 上一次处理完发给 UI 的文本
    
    def reset(self):
        self._raw_buffer = ""
        self._last_processed = ""
    
    @property 
    def signals(self):
        return self.output_signals
    
    def bridge_signals(self,request_signals: "RequesterSignals"):
        
        request_signals.bus_connect(
            other= self.output_signals,
            exclude=['stream_content','full_content']
        )

        # full_content全部拦截，stream内容重写
        request_signals.stream_content.connect(self._handle_stream_content)

    def _handle_stream_content(self, req_id, delta):
        # 1. 累积原始流
        self._raw_buffer += delta
        # 2. 全量跑一遍正则
        current_processed = StrTools.vast_replace(
            self._raw_buffer, 
            self.ARS_config.autoreplace_from, 
            self.ARS_config.autoreplace_to
        )
        # 3. 比较差异
        if current_processed.startswith(self._last_processed):

            # 计算增量
            new_part = current_processed[len(self._last_processed):]
            if new_part:
                # 发送增量信号
                self.signals.stream_content.emit(req_id, new_part)

        # 4. 更新状态
        self._last_processed = current_processed

        # 5. 全量信号同步更新
        self.signals.full_content.emit(req_id, current_processed)

if TYPE_CHECKING:
    from config.settings import UserToolPermission,DangerousTools

class PostProcessor:
    warning = Signal(str)

    def __init__(
            self,ARS_config:"AutoReplaceSettings",
            dangerous_tools:"DangerousTools",
            user_tool_permission:"UserToolPermission",
        ):

        self.dangerous_tools = dangerous_tools
        self.user_tool_permission = user_tool_permission
        self.ARS_config =ARS_config


    def handle_results(self,chat_message):
        # 处理一下非正常报错
        self._handle_finish_reason(chat_message)

        # 真的有服务器不返finish_reason = tool_call的
        # 所以不检查结束原因直接过tool filter，
        tc_list= self._handle_tool_filter(chat_message)

        chat_message=self._content_replace(chat_message)

        return chat_message,tc_list

    def _content_replace(self,chat_message:list):
        content_base = chat_message[0]['content'] or '' # chat_message应该是一个长度为1的列表
        content=StrTools.vast_replace(
            content_base, 
            self.ARS_config.autoreplace_from, 
            self.ARS_config.autoreplace_to
        )

        if not content and content_base and content != content_base:
            self.warning.emit("[CMPL_main_Post] 过度替换警告：响应内容在自动替换完成后为空。")
            content = "_"

        chat_message[0]['content'] = content
        
        return chat_message

    def _handle_tool_filter(self, chat_message)->list:
        if "tool_calls" not in chat_message[0]:
            return []
        
        tool_calls = chat_message[0].get('tool_calls',[])
        
        analyzed_tools = [] 

        for index, tool_call in enumerate(tool_calls):
            tool_call_name = tool_call.get('function', {}).get("name")
            if not tool_call_name:
                continue

            # 核心鉴权逻辑不变
            if tool_call_name in self.user_tool_permission.names:
                status = "allowed"
            elif tool_call_name in self.dangerous_tools.names:
                status = "denied"
            else:
                status = "allowed"
            
            # 把原始工具和它的状态打包在一起，追加到列表
            analyzed_tools.append({
                "tool_call": tool_call, 
                "status": status,
                "index": index
            })
        return analyzed_tools

    def _handle_finish_reason(self,chat_message):
        message = chat_message[0]
        finish_reason= str(message['info']['finish_reason'])
        if not finish_reason in [
            'tool_calls','stop',"None","Null","length","tool_call","paused","function_call"
            ]:
            self.abnormal_finish.emit(chat_message[0]['info']['finish_reason'])

        if not finish_reason == 'content_filter':
            has_content = (
                message.get('content') 
                or message.get('reasoning_content') 
                or (message.get('tool_calls', [{}])[0].get('function', {}).get('arguments'))
            )

            if not has_content:
                self.warning.emit("empty message received, finish_reason: "+finish_reason)

class RequesterPool:
    log=Signal(str)
    def __init__(self):
        self.requesters:set[OneTimeLLMRequester] = set()
        self.current_requester:OneTimeLLMRequester = None

    def add_requester(self,requester:OneTimeLLMRequester):
        self.abandon_all()

        self.current_requester = None
        self.current_requester = requester

        self.requesters.add(requester)
    
    def abandon_all(self):
        """
        清理所有请求，重置状态。
        """
        for req in list(self.requesters):
            try:
                req.signals.disconnect_all()
            except Exception as e:
                self.log.emit(f"[RequesterPool] Disconnect error: {e}")

            try:
                req.close()
            except Exception as e:
                self.log.emit(f"[RequesterPool] Close error: {e}")
        self.requesters.clear()
        self.current_requester = None

class ToolNotExecutedError(RuntimeError):pass
class MessageOrderError(RuntimeError):pass

class RequestFlowManager:
    """
    主对话流程管理器 (Request Flow Manager)
    
    负责管理主对话的完整生命周期，包括预处理、LLM请求、后处理和工具调用。
    注意：此类只管主对话流程，不处理LCI(长上下文注入)/BGG(背景生成)等协作业务。
    
    主流程 pipeline:
        CFM下发对话包 -> 创建新线程 -> 进pre(预处理) -> 创建请求器
        -> 发送请求 -> mid(中间处理)接管流式转发 -> 进post(后处理)
        -> 离开线程 -> post做工具调用拦截处理 -> 结束/工具回调循环
    
    Signals:
        status (dict): 状态更新信号，包含当前流式解析状态
        ask_for_tool_permission (str, list, list): 请求工具权限信号，参数为(请求ID, 允许工具列表, 危险工具列表)
        request_tool_call_assembly (str, list): 请求组装工具回调信号，参数为(请求ID, 工具消息列表)
        update_message (str, list): 更新消息信号，用于工具调用时临时上传AI消息，参数为(请求ID, 消息列表)
    """
    status = Signal(dict)
    """状态更新信号，发射当前流式解析的状态信息"""

    ask_for_tool_permission = Signal(str, list, list)
    """工具权限请求信号，参数: (request_id, allowed_tools, dangerous_tools)"""

    request_tool_call_assembly = Signal(str, list)
    """工具调用组装请求信号，参数: (request_id, tool_messages)"""

    update_message = Signal(str, list)
    """消息更新信号，用于工具调用时临时上传AI message，参数: (request_id, messages)"""

    def __init__(self):
        """
        初始化 RequestFlowManager。
        
        初始化各处理器(pre/mid/post)、请求池、搜索组件和信号连接。
        """
        super().__init__()

        # 状态管理
        self.status_analyzer = StatusAnalyzer()

        # tool loop
        self.function_manager = get_tool_registry()

        # 搜索组件
        self.search_facade = WebSearchFacade(
            engine_name=APP_SETTINGS.web_search.search_engine,
            max_workers=min(6, APP_SETTINGS.web_search.search_results_num),
            timeout=12,
            rag_filter=RagFilter(
                prefix=WebRagPresetVars.prefix,
                suffix=WebRagPresetVars.subfix,
            )
        )

        # Request 三阶段
        self.pre_processor:Preprocessor = Preprocessor(
            search_facade=self.search_facade
        )

        self.mid_processor = MidProcessor(
            ARS_config=APP_SETTINGS.replace,
        )

        self.post_processor = PostProcessor(
            ARS_config=APP_SETTINGS.replace,
            dangerous_tools=APP_RUNTIME.dangerous_tools,
            user_tool_permission=APP_SETTINGS.tool_permission
        )
        self.post_processor.warning.connect(self.signals.warning.emit)

        # Requester生命周期管理
        self.requester_pool : RequesterPool = RequesterPool()

        self.request_session : "requests_session" = requests.session()

        self.current_requester : OneTimeLLMRequester = None

        # 信号总线
        self.signals = RequesterSignals()
        self._connect_mid_signals()


        # cache
        self._request_id_for_tool=''

    def _connect_mid_signals(self):
        """
        连接中间处理器的信号到主信号总线。
        
        将 mid_processor 的流式信号连接到 RequesterSignals，
        并将 reasoning 和 content 流连接到状态更新处理器。
        """
        self.mid_processor.signals.bus_connect(self.signals)
        self.mid_processor.signals.stream_reasoning.connect(
            self._update_status
        )
        self.mid_processor.signals.stream_content.connect(
            self._update_status
        )
    
    def _update_status(self, request_id: str, content: str):
        """
        更新并发射流式解析状态。
        
        通过 StatusAnalyzer 处理流式内容，并将结果发射到 status 信号。
        
        Args:
            request_id: 请求唯一标识
            content: 当前流式内容片段
        """
        result = self.status_analyzer.process_stream(request_id, content)
        self.status.emit(result)

    def reset(self):
        """
        重置 RequestFlowManager 的状态。
        
        清空工具请求ID缓存、放弃所有进行中的请求、重置状态分析器和中间处理器。
        通常在开始新请求前调用。
        """
        self._request_id_for_tool = ''
        self.requester_pool.abandon_all()
        self.status_analyzer.reset()
        self.mid_processor.reset()
        self.current_requester=None
        # self.post_processor.reset() # 无状态


    def _should_send_message(self, chat_session: "ChatSession", request_type="user_message"):
        """
        检查是否应该发送消息，验证消息顺序和工具调用状态。
        
        Args:
            chat_session: 当前聊天会话对象
            request_type: 请求类型，可选值:
                - "user_message": 用户新消息
                - "tool_message": 工具回调消息
                - "assistant_continue": AI续写模式
        
        Raises:
            ToolNotExecutedError: 当AI发起了工具调用但历史记录中缺少对应的工具执行结果时
            MessageOrderError: 当消息顺序不符合预期时
            RuntimeError: 当消息未组装时
        """
        history = chat_session.history
        if not history:
            raise RuntimeError("严重：消息未组装")

        user_last_index = chat_session.get_last_index("user")
        assistant_last_index = chat_session.get_last_index("assistant")
        tool_last_index = chat_session.get_last_index("tool")


        last_ai_message = chat_session.get_last_message("assistant")
        if last_ai_message: # 确保 AI 说过话
            message_tool_call = last_ai_message.get('tool_calls', [])
            if message_tool_call and (tool_last_index < assistant_last_index):
                raise ToolNotExecutedError(
                    "拦截: AI 发起了工具调用，但历史记录中缺少对应的工具执行结果。"
                )

        if request_type == "user_message":
            if user_last_index < assistant_last_index:
                raise MessageOrderError(
                    f"用户消息乱序，History: {history[assistant_last_index:]}"
                )
        
        elif request_type == "tool_message":
            # 确保最后一次操作是工具回传
            if tool_last_index < assistant_last_index:
                raise MessageOrderError(
                    f"消息乱序: 试图发送工具回调，但最后一条消息不是工具结果。"
                )
        
        elif request_type == "assistant_continue":
            # 续写模式下，最后一条必须是 AI 的半截话
            if history[-1].get("role") != "assistant":
                raise MessageOrderError(
                    f"消息乱序: 续写模式要求最后一条消息来自 assistant，当前为 {history[-1].get('role')}"
                )

    def send_request(self, pack: "ChatCompletionPack", request_type="user_message"):
        """
        发送主对话请求。
        
        这是主入口方法，负责：
        1. 重置状态
        2. 验证消息顺序
        3. 启动状态记录
        4. 打包工具列表
        5. 创建请求器并配置信号
        6. 在后台线程启动请求流程
        
        Args:
            pack: 包含对话所需所有数据的 ChatCompletionPack
            request_type: 请求类型，参见 _should_send_message()
        """
        # 重置状态
        self.reset()

        self._should_send_message(pack.chat_session,request_type)

        self.status_analyzer.start_record(model=pack.model, provider=pack.provider_name)

        # 打包工具详情
        pack.tool_list=self.function_manager.openai_tools(
            pack.chat_session.tools
        )

        # 预先创建请求器以复用requester_pool
        req_config = RequestConfig(
            key=pack.provider.key,
            url=pack.provider.url,
            provider_type=pack.provider.provider_type,
        )
        
        self.current_requester=OneTimeLLMRequester(
            config = req_config,
            session=self.request_session
        )
        self.mid_processor.bridge_signals(self.current_requester.signals)
        self.current_requester.signals.finished.connect(self._on_requester_finished)

        self.requester_pool.add_requester(self.current_requester)

        # 启动请求线程
        threading.Thread(
            target=self._RWM_main_request_thread,
              args=(pack,self.current_requester), 
              daemon=True
            ).start()

    def _RWM_main_request_thread(self, pack: "ChatCompletionPack", requester: OneTimeLLMRequester):
        """
        主请求线程入口，在后台线程中运行。
        
        执行流程：
        1. 前处理(prepare_message)
        2. 检查请求是否被取消
        3. 发送实际请求
        
        Args:
            pack: 对话数据包
            requester: 一次性LLM请求器实例
        
        Note:
            网络错误由 requester 自身处理，此处只捕获处理内部错误。
        """
        try:
            # 1. 前处理
            __messages_unused, payload = self.pre_processor.prepare_message(pack)
            
            # 2. 拦截取消的请求
            if requester not in self.requester_pool.requesters:
                return

            # 3. 发送请求
            requester.send_request(payload,create_thread=False)

        except:
            # 网络错误已经由requester处理
            # 主动的raise只有OTLR复用
            # 这里只处理内部错误
            error_message=traceback.format_exc()
            self.signals.error.emit(error_message)
            self.signals.failed.emit(f"[RWM M_R] failed {uuid.uuid4()}",str(error_message))



    def _on_requester_finished(self, request_id: str, result: list[dict]):
        """
        请求完成回调，处理响应结果和工具调用。
        
        此方法在主线程执行，负责：
        1. 后处理响应内容
        2. 如果没有工具调用，发射 finished 信号结束流程
        3. 如果有工具调用，分类处理(允许/拒绝)并进入工具回调流程
        
        Args:
            request_id: 请求唯一标识
            result: LLM返回的消息列表
        """
        chat_message,tc_list = self.post_processor.handle_results(result) 

        if not tc_list:
            # CFM把AI响应加进chat session
            self.signals.finished.emit(request_id,chat_message)
            return
        else:
            self.update_message.emit(request_id,chat_message)

        self._request_id_for_tool=request_id
        _dn_tools=[]
        _ap_tools=[]
        for toolcall in tc_list:
            if toolcall['status']=="denied":
                _dn_tools.append(toolcall)
            else:
                _ap_tools.append(toolcall)

        # 一起发方便回传
        if _dn_tools:
            self.ask_for_tool_permission.emit(request_id,_ap_tools,_dn_tools)
            return
        self.exec_tool_calls(request_id=self._request_id_for_tool,allowed_tool_call=_ap_tools)


    def exec_tool_calls(
            self,
            request_id: str,
            allowed_tool_call: list,
            denied_tool_call: list = None,
        ):
        """
        执行工具调用。
        
        验证请求ID后，在后台线程启动工具执行流程。
        
        Args:
            request_id: 请求唯一标识，用于验证调用有效性
            allowed_tool_call: 已授权允许执行的工具调用列表
            denied_tool_call: 被拒绝的工具调用列表(可选)，会返回拒绝原因
        
        Note:
            如果 request_id 不匹配当前缓存的ID，将放弃执行并发射警告信号。
        """
        if request_id != self._request_id_for_tool:
            self.signals.warning.emit("请求ID不匹配，工具回调弃用")
            return
        threading.Thread(
            target=self._tool_call_thread,
              args=(request_id,allowed_tool_call,denied_tool_call), 
              daemon=True
            ).start()

    def _tool_call_thread(self, request_id, allowed_tool_call, denied_tool_call):
        """
        工具调用执行线程。
        
        在后台线程中执行实际的工具调用，包括：
        1. 执行允许的工具调用
        2. 为被拒绝的工具生成拒绝响应
        3. 组装工具消息并发射回调请求
        
        Args:
            request_id: 请求唯一标识
            allowed_tool_call: 允许执行的工具调用列表
            denied_tool_call: 被拒绝的工具调用列表
        
        Emits:
            request_tool_call_assembly: 组装完成的工具消息列表
        """
        message_to_be_returned={}
        for call in allowed_tool_call:
            tool_to_exec=call['tool_call']
            call_index=call["index"]
            try:
                exec_result = self.function_manager.call_from_openai(tool_to_exec)
                self.signals.log.emit(f"工具调用结果: {exec_result}")
                if  exec_result['ok']:
                    tool_result = exec_result['result']
                else:
                    tool_result = f"工具执行出错: {exec_result['message']}"
                    self.signals.warning.emit(tool_result)
            except Exception as e:
                # AI用错误的参数调用了工具或者执行内容把工具干碎了
                tool_result= f"工具解析出错: {e}"

            message_to_be_returned[call_index]={
                    "role": "tool",
                    "tool_call_id": tool_to_exec.get("id"),
                    "content": tool_result,
                    'info': tool_to_exec
                }

        denied_tool_call = denied_tool_call or []
        for call in denied_tool_call:
            tool_to_exec=call['tool_call']
            call_index=call["index"]
            message_to_be_returned[call_index]={
                    "role": "tool",
                    "tool_call_id": tool_to_exec.get("id"),
                    "content": "工具调用被拒绝。原因：用户拦截。",
                    'info': tool_to_exec
                }
        
        # 按 call_index 排序，生成有序列表
        sorted_indices = sorted(message_to_be_returned.keys())
        tool_call_result_list = [message_to_be_returned[i] for i in sorted_indices]

        # 检查用户有没有refresh Request
        if request_id == self._request_id_for_tool:
            # 叫上层更新chatsession，更新UI，然后重新下发请求
            self.request_tool_call_assembly.emit(self._request_id_for_tool,tool_call_result_list)

    def send_tool_callback_request(self, pack):
        """
        发送工具回调请求。
        
        包装方法，将工具结果作为新请求发送给LLM。
        
        Args:
            pack: 包含工具消息的 ChatCompletionPack
        """
        self.send_request(pack, request_type="tool_message") 
