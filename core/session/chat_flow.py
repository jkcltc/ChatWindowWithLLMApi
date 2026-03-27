from typing import TYPE_CHECKING
import time
from config import APP_SETTINGS,APP_RUNTIME

from service.chat_completion import APIRequestHandler

from core.session.title_generate import TitleGenerator
from core.session.session_manager import SessionManager

from core.context.lci.evaluate import LciMetrics,LciEvaluation
from core.context.lci import LciEngine,LCIValidator

from core.multimodal_coordination.background_generater_helper import BggEvaluation,BggMetrics
from core.background import BackgroundAgent

from core.session.data import ChatCompletionPack,RequestType
from core.session.request_flow import RequestFlowManager
from core.session.signals import ChatFlowManagerSignalBus

from core.utils.dispatcher import MainThreadDispatcher as MTD

from utils.status_analysis import StatusAnalyzer

if TYPE_CHECKING:
    from config.settings import LLMUsagePack

class ChatFlowManager:
    """
    聊天流程管理器，负责处理聊天流程中的各种信号和逻辑
    - 和对话会话管理器交互
    - 请求分流到并发器和RFM
    - 上下文工程
    - 分发标题生成
    - 分发背景生成

    """
    def __init__(self,session_manager:SessionManager):
        self.signals=ChatFlowManagerSignalBus()

        # 状态管理
        self.status_analyzer = StatusAnalyzer()

        # 标题生成器要发自己的api请求
        api_requester=APIRequestHandler()
        self.title_generator=TitleGenerator(
            api_handler=api_requester,
            settings=APP_SETTINGS.title
        )
        self._connect_title_signals()

        self.rfm=RequestFlowManager(status_analyzer=self.status_analyzer)
        self._connect_rfm_signals()

        # 持有会话管理器
        self.session_manager = session_manager

        self.lci= LciEngine()#LongChatImprove as LciEngine
        self.lci_validator = LCIValidator()
        self.lci.on_save_history = self._on_lci_complete

        self.bga= BackgroundAgent()
        self._connect_bga_signals()

    def _connect_bga_signals(self):
        self.bga.signals.bus_connect(self.signals)
        self.bga.signals.poll_success.connect(self.signals.BGG_finish.emit)

    #def init_concurrenter(self):
    #    self.concurrent_model=ConvergenceDialogueOptiProcessor()
    #    self.concurrent_model.concurrentor_content.connect(self.concurrentor_content_receive)
    #    self.concurrent_model.concurrentor_reasoning.connect(self.concurrentor_reasoning_receive)
    #    self.concurrent_model.concurrentor_finish.connect(self.concurrentor_finish_receive)

    def _connect_title_signals(self):
        def _set_title(id,title):
            if id == self.session_manager.chat_id:
                self.session_manager.set_title(title)
        self.title_generator.title_generated.connect(_set_title)
        self.title_generator.log.connect(self.signals.log.emit)
        self.title_generator.warning.connect(self.signals.warning.emit)
        self.title_generator.error.connect(self.signals.error.emit)

    def _connect_rfm_signals(self):
        self.rfm.signals.bus_connect(self.signals,exclude='finish_reason_received')
        self.rfm.signals.request_toolcall_resend.connect(self._request_toolcall_resend)
        self.rfm.signals.update_message.connect(self._handle_message_update)
        self.rfm.signals.finished.connect(self._handle_message_update)
        # todo: tts现在接了完整的内容，O(n^2)，要换成接流式
        self.rfm.signals.full_content.connect(self._dist_tts)
        self.rfm.signals.failed.connect(self._handle_request_fail)

    def _handle_request_fail(self, request_id: str, error: str):
        self.signals.error.emit(error)
        self.session_manager.add_new_message(
            role='assistant',
            content=error,
            info={
                'id': 'ERROR_'+request_id,
                'model' : 'ERROR'
            }
        )



    def _handle_message_update(self,request_id,messages):
        self.session_manager.add_messages(messages)
        stats_dict = self.status_analyzer.process_full()
        stats_dict['total_rounds'] = self.session_manager.current_chat.chat_rounds
        stats_dict['total_length'] = self.session_manager.current_chat.chat_length

        self.signals.request_status.emit(stats_dict)

    def _request_toolcall_resend(self,request_id):
        self.send_request(
            request_type=RequestType.TOOL_MESSAGE,
            LLM_usage=APP_SETTINGS.ui.LLM,# 跟随UI自动更新
            temp_style='' # todo: temp style 绑定到app runtime
        )

    def create_chat_title(self):
        include_sys_pmt =   APP_SETTINGS.title.include_sys_pmt
        use_local       =   APP_SETTINGS.title.use_local
        max_length      =   APP_SETTINGS.title.max_length
        task_id         =   self.session_manager.chat_id
        his             =   self.session_manager.history

        self.title_generator.create_chat_title(
            chathistory=his,
            include_system_prompt=include_sys_pmt,
            use_local=use_local,
            max_length=max_length,
            task_id= task_id
        )
    
    def _dist_tts(self,id,text):
        if APP_SETTINGS.tts.tts_enabled:
            self.signals.tts.emit(id,text)

    def pause(self):
        self.rfm.pause()
    
    def resend_message(self, msg_id='', LLM_usage=None, temp_style='') -> bool:
        """
        resend_message : 重发消息，如果msg_id为空，则重发最后一条消息
        """
        chathistory = []
        if not msg_id:
            msg_id = self.session_manager.get_last_message()['info']['id']

        chathistory = self.session_manager.fallback_history_for_resend(msg_id=msg_id)

        if not chathistory or len(chathistory) < 2:
            self.signals.error.emit("重发失败：消息数不足")
            return False

        request_type = None
        for message in reversed(chathistory):
            role = message['role']
            if role == 'user':
                request_type = RequestType.USER_MESSAGE
                break
            elif role == 'assistant':
                request_type = RequestType.ASSISTANT_CONTINUE
                break
            elif role == 'tool':
                request_type = RequestType.TOOL_MESSAGE
                break
        if not request_type:
            self.signals.error.emit("这是塞了什么鬼东西进来重传？")
            return False

        # 如果上层没传参数，兜底使用全局设置
        if not LLM_usage:
            LLM_usage = APP_SETTINGS.ui.LLM

        self.send_request(
            request_type=request_type,
            LLM_usage=LLM_usage,
            temp_style=temp_style
        )

        return True

    # 抛弃功能
    # 0.24.4 模型并发信号
    #def concurrentor_content_receive(self,msg_id,content):
    #    self.full_response=content
    #    self.ai_response.emit(str(msg_id),content)

    #def concurrentor_reasoning_receive(self,msg_id,content):
    #    self.think_response=content
    #    self.thinked=True
    #    self.ai_reasoning.emit(str(msg_id),content)

    #def concurrentor_finish_receive(self,msg_id,content):
    #    self.last_chat_info = self.concurrent_model.get_concurrentor_info()
    #    self.full_response=content
    #    self._receive_message(
    #        {
    #            "role": "assistant",
    #            "content": content,
    #            "info": {
    #                "id": msg_id,
    #                "time":time.strftime("%Y-%m-%d %H:%M:%S")
    #            }
    #        }
    #    )
    def enforce_lci(self):
        self.session_manager.current_chat.reset_chat_rounds()
        self.signals.notify.emit("LCI已启动。")
        self.lci.start(
            session=self.session_manager.current_chat,
            lci_settings=APP_SETTINGS.lci,
            api_settings=APP_SETTINGS.api
        )
    
    def _should_do_lci(self):
        if not APP_SETTINGS.lci.enabled:
            return False

        metrics = LciMetrics.from_session(self.session_manager.current_chat)
        result = LciEvaluation.evaluate(metrics, APP_SETTINGS.lci)

        self.signals.log.emit(result.format_log(APP_SETTINGS.lci))

        return result.triggered

    def _should_update_background(self):
        if not APP_SETTINGS.background.enabled:
            return
        
        metrics = BggMetrics.from_session(self.session_manager.current_chat)
        result = BggEvaluation.evaluate(metrics, APP_SETTINGS.background)

        self.signals.log.emit(result.format_log(APP_SETTINGS.background))

        return result.triggered

    def _trigger_accompanying_function(self):
        # 三位启动自己的线程
        
        if self._should_do_lci():
            self.signals.notify.emit("LCI已启动。")
            self.lci.start(
                session=self.session_manager.current_chat,
                lci_settings=APP_SETTINGS.lci,
                api_settings=APP_SETTINGS.api
            )
            self.session_manager.current_chat.reset_chat_rounds()

        if self._should_update_background():
            self.bga.generate(
                self.session_manager.current_chat,
                setting=APP_SETTINGS.background
            )
            self.session_manager.current_chat.reset_background_rounds()
        
        if self.session_manager.should_generate_title:
            self.create_chat_title()

    def set_activated_tools(self,tool_list):
        self.session_manager.set_tools(tool_list)
    
    @MTD.run_in_main
    def _on_lci_complete(self, generated_items: list[dict], anchor_id: str):

        print(generated_items)
        
        # 135μs  @ scan 5000 items, 10 generated_items, 9800X3D
        context_data = self.session_manager.get_filtered_context_data(generated_items, anchor_id)
        
        if context_data is None:
            self.session_manager.error.emit(f"LCI校验失败: 锚点 {anchor_id} 不存在")
            return
        
        # 1.5μs @ 100 ~ 100k (O(1)?)
        report = self.lci_validator.validate(generated_items, anchor_id, context_data) 
        
        if not report.is_valid:
            self.session_manager.error.emit(f"LCI校验失败: {report.error_msg} ")
            return
        
        # 157μs  @ 3 inserts into 5000 items
        self.session_manager.insert_items_by_anchor(generated_items, report.anchor_id)

        # 排队到下一个节点做deepcopy
        # 6μs  @ 500 items
        @MTD.run_in_main
        def save():
            self.session_manager.request_autosave()
        save()


    def send_new_message(
            self,
            prompt_pack:tuple[str,list],# user_prompt, multimodal_content->list[dict[str:literal[str,list]]
            LLM_usage:"LLMUsagePack",
            temp_style:str='', # 临时风格，这个确实应该在UI上
            ):
        text,multimodal_content=prompt_pack
        self.session_manager.add_new_message(
            role='user',
            content=text,
            multimodal=multimodal_content
        )

        #大胶水启动！
        successful=self.send_request(
            RequestType.USER_MESSAGE,
            LLM_usage=LLM_usage,
            temp_style=temp_style,
            
        )
        return successful


    # >>> 发送请求主函数 <<<
    def send_request(
            self,
            request_type:RequestType,
            LLM_usage:"LLMUsagePack",
            temp_style:str='',
        ):
        start_time=time.time()*1000

        pack = ChatCompletionPack(
            chat_session=self.session_manager.current_chat,
            model=LLM_usage.model,
            provider=APP_SETTINGS.api.providers[LLM_usage.provider],
            provider_name=LLM_usage.provider,
            optional={
                "temp_style": temp_style,
            },
            mod=[]## todo: 把mod功能加进来 self._handle_mod_functions,
        )

        # 启动主循环
        try:
            start_successful = self.rfm.send_request(
                pack=pack,
                request_type=request_type
            )
        except Exception as e:
            start_successful = False
            error_msg = str(e)
            self.signals.error.emit(f'main completion request fail {error_msg}')

        # 启动伴生功能，只有LCI会重插记忆消息
        # 主对话对伴生功能提供的新消息的时机和内容不敏感
        # 最多AI失忆截断后的最早一到二轮
        if start_successful:
            self._trigger_accompanying_function()

            end_time=time.time()*1000
            self.signals.log.emit(
                f'消息送至打包流程:{(end_time-start_time):.2f}ms'
            )

        return start_successful
 