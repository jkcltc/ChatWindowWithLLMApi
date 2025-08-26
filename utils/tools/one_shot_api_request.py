from PyQt5.QtCore import QObject,pyqtSignal
import threading
import openai
import time
import json

class APIRequestHandler(QObject):
    # 定义信号用于跨线程通信
    response_received = pyqtSignal(str)  # 接收到部分响应
    reasoning_response_received = pyqtSignal(str)
    request_completed = pyqtSignal(str)  # 请求完成
    error_occurred = pyqtSignal(str)  # 发生错误
    
    def __init__(self, api_config, parent=None):
        """
        初始化API请求处理器
        :param api_config: API配置信息
        :param parent: 父对象

        api_config={
            "url": default_apis[self.api_provider]["url"],
            "key": default_apis[self.api_provider]["key"]
        }
        """
        super().__init__(parent)
        self.api_config = api_config
        self.client = None
        self.current_thread = None
        self.full_response = ""  # 用于存储完整响应

    def send_request(self, message, model):
        """
        发送API请求（线程安全方式）
        :param message: 提示词
        :param model: 使用的模型
        """
        threading.Thread(
            target=self._send_request_thread,
            args=(message, model)
        ).start()
    
    def special_block_handler(self,content,                      #incoming content                     #function to call
                                  starter='<think>', 
                                  ender='</think>',
                                  extra_params=None             #extra params to fullfill
                                  ):
        """处理自定义块内容"""
        if starter in content :
            content = content.split(starter)[1]
            if ender in content:
                return {"starter":True,"ender":True}
            if extra_params:
                if hasattr(self, extra_params):
                    setattr(self, extra_params, content)

            return {"starter":True,"ender":False}
        return {"starter":False,"ender":False}

    def _send_request_thread(self, messages, model):

        
        def handle_response(content,temp_response):
            if hasattr(content, "content") and content.content:
                special_block_handler_result=self.special_block_handler(temp_response,
                                      starter='<think>', ender='</think>',
                                      extra_params='think_response'
                                      )
                if special_block_handler_result["starter"] and special_block_handler_result["ender"]:#如果思考链结束
                    self.full_response+= content.content
                    self.reasoning_response_received.emit(content.content)
                    self.full_response.replace('</think>\n\n', '')
                elif not (special_block_handler_result["starter"]):#如果没有思考链
                    self.full_response += content.content
                    self.response_received.emit(content.content)
                        # 处理思考链内容
            if hasattr(content, "reasoning_content") and content.reasoning_content:
                self.think_response += content.reasoning_content
                self.reasoning_response_received.emit(content.reasoning_content)
        #try:
        client = openai.Client(
            api_key=self.api_config['key'],  # 替换为实际的 API 密钥
            base_url=self.api_config['url']  # 替换为实际的 API 基础 URL
        )
        try: 
            print('AI回复(流式):',type(messages))
            self.response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,  # 启用流式响应
                )
            self.full_response = ""
            self.think_response = "### AI 思考链\n---\n"
            temp_response = ""
            print('请求已经发到API')


            for event in self.response:
                if not hasattr(event, "choices") or not event.choices:
                    print("无效的响应事件:", event)
                    continue

                content = getattr(event.choices[0], "delta", None)
                if not content:
                    print("无效的内容:", event.choices[0])
                    continue
                if hasattr(content, "content") and content.content:
                    temp_response += content.content
                    handle_response(content,temp_response)
                if hasattr(content, "reasoning_content") and content.reasoning_content:
                    self.think_response += content.reasoning_content
                    print(content.reasoning_content, end='', flush=True)
            print("OSA 请求完成")
            self.request_completed.emit(self.full_response)
        except Exception as e:
            print("OSA API请求错误:", str(e))
            self.error_occurred.emit(f"API请求错误: {str(e)}")

class FullFunctionRequestHandler(QObject):
    #CoT
    think_event_signal=pyqtSignal(str,str)
    think_response_signal=pyqtSignal(str,str)

    #常规推理内容
    ai_event_response=pyqtSignal(str,str)
    ai_response_signal=pyqtSignal(str,str)

    #工具调用（参数）
    tool_response_signal=pyqtSignal(str,str)

    #报错
    completion_failed=pyqtSignal(str,str)

    #结束原因
    report_finish_reason=pyqtSignal(str,str,str) #request id, finish_reason_raw, finish_reason_readable

    #请求结果
    request_finished=pyqtSignal(str,object) #request id, chathistory or None

    def __init__(self):
        super().__init__()
        self.chathistory=[]
        self.full_response =''
        self.think_response =''
        self.chatting_tool_call=None
        self.request_id =''
     
    def _special_block_handler(self,content,                      #incoming content                     #function to call
                                  starter='<think>', 
                                  ender='</think>',
                                  extra_params=None             #extra params to fullfill
                                  ):
        """处理自定义块内容"""
        if starter in content :
            content = content.split(starter)[1]
            if ender in content:
                return {"starter":True,"ender":True}
            if extra_params:
                if hasattr(self, extra_params):
                    setattr(self, extra_params, content)

            return {"starter":True,"ender":False}
        return {"starter":False,"ender":False}

    def _handle_response(self,content,temp_response):
        """
        Handle a single chunk of streaming response from the LLM.
        This method is invoked for every incremental piece of data returned by the
        provider.  It inspects the chunk and dispatches the contained information to
        the appropriate internal buffers and Qt signals:
        - **Main content** (`content.content`)  
            – Emitted through `ai_event_response` and appended to `full_response`.  
            – If the chunk is wrapped in `<think> … </think>` tags, the tags are
                stripped from the final text once the closing tag is seen.
        - **Reasoning / thinking content** (`content.reasoning_content` or
            `content.reasoning`)  
            – Appended to `think_response` and emitted via `think_response_signal`
                and `think_event_signal`.
        - **Tool calls** (`content.tool_calls`)  
            – Aggregated incrementally into `chatting_tool_call`, keyed by the tool
                call index.  
            – Each partial tool-call delta (function name and arguments) is appended
                to both `tool_response` and `think_response`, and the corresponding
                signals (`tool_response_signal`, `think_response_signal`) are emitted.
        Parameters
        ----------
        content : object
                A single streaming chunk returned by the LLM provider.  Expected to
                expose attributes such as `content`, `reasoning_content`, `reasoning`,
                and `tool_calls` when they are present.
        temp_response : str
                Temporary buffer holding the raw text accumulated so far; used by the
                `special_block_handler` to detect `<think>` blocks.
        Notes
        -----
        - The method is designed to be called repeatedly in a streaming context.
        - State is mutated in-place (`full_response`, `think_response`,
            `chatting_tool_call`, etc.).
        - Qt signals are emitted synchronously from within this method.
        """
        if hasattr(content, "content") and content.content:
            special_block_handler_result=self._special_block_handler(self,
                                temp_response,
                                self.think_response_signal.emit,
                                self.request_id,
                                starter='<think>', ender='</think>',
                                extra_params='think_response'
                                )
        if special_block_handler_result["starter"] and special_block_handler_result["ender"]:#如果思考链结束
            self.ai_event_response.emit(self.request_id,content.content)
            self.full_response+= content.content
            self.full_response.replace('</think>\n\n', '')
            self.thinked=True
            self.ai_response_signal.emit(self.request_id,self.full_response)
        elif not (special_block_handler_result["starter"]):#如果没有思考链
            self.ai_event_response.emit(self.request_id,content.content)
            self.full_response += content.content
            self.ai_response_signal.emit(self.request_id,self.full_response)

        # 处理思考链内容
        if hasattr(content, "reasoning_content") and content.reasoning_content:
            self.thinked=True
            self.think_response += content.reasoning_content
            self.think_response_signal.emit(self.request_id,self.think_response)
            self.think_event_signal.emit(self.request_id,content.reasoning_content)
        
        if hasattr(content, "reasoning") and content.reasoning:
            self.thinked=True
            self.think_response += content.reasoning
            self.think_response_signal.emit(self.request_id,self.think_response)
            self.think_event_signal.emit(self.request_id,content.reasoning)
        
        #处理工具调用
        if hasattr(content, "tool_calls") and content.tool_calls:
                
                #获取工具调用内容，包含index,id,function->dict,type
                temp_fcalls = content.tool_calls

                #如果没有初始化，则初始化工具调用字典，用index作为特征
                if not self.chatting_tool_call:
                    self.chatting_tool_call={
                        0:{
                            'index':0,
                            "id": temp_fcalls[0].id,
                            "type": "function",
                            "function": {"name": "", "arguments": ""}
                        }
                    }
                
                #很多供应商一般只在回复列表中包含一个工具调用，但我们都处理
                for function_call in temp_fcalls:
                    
                    #提取index和id，id是重发供应商需要用的
                    tool_call_index=function_call.index
                    tool_call_id=function_call.id

                    if tool_call_id:
                        self.chatting_tool_call[tool_call_index]['id']=tool_call_id

                    # 在同一个index下填充流式进来的内容
                    returned_function_call = getattr(function_call, "function", '')
                    returned_name=getattr(returned_function_call, "name", "")

                    #函数名
                    if returned_name:
                        self.chatting_tool_call[tool_call_index]["function"]["name"] += returned_name
                    returned_arguments=getattr(returned_function_call, "arguments", "")

                    #函数参数
                    if returned_arguments:
                        self.chatting_tool_call[tool_call_index]["function"]["arguments"] += returned_arguments
                        self.think_response += returned_arguments
                        self.think_response_signal.emit(self.request_id,self.think_response)

                        self.tool_response += returned_arguments
                        self.tool_response_signal.emit(self.request_id,self.tool_response)
    
    def _handel_tool_call(self):
        try:
            self.chathistory.append({"role":"assistant",
                                    "content":self.full_response,
                                    'tool_calls':list(self.chatting_tool_call.values()),
                                    'reasoning_content':self.think_response,
                                    'info':self._update_info()})
            for tool_call_item in self.chatting_tool_call:
                arguments=self._load_tool_arguments(tool_call_item)
                tool_result = self.function_manager.call_function(arguments)
                if not isinstance(tool_result, str):
                    tool_result = json.dumps(tool_result, ensure_ascii=False)
                self.chathistory.append({"role":"tool",
                                        "tool_call_id":tool_call_item["id"],
                                        "content":tool_result,
                                        'info':tool_call_item})
            self.request_finished.emit(self.request_id,self.chathistory)
        except Exception as e:
            print('Failed function calling:',type(e),e)
            self.return_message = f"Failed function calling: {e}"
            self.update_response_signal.emit('100000',self.return_message)

    def _load_tool_arguments(self,function_call):
        """
        Parse and normalize the arguments contained in a function-call object.

        Parameters
        ----------
        function_call : dict
            A dictionary that contains at least the key ``"function"`` whose value
            is another dictionary with an ``"arguments"`` key.  The value of
            ``"arguments"`` is expected to be a JSON-encoded string, but may also
            be a stringified Python literal or any other string.

        Returns
        -------
        object
            The deserialized arguments.  The function tries, in order:

            1. ``json.loads``  if the string is valid JSON.
            2. ``ast.literal_eval``  if the JSON attempt fails and the string
               looks like a Python literal.
            3. The original string  if both attempts above fail.

            Any exception raised during deserialization is swallowed and logged;
            the original string is returned as a fallback.

        Notes
        -----
        - The function prints diagnostic messages to stdout when recovery
          attempts are made or when all attempts fail.
        - The returned value is **not** guaranteed to be a dictionary; it can be
          any Python object that results from the deserialization steps above.
        """
        try:
            arguments = json.loads(function_call["function"]["arguments"])  # 验证 JSON 是否合法
            if isinstance(arguments,str):
                print('kimi的字符串load结果又来了\n')
                import ast
                arguments = ast.literal_eval(function_call["function"]["arguments"])
        except json.JSONDecodeError:
            print("函数参数 JSON 解析失败:", function_call["function"]["arguments"],
                  '\n尝试python原生导入',e)
            try:
                import ast
                arguments = ast.literal_eval(function_call["function"]["arguments"])
            except Exception as e:
                arguments=function_call["function"]["arguments"]
                print('python原生导入也不行','函数调用的时候再救',e)
        except Exception as e:
            print(f'狗日的救不回来：{e}','函数调用的时候再救',e)
        finally:
            return arguments

    def _to_serializable(self,obj):
        """递归将对象转换为可序列化的基本类型（字典/列表/基本类型）"""
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        
        if isinstance(obj, dict):
            return {k: self._to_serializable(v) for k, v in obj.items()}
        
        if isinstance(obj, list):
            return [self._to_serializable(item) for item in obj]
        
        if hasattr(obj, '__dict__'):
            # 处理普通对象
            return self._to_serializable(vars(obj))
        
        if hasattr(obj, 'model_dump'):
            # 处理Pydantic v2模型
            return self._to_serializable(obj.model_dump())
        
        if hasattr(obj, 'dict'):
            # 处理Pydantic v1模型
            return self._to_serializable(obj.dict())
        
        # 其他不可识别类型
        return str(obj)
    
    def _update_info(self,event):
        try:
            if event.usage:
                # 递归转换所有嵌套结构
                usage_dict = self._to_serializable(event.usage)
                if isinstance(usage_dict, dict):
                    pass
                else:
                    # 如果转换后不是字典（如某些API返回的列表结构）
                    usage_dict = {'usage_data': usage_dict}
            else:
                usage_dict = {}
                
            self.last_chat_info = {
                **usage_dict,
                "model": event.model,
                "id":self.request_id,
                'time':time.strftime("%Y-%m-%d %H:%M:%S")
            }
            return self.last_chat_info
        except Exception as e:
            print('failed info update',str(e))
            self.completion_failed.emit(self.request_id,'failed info update:'+str(e))
            return{
                "id":self.request_id+' failed info update '+str(e),
                'time':time.strftime("%Y-%m-%d %H:%M:%S")
            }

    def check_finish_reason(self, event):
        """
        检查并报告 LLM 响应的 finish_reason。
        流程：
        1. 从 `event.choices[0].finish_reason` 提取原始结束原因。
        2. 将标准原因映射为可读中文描述。
        3. 通过 `report_finish_reason` 信号发射：
            - request_id
            - 原始结束原因
            - 可读结束原因
        4. 若发生异常，通过 `completion_failed` 信号发射错误信息。
        信号：
             report_finish_reason(str, str, str)
                  成功解析并映射结束原因时发射。
             completion_failed(str, str)
                  解析或映射过程中出现异常时发射。
        异常：
             任何在解析 `event.choices[0].finish_reason` 时抛出的异常都会被捕获，
             并通过 `completion_failed` 信号报告。
        """
        try:
            if hasattr(event, 'finish_reason'):
                finish_reason = str(event.choices[0].finish_reason)
                
                # 定义标准 finish_reason 到可读字符串的映射
                normal_finish_reason = {
                    "stop": "正常结束",
                    "length": "长度限制",
                    "content_filter": "内容过滤",
                    "function_call": "函数调用",
                    "null": "未完成或进行中",
                    None: "未返回完成原因"
                }
                
                # 获取可读的结束原因，若未知则使用原始值
                finish_reason_readable = normal_finish_reason.get(
                    event.choices[0].finish_reason, 
                    f"未知结束类型: {finish_reason}"
                )

                # 发射信号
                self.report_finish_reason.emit(
                    self.request_id, 
                    finish_reason, 
                    finish_reason_readable
                )
                
        except Exception as e:
            # 可选：处理异常情况
            error_msg = f"处理结束原因时出错: {str(e)}"
            self.completion_failed.emit(self.request_id,error_msg)
    
    def _handle_non_stream_request(self):
        try:
            content= self.response.choices[0].message
            request_id=self.response.id
            temp_response += content.content
            self._handle_response(content,temp_response)
            self._update_info(self.response)
            print(f'\n返回长度：{len(self.full_response)}\n思考链长度: {len(self.think_response)}')
            self.update_response_signal.emit(request_id,self.full_response)
            return
        except Exception as e:
            try:
                self.handle_stream_request()
                print('fail sending request @1 attempts'+str(e))
            except Exception as f:
                self.completion_failed.emit(
                    self.request_id,
                    'fail sending request @2 attempts'+str(f)
            )
            print('已进入流式状态')
    
    def _handle_stream_request(self):
        #用于解析ollama等不返回reasoning content的响应
        temp_response = ""

        # 工具调用清单
        self.chatting_tool_call = None

        # 从响应中接收ID的标志
        flag_id_received_from_completion=False

        # 处理响应的各个分块
        for event in self.response:

            # 处理暂停回复
            if self.pause_flag:
                try:
                    self.response.close()
                except Exception as e:
                    print('response.close失败，正在强制停止本地接收。',
                          '\nError Code:',e)
                print('对话已停止。')
                return
            
            # 检测是否接受过ID，没接收过就尝试解析
            if not flag_id_received_from_completion:
                if hasattr(event,'id'):
                    request_id=event.id
                    flag_id_received_from_completion=True

            # 跳过空回复
            if not hasattr(event, "choices") or not event.choices:
                continue
            
            # 获取有效回复
            content = getattr(event.choices[0], "delta", None)

            # delta也有可能是个空的
            if not content:
                continue
            
            # 处理不区分思维链的后端
            if hasattr(content, "content") and content.content:
                temp_response += content.content

            # 开始分块处理内容
            self._handle_response(content,temp_response)

        self._handel_tool_call()
        self._update_info()
        self.check_finish_reason(event)

        print(f'\n返回长度：{len(self.full_response)}\n思考链长度: {len(self.think_response)}')
        self.update_response_signal.emit(request_id,self.full_response)

    def send_request(self,provider,model, params,api_config=None):
        """发送请求并处理流式响应"""
        #检查是否传入了api_config，如果没有，就去仓库找
        if not api_config:
            api_key,url=self.get_api_info(provider)
        #方便起见，接受[url,key]
        elif type(api_config)==list and len(api_config)==2:
            api_key=api_config[1]
            url=api_config[0]
        #生成报错和供应商崩溃时用的临时ID
        self.request_id='CWLA_local_'+str(int(time.time())+1)

        #
        api_provider = self.api_var.currentText()
        client = openai.Client(
            api_key=api_config[provider][1],
            base_url=api_config[provider][0]
        )
        self.response = client.chat.completions.create(**params)
        self.full_response = ""
        self.think_response = ""

        if not params['stream']:
            self._handle_non_stream_request()

        else:
            self._handle_stream_request()
        

    def get_api_info(self,provider):
        pass