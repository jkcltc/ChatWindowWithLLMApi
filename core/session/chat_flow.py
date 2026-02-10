from typing import TYPE_CHECKING
import time
import uuid
from PyQt6.QtCore import QObject,QTimer,pyqtSignal
from service.chat_completion import FullFunctionRequestHandler,APIRequestHandler
from core.session.preprocessor import PreprocessorPatch,Preprocessor,PostProcessor
from core.tool_call.tool_core import get_functions_events,get_tool_registry,ToolRegistry
from core.session.concurrentor import ConvergenceDialogueOptiProcessor
from core.session.title_generate import TitleGenerator
from core.session.session_manager import SessionManager
from core.session.lci_helper import LciMetrics,LciEvaluation
from core.multimodal_coordination.background_generater_helper import BggEvaluation,BggMetrics
from core.multimodal_coordination.background_generate import BackgroundWorker
from core.session.data import ChatCompletionPack
from config import APP_SETTINGS

if TYPE_CHECKING:
    from config.settings import LLMUsagePack


class ChatFlowManager(QObject):
    log = pyqtSignal(str)
    warning = pyqtSignal(str)
    error = pyqtSignal(str)
    notify = pyqtSignal(str)

    # ui 通知信号
    ai_response =pyqtSignal(str,str)
    """ 'content':str """
    ai_reasoning=pyqtSignal(str,str)
    """ 'reasoning_content':str """
    ai_tool_call=pyqtSignal(str,str)
    """ 
    > LLM tool call
    ['role' : 'assistant']  
    
    'content':str
    """

    status_changed=pyqtSignal(str)

    def __init__(self,session_manager:SessionManager):
        super().__init__()
        self.init_requester()
        # 全局单例，逮着硬薅，得，薅不到
        # self.function_manager:ToolRegistry = get_tool_registry()
        get_functions_events().errorOccurred.connect(self.error.emit)

        # 标题生成器要发自己的api请求
        api_requester=APIRequestHandler(api_config=APP_SETTINGS.api.providers)
        self.title_generator=TitleGenerator(api_handler=api_requester)

        # 持有会话管理器
        self.session_manager = session_manager

        self.lci= None # LciManager()

        self.bgg= BackgroundWorker()


    def init_requester(self):
        self.requester = FullFunctionRequestHandler()

        # 连接信号到具体的方法
        self.requester.ai_response_signal.connect(self._on_ai_response)
        self.requester.think_response_signal.connect(self._on_think_response)
        self.requester.tool_response_signal.connect(self._on_tool_response)

        self.requester.log_signal.connect(self.log.emit)
        self.requester.warning_signal.connect(self.warning.emit)
        self.requester.completion_failed.connect(self.error.emit)

    # 专门处理 AI 响应
    def _on_ai_response(self, request_id, content):
        self.request_id = request_id
        self.full_response = content
        self.ai_response.emit(request_id,content)

    # 专门处理思维链
    def _on_think_response(self, request_id, content):
        self.request_id = request_id
        self.think_response = content
        self.ai_reasoning.emit(request_id,content)

    # 专门处理工具调用
    def _on_tool_response(self, request_id, content):
        self.request_id = request_id
        self.tool_response = content
        self.ai_tool_call.emit(request_id,content)

    def init_concurrenter(self):
        self.concurrent_model=ConvergenceDialogueOptiProcessor()
        self.concurrent_model.concurrentor_content.connect(self.concurrentor_content_receive)
        self.concurrent_model.concurrentor_reasoning.connect(self.concurrentor_reasoning_receive)
        self.concurrent_model.concurrentor_finish.connect(self.concurrentor_finish_receive)


    def create_chat_title(self,chathistory):
        include_sys_pmt =   APP_SETTINGS.title.include_sys_pmt
        use_local       =   APP_SETTINGS.title.use_local
        max_length      =   APP_SETTINGS.title.max_length
        task_id         =   self.session_manager.chat_id

        self.title_generator.create_chat_title(
            chathistory=chathistory,
            include_system_prompt=include_sys_pmt,
            use_local=use_local,
            max_length=max_length,
            task_id= task_id
        )
    
    
    #重生成消息，直接创建最后一条
    def resend_message_last(self):
        self.resend_message()
    
    def _rollback_lci_counters(self, amount=-2):
        """
        _rollback_lci_counters(self, amount=-2) 是消息回退时对两个附属模块触发进度的回退
        
        :param amount: 直接回退一条是-2，留接口给回退好几条的情况
        """
        self.session_manager.apply_updates(
            amount = amount,
            lci=APP_SETTINGS.lci.enabled,
            bgg=APP_SETTINGS.background.enabled
        )
    
    def resend_message(self,msg_id='')->bool:
        """
        resend_message : 重发消息，如果msg_id为空，则重发最后一条消息

        :param msg_id: 说明
        :return: 成功则返回True，实际用于UI的setEnabled(not status)
        :rtype: bool
        """
        chathistory=[]
        start_chat_length=self.session_manager.chat_rounds
        try:
            chathistory = self.session_manager.fallback_history_for_resend(msg_id=msg_id)
        except Exception as e:
            self.error.emit("重发失败：消息回退失败"+str(e))
            return False

        if not chathistory or len(chathistory) < 2:
            self.error.emit("重发失败：消息数不足")
            return False

        end_chat_length=self.session_manager.chat_rounds
        self._rollback_lci_counters(end_chat_length-start_chat_length)

        self.send_request(create_thread= not APP_SETTINGS.concurrent.enabled)

        return True

    #0.25.3 info_manager + api request基础重构
    def resend_message_by_tool(self):
        self._receive_message([])
        self.send_request()

    # 0.24.4 模型并发信号
    def concurrentor_content_receive(self,msg_id,content):
        self.full_response=content
        self.ai_response.emit(str(msg_id),content)

    def concurrentor_reasoning_receive(self,msg_id,content):
        self.think_response=content
        self.thinked=True
        self.ai_reasoning.emit(str(msg_id),content)

    def concurrentor_finish_receive(self,msg_id,content):
        self.last_chat_info = self.concurrent_model.get_concurrentor_info()
        self.full_response=content
        self._receive_message(
            {
                "role": "assistant",
                "content": content,
                "info": {
                    "id": msg_id,
                    "time":time.strftime("%Y-%m-%d %H:%M:%S")
                }
            }
        )
    
    def _should_do_lci(self):
        if not APP_SETTINGS.lci.enabled:
            return False

        metrics = LciMetrics.from_session(self.session_manager.current_chat)
        result = LciEvaluation.evaluate(metrics, APP_SETTINGS.lci)

        self.log.emit(result.format_log(APP_SETTINGS.lci))

        return result.triggered

    def _should_send_message(self):
        # 先检查当前消息
        pass

    
    def _should_update_background(self):
        if not APP_SETTINGS.background.enabled:
            return
        
        metrics = BggMetrics.from_session(self.session_manager.current_chat)
        result = BggEvaluation.evaluate(metrics, APP_SETTINGS.background)

        self.log.emit(result.format_log(APP_SETTINGS.background))

        return result.triggered
    
    def _trigger_accompanying_function(self):
        # 三位启动自己的线程
        if self._should_do_lci():
            self.lci.start(
                payload=self.session_manager.current_chat,
                setting=APP_SETTINGS.lci
            )
        if self._should_update_background():
            self.bgg.start(
                self.session_manager.current_chat,
                setting=APP_SETTINGS.background
            )
        if self.session_manager.should_generate_title:
            self.create_chat_title(self.session_manager.history)

    def send_new_message(
            self,
            prompt_pack:tuple[str,list],# user_prompt, multimodal_content->list[dict[str:literal[str,list]]
            LLM_usage:"LLMUsagePack",
            tool_list:list=None, # 这玩意怎么会是绑定在UI上的，我model呢！
            temp_style:str='', # 临时风格，这个确实应该在UI上
            ):
        text,multimodal_content=prompt_pack
        self.session_manager.add_message(
            role='user',
            content=text,
            multimodal=multimodal_content
        )

        #大胶水启动！
        self.send_request(
            LLM_usage=LLM_usage,
            tool_list=tool_list,
            temp_style=temp_style
        )


    # >>> 发送请求主函数 <<<
    def send_request(
            self,
            LLM_usage:"LLMUsagePack",
            tool_list:list=None,
            temp_style:str='',
        ):
        start_time=time.time()*1000

        # 送走request_workflow_manager的所有请求器，请求器和管理器的连接
        self.request_workflow_manager.abandon_all_requester()

        pack = ChatCompletionPack(
            chathistory=self.session_manager.history,
            model=LLM_usage.model,
            provider=APP_SETTINGS.api.providers[LLM_usage.provider],
            tool_list=tool_list, # 工具列表
            optional={
                "temp_style": temp_style,
            #    "enforce_lower_repeat_text": APP_RUNTIME.force_repeat.text 让patch处理器现场算
            }
        )

        # 让request_workflow_manager自己管理各个请求器的信号
        requset_flow=self.request_workflow_manager.create_requester(id=self.session_manager.chat_id)

        try:
            requset_flow.start(pack)
        except Exception as e:
            self.error.emit('main completion request fail '+str(e))

        # 启动伴生功能，只有LCI会重插记忆消息
        # 主对话对伴生功能提供的新消息的时机和内容不敏感
        # 最多AI失忆截断后的最早一到二轮
        self._trigger_accompanying_function()

        self.status_changed.emit('sending')

        end_time=time.time()*1000
        self.log.emit(f'消息送至打包流程:{(end_time-start_time):.2f}ms')

        self.message_status.start_record(
            model=LLM_usage.model,
            provider=LLM_usage.provider,
            request_send_time=start_time
        )
        return True

        
    #接受信息，信息后处理
    def _receive_message(self,message):
        try:
            message=self._replace_for_receive_message(message)
            self.current_chat.history.extend(message)
            # AI响应状态栏更新
            self.ai_response_text.setMarkdown(self.get_status_str(message_finished=True))

            # mod后处理
            self.mod_configer.handle_new_message(self.full_response,self.current_chat.history)
        except Exception as e:
            self.info_manager.notify(level='error',text='receive fail '+str(e))
        finally:
            self.control_frame_to_state('finished')
            self.update_chat_history()