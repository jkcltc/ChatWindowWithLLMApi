from PyQt6.QtCore import QObject,QTimer,pyqtSignal
from service.chat_completion import FullFunctionRequestHandler,APIRequestHandler
from core.session.preprocessor import PreprocessorPatch,Preprocessor,PostProcessor
from core.tool_call.tool_core import get_functions_events,get_tool_registry,ToolRegistry
from core.session.concurrentor import ConvergenceDialogueOptiProcessor
from core.session.title_generate import TitleGenerator
from core.session.session_manager import SessionManager
from config import APP_SETTINGS
import time

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

    def __init__(self,session_manager:SessionManager):
        super().__init__()
        self.init_requester()
        # 全局单例，逮着硬薅
        self.function_manager:ToolRegistry = get_tool_registry()
        get_functions_events().errorOccurred.connect(self.error.emit)

        # 标题生成器要发自己的api请求
        api_requester=APIRequestHandler(api_config=APP_SETTINGS.api.providers)
        self.title_generator=TitleGenerator(api_handler=api_requester)

        # 持有会话管理器
        self.session_manager = session_manager

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

    def create_chat_title_when_empty(self):
        if self.session_manager.should_generate_title:
            self.create_chat_title(self.session_manager.history)

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
    
    def _do_lci(self):
        if APP_SETTINGS.lci.enabled:
            try:
                self.new_chat_rounds+=2

                full_chat_lenth=StrTools.get_chat_content_length(self.current_chat.history)

                message_lenth_bool=(len(self.current_chat.history)>APP_SETTINGS.generation.max_message_rounds \
                                    or full_chat_lenth>APP_SETTINGS.lci.max_total_length)
                
                newchat_rounds_bool=self.new_chat_rounds>APP_SETTINGS.generation.max_message_rounds

                newchat_lenth_bool=StrTools.get_chat_content_length(self.current_chat.history[-self.new_chat_rounds:])>APP_SETTINGS.lci.max_segment_length

                long_chat_improve_bool=message_lenth_bool and newchat_rounds_bool or newchat_lenth_bool

                self.info_manager.log(
                    ''.join(
                        [
                            '长对话优化日志：',
                            '\n当前对话次数:', str(len(self.current_chat.history)-1),
                            '\n当前对话长度（包含system prompt）:', str(full_chat_lenth),
                            '\n当前新对话轮次:', str(self.new_chat_rounds), '/', str(APP_SETTINGS.generation.max_message_rounds),
                            '\n新对话长度:', str(len(str(self.current_chat.history[-self.new_chat_rounds:]))),
                            '\n触发条件:',
                            '\n总对话轮数达标:'
                            '\n对话长度达达到', str(APP_SETTINGS.generation.max_message_rounds), ":", str(message_lenth_bool),
                            '\n新对话轮次超过限制:', str(newchat_rounds_bool),
                            '\n新对话长度超过限制:', str(newchat_lenth_bool),
                            '\n触发长对话优化:', str(long_chat_improve_bool)
                        ]
                    ),
                    level='info'
                )
            except Exception as e:
                self.info_manager.notify(level='error',text='长对话优化失败'+str(e))
                print("LCI还能失败？")
            return long_chat_improve_bool

    #发送消息前的预处理，防止报错,触发长文本优化,触发联网搜索
    def sending_rule(self):   
        user_input = self.user_input_text.toPlainText()
        if self.current_chat.history[-1]['role'] == "user":
            # 创建一个自定义的 QMessageBox
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('确认操作')
            msg_box.setText('确定连发两条吗？')
            
            # 添加自定义按钮
            btn_yes = msg_box.addButton('确定', QMessageBox.ButtonRole.YesRole)
            btn_no = msg_box.addButton('取消', QMessageBox.ButtonRole.NoRole)
            btn_edit = msg_box.addButton('编辑聊天记录', QMessageBox.ButtonRole.ActionRole)
            
            # 显示消息框并获取用户的选择
            msg_box.exec()
            
            # 根据用户点击的按钮执行操作
            if msg_box.clickedButton() == btn_yes:
                # 正常继续
                pass
            elif msg_box.clickedButton() == btn_no:
                # 如果否定：return False
                return False
            elif msg_box.clickedButton() == btn_edit:
                # 如果“编辑聊天记录”：跳转self.edit_chathistory()
                self.edit_chathistory()
                return False
        elif user_input == '':
            # 弹出窗口：确定发送空消息？
            reply = QMessageBox.question(self, '确认操作', '确定发送空消息？',
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.user_input_text.setText('_')
                # 正常继续
            elif reply == QMessageBox.StandardButton.No:
                # 如果否定：return False
                return False
        if APP_SETTINGS.lci.enabled:
            try:
                self.new_chat_rounds+=2

                full_chat_lenth=StrTools.get_chat_content_length(self.current_chat.history)

                message_lenth_bool=(len(self.current_chat.history)>APP_SETTINGS.generation.max_message_rounds \
                                    or full_chat_lenth>APP_SETTINGS.lci.max_total_length)
                
                newchat_rounds_bool=self.new_chat_rounds>APP_SETTINGS.generation.max_message_rounds

                newchat_lenth_bool=StrTools.get_chat_content_length(self.current_chat.history[-self.new_chat_rounds:])>APP_SETTINGS.lci.max_segment_length

                long_chat_improve_bool=message_lenth_bool and newchat_rounds_bool or newchat_lenth_bool

                self.info_manager.log(
                    ''.join(
                        [
                            '长对话优化日志：',
                            '\n当前对话次数:', str(len(self.current_chat.history)-1),
                            '\n当前对话长度（包含system prompt）:', str(full_chat_lenth),
                            '\n当前新对话轮次:', str(self.new_chat_rounds), '/', str(APP_SETTINGS.generation.max_message_rounds),
                            '\n新对话长度:', str(len(str(self.current_chat.history[-self.new_chat_rounds:]))),
                            '\n触发条件:',
                            '\n总对话轮数达标:'
                            '\n对话长度达达到', str(APP_SETTINGS.generation.max_message_rounds), ":", str(message_lenth_bool),
                            '\n新对话轮次超过限制:', str(newchat_rounds_bool),
                            '\n新对话长度超过限制:', str(newchat_lenth_bool),
                            '\n触发长对话优化:', str(long_chat_improve_bool)
                        ]
                    ),
                    level='info'
                )
                if long_chat_improve_bool:
                    self.new_chat_rounds=0
                    self.info_manager.notify('条件达到,长文本优化已触发','info')
                    self.long_chat_improve()
            except Exception as e:
                self.info_manager.notify(f"long chat improvement failed, Error code:{e}",'error')
        if APP_SETTINGS.background.enabled:
            try:
                self.new_background_rounds+=2
                full_chat_lenth=StrTools.get_chat_content_length(self.current_chat.history)
                message_lenth_bool=(len(self.current_chat.history)>APP_SETTINGS.background.max_rounds \
                                    or full_chat_lenth>APP_SETTINGS.background.max_length)
                newchat_rounds_bool=self.new_background_rounds>APP_SETTINGS.background.max_rounds

                long_chat_improve_bool=message_lenth_bool and newchat_rounds_bool

                self.info_manager.log(f"""背景更新日志：
当前对话次数: {len(self.current_chat.history)-1}
当前对话长度（包含system prompt）: {full_chat_lenth}
当前新对话轮次: {self.new_background_rounds}/{APP_SETTINGS.background.max_rounds}
新对话长度: {StrTools.get_chat_content_length(self.current_chat.history[-self.new_background_rounds:])-StrTools.get_chat_content_length([self.current_chat.history[0]])}
触发条件:
总对话轮数达标:
对话长度达到 {APP_SETTINGS.background.max_length}: {message_lenth_bool}
新对话轮次超过限制{APP_SETTINGS.background.max_rounds}: {newchat_rounds_bool}
触发背景更新: {long_chat_improve_bool}""",
                    level='info')
                if long_chat_improve_bool:
                    self.new_background_rounds=0
                    
                    self.info_manager.notify('条件达到,背景更新已触发')
                    self.call_background_update()
                
            except Exception as e:
                LOGGER.error(f"Background update failed, Error code:{e}")
        if APP_SETTINGS.force_repeat.enabled:

            APP_RUNTIME.force_repeat.text=''
            repeat_list=self.repeat_processor.find_last_repeats()
            if len(repeat_list)>0:
                for i in repeat_list:
                    APP_RUNTIME.force_repeat.text+=i+'"或"'
                APP_RUNTIME.force_repeat.text='避免回复词汇"'+APP_RUNTIME.force_repeat.text[:-2]
        else:
            APP_RUNTIME.force_repeat.text=''
        return True

        #预处理用户输入，并创建发送信息的线程
    def send_message_toapi(self):
        '''
        提取用户输入，
        创建用户消息，
        更新聊天记录，
        发送请求，
        清空输入框，
        '''
        self.control_frame_to_state('sending')
        self.ai_response_text.setText("已发送，等待回复...")
        user_input = self.user_input_text.toPlainText()
        multimodal_input=self.user_input_text.get_multimodal_content()

        new_message={
                'role': 'user', 
                'content': user_input,
                'info':{
                    "id":str(int(time.time())),
                    'time':time.strftime("%Y-%m-%d %H:%M:%S")
                    }
            }
        
        if multimodal_input:
            new_message['info']['multimodal']=multimodal_input
        self.current_chat.history.append(new_message)
        self.user_input_text.clear()
        self.create_chat_title_when_empty(self.current_chat.history)
        self.update_chat_history()
        self.send_request(create_thread= not APP_SETTINGS.concurrent.enabled)
    
    
    ###发送请求主函数 0.25.3 api基础重构
    def send_request(self,create_thread=True):
        self.full_response=''
        self.think_response=''
        self.tool_response=''
        def target():
            pack = PreprocessorPatch(self).prepare_patch()  # 创建预处理器实例
            message, params = MessagePreprocessor().prepare_message(pack=pack)
            if APP_SETTINGS.concurrent.enabled:
                self.concurrent_model.start_workflow(params)
                return
            self.requester.set_provider(
            provider=self.api_var.currentText(),
            api_config=APP_SETTINGS.api.providers
            )
            self.requester.send_request(params)
        try:
            if create_thread:
                thread1 = threading.Thread(target=target)
                thread1.start()
            else:
                target()
            self.main_message_process_timer_end=time.time()*1000
            LOGGER.info(f'消息前处理耗时:{(self.main_message_process_timer_end-self.main_message_process_timer_start):.2f}ms')
            self.message_status.start_record(
                model=self.model_combobox.currentText(),
                provider=self.api_var.currentText(),
                request_send_time=self.main_message_process_timer_end/1000
            )
        except Exception as e:
            self.info_manager.notify(f"Error in sending request: {e}",level='error')
        
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