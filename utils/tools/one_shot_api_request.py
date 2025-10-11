from PyQt5.QtCore import QObject,pyqtSignal
import threading
import openai
import time
import json
import requests
from utils.function_manager import FunctionManager

class DeltaObject:
    def __init__(self, delta_data):
        self.content = delta_data.get('content', '')
        self.reasoning_content = delta_data.get('reasoning_content', '') if delta_data.get('reasoning_content', '') else delta_data.get('reasoning', '')
        self.tool_calls = self._parse_tool_calls(delta_data.get('tool_calls', []))
    
    def _parse_tool_calls(self, tool_calls_data):
        if not tool_calls_data:
            return None
        
        tool_calls = []
        for tc in tool_calls_data:
            tool_call = type('ToolCall', (), {})()
            tool_call.index = tc.get('index', 0)
            tool_call.id = tc.get('id', '')
            
            # 处理 function 字段
            function_data = tc.get('function', {})
            function_obj = type('Function', (), {})()
            function_obj.name = function_data.get('name', '')
            function_obj.arguments = function_data.get('arguments', '')
            
            tool_call.function = function_obj
            tool_calls.append(tool_call)
        
        return tool_calls


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
        self.provider_type= "openai_compatible"

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
            api_key=self.api_config['key'], 
            base_url=self.api_config['url'] 
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

class FullFunctionRequestHandlerOld(QObject):
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

    #要求重新发送对话，可用于工具调用
    ask_repeat_request=pyqtSignal() # 只是要求重新发起对话

    #请求结果
    request_finished=pyqtSignal(list) # a list of chat history

    def __init__(self):
        super().__init__()
        self.chathistory=[]
        self.full_response =''
        self.think_response =''
        self.chatting_tool_call=None
        self.request_id ='init'
        self.function_manager = FunctionManager()
        self.pause_flag=False
        self.multimodal_content=False
        self.tool_response=''
        self.last_chat_info={
                "id":self.request_id,
                'time':time.strftime("%Y-%m-%d %H:%M:%S")
            }
  
    def send_request(self,params):
        """
        向已配置的 LLM 提供商发送单次对话补全请求。

        参数
        ----
        params : dict
            透传给底层客户端 `chat.completions.create` 的关键字参数，至少应包含：
            - messages : list[dict]
            要发送给模型的对话历史。
            - stream : bool
            是否请求流式响应。

        副作用
        ------
        1. 生成备用请求 ID `self.request_id` 用于追踪与错误报告。
        2. 重置内部状态：
           - `self.full_response`
           - `self.think_response`
           - `self.chathistory`
           - `self.chatting_tool_call`
        3. 通过 `self.client.chat.completions.create(**params)` 调用 LLM。
        4. 根据 `params['stream']` 的值，分别交由 `_handle_non_stream_request`
           或 `_handle_stream_request` 处理。
        5. 发出 `self.request_finished` 信号，携带生成的请求 ID 与组装后的结果消息。

        返回值
        ------
        None
        """
        # 生成报错和供应商崩溃时用的临时ID
        self.request_id='CWLA_local_'+str(int(time.time())+1)

        # 清空旧数据
        self.full_response = ""
        self.think_response = ""
        self.tool_response=''
        self.chathistory=params['messages']
        self.chatting_tool_call=None
        self.pause_flag=False

        # 创建请求
        try:
            self.response = self.client.chat.completions.create(**params)
            if not params['stream']:
                self._handle_non_stream_request()

            else:
                self._handle_stream_request()
            
            self.request_finished.emit(
            self._assembly_result_message()
            )
        except Exception as e:
            self.completion_failed.emit(f'Error in sending request/vast: {e}','error')
            return
        
        if self.chatting_tool_call:
            self.ask_repeat_request.emit()
    def set_provider(self,provider,api_config=None):
        def is_dsls(obj):#dict={'str':['str']} dsls: Dict:{String:List['String']}
            """
            判断是否为{'provider':['url','key']}
            """
            # 检查是否为字典
            if not isinstance(obj, dict):
                return False
            
            # 遍历字典的键值对
            for key, value in obj.items():
                # 检查键是否为字符串
                if not isinstance(key, str):
                    return False
                # 检查值是否为列表
                if not isinstance(value, list) and not isinstance(value, tuple):
                    print(type(value))
                    return False
                # 检查列表中的每个元素是否为字符串
                for item in value:
                    if not isinstance(item, str):
                        return False
            return True
        
        def is_dsds(obj): # {'provider': {'url': 'str','key': 'str'}} dsds: Dict(String:Dict{String:String})
            """
            判断对象是否为: {'provider': {'url': 'str','key': 'str'}}
            """
            # 检查是否为字典
            if not isinstance(obj, dict):
                return False
            
            # 检查外层字典
            for key, value in obj.items():
                # 检查键是否为字符串
                if not isinstance(key, str):
                    return False
                
                # 检查值是否为字典
                if not isinstance(value, dict):
                    return False
                
                # 检查内层字典
                for inner_key, inner_value in value.items():
                    # 检查内层键和值是否为字符串
                    if not isinstance(inner_key, str) or not isinstance(inner_value, str):
                        return False
            
            return True
        
        def is_dsuk(obj): # {'url': 'str','key': 'str'}
            if not isinstance(obj, dict):
                return False
            if not 'url' in obj:
                return False
            elif not 'key' in obj:
                return False
            return True

        #检查是否传入了api_config，如果没有，就去仓库找
        if not api_config:
            api_key,url=self._get_api_info(provider)

        #如果已经传入了api_config
        #开始检查传入类型
        
        # 方便起见，接受多种格式
        # [url,key]
        elif type(api_config)==list and len(api_config)==2:
            api_key=api_config[1]
            url=api_config[0]
        
        # {'provider':['url','key']}
        elif is_dsls(api_config):
            url=api_config[provider][0]
            api_key=api_config[provider][1]
        
        # {'provider': {'url': 'str','key': 'str'}}
        elif is_dsds(api_config):
            url=api_config[provider]['url']
            api_key=api_config[provider]['key']
        
        # {'url': 'str','key': 'str'}
        elif is_dsuk(api_config):
            url=api_config['url']
            api_key=api_config['key']
        
        # 都没找到，报错
        else:
            self.completion_failed.emit('FFR-set_provider','Unrecognized structure')
            raise ValueError('Unrecognized structure'+str(api_config))
        
        self.client = openai.Client(
            api_key=api_key,
            base_url=url
        )

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
    
    def pause(self):
        self.pause_flag=True

    def _special_block_handler(
            self,
            content,                      #incoming content
            signal,                       #function to call
            request_id,
            starter='<think>', 
            ender='</think>',
            extra_params=None,             #extra params to fullfil
        ):
        """处理自定义块内容"""
        if starter in content :
            content = content.split(starter)[1]
            if ender in content:
                return {"starter":True,"ender":True}
            if extra_params:
                if hasattr(self, extra_params):
                    setattr(self, extra_params, content)
            signal(request_id,content)
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
            special_block_handler_result=self._special_block_handler(
                temp_response,
                self.think_response_signal.emit,
                self.request_id,
                starter='<think>', ender='</think>',
                extra_params='think_response'
            )
            if special_block_handler_result["starter"] and special_block_handler_result["ender"]:#如果思考链结束
                self.ai_event_response.emit(self.request_id,content.content)
                self.full_response+= content.content
                self.full_response=self.full_response.replace('</think>\n\n', '')
                self.ai_response_signal.emit(self.request_id,self.full_response)
            elif not (special_block_handler_result["starter"]):#如果没有思考链
                self.ai_event_response.emit(self.request_id,content.content)
                self.full_response += content.content
                self.ai_response_signal.emit(self.request_id,self.full_response)

        # 处理思考链内容
        if hasattr(content, "reasoning_content") and content.reasoning_content:
            self.think_response += content.reasoning_content
            self.think_response_signal.emit(self.request_id,self.think_response)
            self.think_event_signal.emit(self.request_id,content.reasoning_content)
        
        if hasattr(content, "reasoning") and content.reasoning:
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
                
                #tool_call_id 非空的时候才赋值
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
    
    def _handle_tool_call(self, chathistory):
        try:
            # 1) 构造“给模型看的”tool_calls（保证 arguments 是字符串，且不包含 index）
            tool_calls_for_msg = []
            for idx, call in (self.chatting_tool_call or {}).items():
                args_str = call["function"].get("arguments", "")
                if not isinstance(args_str, str):
                    # 若之前被误改成了对象，序列化回字符串，兜底不再报错
                    try:
                        args_str = json.dumps(args_str, ensure_ascii=False)
                    except Exception:
                        args_str = str(args_str)

                tool_calls_for_msg.append({
                    "id": call.get("id"),
                    "type": "function",
                    "function": {
                        "name": call["function"].get("name", ""),
                        "arguments": args_str
                    }
                })

            # 先把“assistant 带 tool_calls”的消息压入历史
            chathistory.append({
                "role": "assistant",
                "content": self.full_response or "",
                "tool_calls": tool_calls_for_msg,
                 "reasoning_content": self.think_response,
                 "info": self.last_chat_info
            })

            # 2) 逐个执行工具（这里用解析后的参数，但不要回写到 tool_calls_for_msg）
            for _, call in (self.chatting_tool_call or {}).items():
                parsed_args = self._load_tool_arguments(call)  # 返回 Python 对象
                call_for_exec = {
                    "id": call.get("id"),
                    "type": "function",
                    "function": {
                        "name": call["function"].get("name", ""),
                        "arguments": parsed_args
                    }
                }
                tool_result = self.function_manager.call_function(call_for_exec)
                if not isinstance(tool_result, str):
                    tool_result = json.dumps(tool_result, ensure_ascii=False)

                chathistory.append({
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "content": tool_result,
                    'info':call
                })

            return chathistory

        except Exception as e:
            print('Failed function calling:', type(e), e)
            self.completion_failed.emit('FFR-tool_call', f"Failed function calling: {e}")

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

        raw = function_call.get("function", {}).get("arguments", "")
        # 默认返回原始
        arguments = raw
        try:
            # 优先按 JSON 解析
            arguments = json.loads(raw)
        except Exception:
            try:
                # 再尝试 Python 字面量（兼容部分厂商奇葩输出）
                import ast
                arguments = ast.literal_eval(raw)
            except Exception:
                # 都不行就返原始字符串
                arguments = raw
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

    def _handle_non_stream_request(self):
        try:
            content = self.response.choices[0].message
            self.request_id = self.response.id
            temp_response = ""
            if getattr(content, "content", None):
                temp_response += content.content
            self._handle_response(content, temp_response)
            self._update_info(self.response)
            print(f'\n返回长度：{len(self.full_response)}\n思考链长度: {len(self.think_response)}')
            return
        except Exception as e:
            try:
                self._handle_stream_request()
                print('已进入流式状态')
                print('fail sending request @1 attempts'+str(e))
            except Exception as f:
                self.completion_failed.emit(
                    self.request_id,
                    'fail sending request @2 attempts'+str(f)
            )   
    
    def _handle_stream_request(self):
        #用于解析ollama等不返回reasoning content的响应
        temp_response = ""

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
                break
            
            # 检测是否接受过ID，没接收过就尝试解析
            if not flag_id_received_from_completion:
                if hasattr(event,'id') and event.id:
                    self.request_id=event.id
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
        
        self.check_finish_reason(event)
        self._update_info(event)
        return event

    def _get_api_info(self,provider):
        pass

    def _assembly_result_message(self):
        if self.chatting_tool_call:
            message=self._handle_tool_call([])
        else:
            message=[{
                'role':'assistant',
                'content':self.full_response,
                'reasoning_content':self.think_response,
                'info':self.last_chat_info
            }]
        return message

class FullFunctionRequestHandler(QObject):
    # CoT
    think_event_signal = pyqtSignal(str, str)
    think_response_signal = pyqtSignal(str, str)

    # 常规推理内容
    ai_event_response = pyqtSignal(str, str)
    ai_response_signal = pyqtSignal(str, str)

    # 工具调用（参数）
    tool_response_signal = pyqtSignal(str, str)

    # 报错
    completion_failed = pyqtSignal(str, str)

    # 结束原因
    report_finish_reason = pyqtSignal(str, str, str)  # request id, finish_reason_raw, finish_reason_readable

    # 要求重新发送对话，可用于工具调用
    ask_repeat_request = pyqtSignal()  # 只是要求重新发起对话

    # 请求结果
    request_finished = pyqtSignal(list)  # a list of chat history

    def __init__(self):
        super().__init__()
        self.chathistory = []
        self.full_response = ''
        self.think_response = ''
        self.chatting_tool_call = None
        self.request_id = 'init'
        self.function_manager = FunctionManager()
        self.pause_flag = False
        self.multimodal_content = False
        self.tool_response = ''
        self.last_chat_info = {
            "id": self.request_id,
            'time': time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.session = requests.Session()
        self.base_url = ''
        self.api_key = ''

    def send_request(self, params):
        """
        向已配置的 LLM 提供商发送单次对话补全请求（使用 requests 库）。
        """
        # 生成报错和供应商崩溃时用的临时ID
        self.request_id = 'CWLA_local_' + str(int(time.time()) + 1)

        # 清空旧数据
        self.full_response = ""
        self.think_response = ""
        self.tool_response = ''
        self.chathistory = params['messages']
        self.chatting_tool_call = None
        self.pause_flag = False

        # 构建请求数据
        request_data = params
        
        # 构建请求头
        headers = self._build_headers()

        # 供应商特殊请求头
        headers = self._apply_headers_providers_patch(headers,params)


        try:
            if params.get('stream', False):
                self._handle_stream_request(request_data, headers)
            else:
                self._handle_non_stream_request(request_data, headers)
            
            self.request_finished.emit(self._assembly_result_message())
        except Exception as e:
            self.completion_failed.emit(f'Error in sending request: {e}', 'error')
            return
        
        if self.chatting_tool_call:
            self.ask_repeat_request.emit()

    def _build_headers(self):
        """构建请求头"""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        return headers

    def _apply_headers_providers_patch(self,headers,params):
        # openrouter
        if 'extra_headers' in params:
            for key,value in params['extra_headers'].items():
                headers[key]=value
        return headers

    def set_provider(self, provider, api_config=None):
        def is_dsls(obj):
            """判断是否为{'provider':['url','key']}"""
            if not isinstance(obj, dict):
                return False
            
            for key, value in obj.items():
                if not isinstance(key, str):
                    return False
                if not isinstance(value, list) and not isinstance(value, tuple):
                    return False
                for item in value:
                    if not isinstance(item, str):
                        return False
            return True
        
        def is_dsds(obj):
            """判断对象是否为: {'provider': {'url': 'str','key': 'str'}}"""
            if not isinstance(obj, dict):
                return False
            
            for key, value in obj.items():
                if not isinstance(key, str):
                    return False
                if not isinstance(value, dict):
                    return False
                for inner_key, inner_value in value.items():
                    if not isinstance(inner_key, str) or not isinstance(inner_value, str):
                        return False
            return True
        
        def is_dsuk(obj):
            """判断是否为 {'url': 'str','key': 'str'}"""
            if not isinstance(obj, dict):
                return False
            if 'url' not in obj or 'key' not in obj:
                return False
            return True

        def get_provider_type(url):
            """
            根据字符串匹配确定供应商类型
            匹配不到默认openai兼容
            不兼容的话后续也会报错
            """
            pre_defined_provider_map={
                'localhost':'local',
                '127.0':'local',
                '192.168':'local',
                'api.deepseek.com':'deepseek',
                'qianfan.baidubce.com':'baidu',
                'api.siliconflow.cn':'siliconflow',
                'api.lkeap.cloud.tencent.com':'tencent',
                'api.moonshot.cn':'kimi',
                'api.novita.ai':'novita',
                'openrouter.ai':'openrouter'
            }
            for feature in pre_defined_provider_map.keys():
                if feature in url:
                    return pre_defined_provider_map[feature]
            return 'openai_compatible'

        # 检查是否传入了api_config，如果没有，就去仓库找
        if not api_config:
            api_key, url = self._get_api_info(provider)
        
        # 如果已经传入了api_config
        elif isinstance(api_config, list) and len(api_config) == 2:
            url = api_config[0]
            api_key = api_config[1]
        
        elif is_dsls(api_config):
            url = api_config[provider][0]
            api_key = api_config[provider][1]
        
        elif is_dsds(api_config):
            url = api_config[provider]['url']
            api_key = api_config[provider]['key']
        
        elif is_dsuk(api_config):
            url = api_config['url']
            api_key = api_config['key']
        
        else:
            self.completion_failed.emit('FFR-set_provider', 'Unrecognized structure')
            raise ValueError('Unrecognized structure' + str(api_config))
        
        self.base_url = url.rstrip('/')
        self.api_key = api_key
        self.provider_type=get_provider_type(self.base_url)

    def _handle_stream_request(self, request_data, headers):
        """处理流式请求"""
        url = f"{self.base_url}/chat/completions"
        temp_response = ""
        flag_id_received_from_completion = False

        try:
            response = self.session.post(
                url, 
                json=request_data, 
                headers=headers, 
                stream=True,
                timeout=60
            )
            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=False):
                if line is None:
                    continue
                # 尝试解码行
                try:
                    line_text = line.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        line_text = line.decode('gbk')
                    except UnicodeDecodeError:
                        try:
                            line_text = line.decode('gb2312')
                        except UnicodeDecodeError:
                            # 如果都不行，使用替换错误策略
                            line_text = line.decode('utf-8', errors='replace')
                line=line_text
                if self.pause_flag:
                    response.close()
                    print('对话已停止。')
                    break
                
                if not line:
                    continue
                
                # 处理 SSE 格式
                if line.startswith('data: '):
                    data = line[6:]  # 去掉 'data: ' 前缀
                    
                    if data == '[DONE]':
                        break
                    
                    try:
                        event = json.loads(data)
                        if not flag_id_received_from_completion and 'id' in event:
                            self.request_id = event['id']
                            flag_id_received_from_completion = True
                        if 'choices' not in event or not event['choices']:
                            return

                        choice = event['choices'][0]

                        delta_data = choice.get('delta', {})
                        content = DeltaObject(delta_data)
                        
                        # 处理内容
                        if hasattr(content, "content") and content.content:
                            temp_response += content.content
                        self._handle_response(content, temp_response)

                    except json.JSONDecodeError:
                        continue

            # 获取最后一个有效事件用于检查完成原因
            if 'event' in locals():
                self.check_finish_reason(event)
                self._update_info(event)

        except requests.exceptions.RequestException as e:
            error_detail = self._extract_error_detail(e, response)
            self.completion_failed.emit(
                self.request_id, 
                f'Stream request failed, error code:\n{e}\nError details:\n{error_detail}\nRequest payload:\n```json\n{json.dumps(request_data, indent=2, ensure_ascii=False)}\n```'
            )

    def _handle_non_stream_request(self, request_data, headers):
        """处理非流式请求"""
        url = f"{self.base_url}/chat/completions"
        
        try:
            response = self.session.post(url, json=request_data, headers=headers, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            self.request_id = data.get('id', self.request_id)
            
            # 处理响应内容
            if 'choices' in data and data['choices']:
                choice = data['choices'][0]
                message = choice.get('message', {})

                message_obj = DeltaObject(message)
                temp_response = message_obj.content or ""
                
                self._handle_response(message_obj, temp_response)
                self._update_info(data)
                
                print(f'\n返回长度：{len(self.full_response)}\n思考链长度: {len(self.think_response)}')
            
        except requests.exceptions.RequestException as e:
            error_detail = self._extract_error_detail(e, response)
            self.completion_failed.emit(
                self.request_id, 
                f'Non-stream request failed: {e}\nError details: {error_detail}'
            )
    
    def _extract_error_detail(self, exception, response):
        """
        从异常和响应中提取详细的错误信息
        
        Args:
            exception: 请求异常对象
            response: 响应对象（可能为None）
            
        Returns:
            str: 格式化的错误详细信息
        """
        error_parts = []
        
        # 1. 添加异常基本信息
        error_parts.append(f"Exception type: {type(exception).__name__}")
        error_parts.append(f"Exception message: {str(exception)}")
        
        # 2. 如果有响应对象，提取状态码和响应体
        if hasattr(exception, 'response') and exception.response is not None:
            response_obj = exception.response
            error_parts.append(f"Status code: {response_obj.status_code}")
            
            try:
                # 尝试解析响应体为JSON
                if response_obj.content:
                    error_data = response_obj.json()
                    if isinstance(error_data, dict):
                        # 常见供应商错误信息字段
                        error_fields = ['error', 'message', 'detail', 'description', 'reason']
                        for field in error_fields:
                            if field in error_data:
                                error_value = error_data[field]
                                if isinstance(error_value, dict):
                                    # 如果错误信息是嵌套字典，进一步提取
                                    nested_fields = ['message', 'type', 'code', 'param']
                                    for nested_field in nested_fields:
                                        if nested_field in error_value:
                                            error_parts.append(f"Error {nested_field}: {error_value[nested_field]}")
                                else:
                                    error_parts.append(f"Error {field}: {error_value}")
                    else:
                        # 如果响应体不是JSON，直接显示文本
                        error_parts.append(f"Response body: {response_obj.text}")
            except (json.JSONDecodeError, ValueError, AttributeError):
                # 如果JSON解析失败，显示原始文本
                if response_obj.text:
                    error_parts.append(f"Response text: {response_obj.text}")
                elif response_obj.content:
                    error_parts.append(f"Response content: {response_obj.content}")
        
        # 3. 如果没有响应对象但有请求对象，显示请求信息
        elif hasattr(exception, 'request') and exception.request is not None:
            request_obj = exception.request
            error_parts.append("No response received")
            if hasattr(request_obj, 'url'):
                error_parts.append(f"Request URL: {request_obj.url}")
            if hasattr(request_obj, 'method'):
                error_parts.append(f"Request method: {request_obj.method}")
        
        # 4. 特定异常类型的额外信息
        if isinstance(exception, requests.exceptions.Timeout):
            error_parts.append("Request timed out")
        elif isinstance(exception, requests.exceptions.ConnectionError):
            error_parts.append("Connection error - check network connectivity and API endpoint")
        elif isinstance(exception, requests.exceptions.HTTPError):
            error_parts.append("HTTP error occurred")
        
        return "\n".join(error_parts)

    def check_finish_reason(self, event):
        """检查并报告 LLM 响应的 finish_reason"""
        try:
            # 适配 requests 返回的数据结构
            if isinstance(event, dict):
                choices = event.get('choices', [])
                if choices:
                    finish_reason = choices[0].get('finish_reason', '')
                else:
                    finish_reason = ''
            else:
                # 如果是对象（在流式处理中可能是模拟对象）
                finish_reason = getattr(event.choices[0], 'finish_reason', '') if hasattr(event, 'choices') and event.choices else ''

            normal_finish_reason = {
                "stop": "正常结束",
                "length": "长度限制",
                "content_filter": "内容过滤",
                "function_call": "函数调用",
                "null": "未完成或进行中",
                None: "未返回完成原因",
                "": "未返回完成原因"
            }
            
            finish_reason_readable = normal_finish_reason.get(
                finish_reason, 
                f"未知结束类型: {finish_reason}"
            )

            self.report_finish_reason.emit(
                self.request_id, 
                str(finish_reason), 
                finish_reason_readable
            )
                
        except Exception as e:
            error_msg = f"处理结束原因时出错: {str(e)}"
            self.completion_failed.emit(self.request_id, error_msg)

    def pause(self):
        self.pause_flag = True

    def _local_model_content_categorizer(
            self, 
            uncategorized_full_content:str, 
            starter='<think>', 
            ender='</think>', 
            reason_var_to_update: str =None,
            content_var_to_update :str = None
        ) -> dict:
        """处理ollama等本地模型的思维链"""
        status={
            "starter": uncategorized_full_content.startswith(starter), # 限制starter在初始位置，缓和聊天提到think token误判
            "ender": ender in uncategorized_full_content, # 不限制末尾位置，完整内容在思考结束以后还有正式内容
            'reasoning_content':'',
            'content':'',
            'is_reasoning':False
        }
        if not status['starter'] and not status['ender']:
            # 没有发现标识，认为是正式内容。
            status['content']=uncategorized_full_content

        elif status['starter'] and status['ender']:
            # 确定了此时存在完整的思维链。
            # 提取出第一段思维链后的字符作为content。
            # 以防有人玩多段thinking花活。
            splited_full_content_position = uncategorized_full_content.index(ender)
            status['reasoning_content'] = uncategorized_full_content[:splited_full_content_position].replace(starter,'')
            status['content'] = uncategorized_full_content[splited_full_content_position+len(ender):]
            status['is_reasoning'] = False

        elif status['starter'] and not status['ender']:
            # 一般正处于思维链过程中，这部分归到思维链没有问题
            status['reasoning_content'] = uncategorized_full_content.replace(starter,'')
            status['is_reasoning'] = True

        elif status['ender'] and not status['starter']:
            # 有些模型不生成初始起始内容，发现think token后把前半段当思维链
            splited_full_content_position = uncategorized_full_content.index(ender)
            status['reasoning_content'] = uncategorized_full_content[:splited_full_content_position].replace(starter,'')
            status['content'] = uncategorized_full_content[splited_full_content_position+len(ender):]
            status['is_reasoning'] = False

        if reason_var_to_update:
            if hasattr(self, reason_var_to_update):
                setattr(self, reason_var_to_update, status['reasoning_content'])
        if content_var_to_update:
            if hasattr(self,content_var_to_update):
                setattr(self,content_var_to_update,status['content'])
        return status

    def _handle_response(self, content:DeltaObject, temp_response):
        """处理响应内容"""
        # 从content中提取思维链和主要内容
        if hasattr(content, "content") and content.content:
            # 目前只看到本地模型不分reasoning，排除本地就可以直接发内容信号
            if not self.provider_type=='local':
                self.ai_event_response.emit(self.request_id, content.content)
                self.full_response += content.content
                self.ai_response_signal.emit(self.request_id, self.full_response)
            
            else:
                # 开始处理本地模型输出
                local_model_result = self._local_model_content_categorizer(
                    temp_response,
                    starter='<think>', ender='</think>',
                )
                if local_model_result['is_reasoning']:
                    self.think_event_signal.emit(self.request_id,content.content)
                else:
                    self.ai_event_response.emit(self.request_id,content.content)
                if local_model_result['reasoning_content'] and not local_model_result['reasoning_content']==self.think_response:
                    self.think_response = local_model_result['reasoning_content']
                    self.think_response_signal.emit(self.request_id,local_model_result['reasoning_content'])
                if local_model_result['content']:
                    self.full_response = local_model_result['content']
                    self.ai_response_signal.emit(self.request_id,local_model_result['content'])


        if hasattr(content, "reasoning_content") and content.reasoning_content:
            self.think_response += content.reasoning_content
            self.think_response_signal.emit(self.request_id, self.think_response)
            self.think_event_signal.emit(self.request_id, content.reasoning_content)
        
        if hasattr(content, "tool_calls") and content.tool_calls:
            temp_fcalls = content.tool_calls
            if not self.chatting_tool_call:
                self.chatting_tool_call = {
                    0: {
                        "id": temp_fcalls[0].id,
                        "type": "function",
                        "function": {"name": "", "arguments": ""}
                    }
                }
            
            for function_call in temp_fcalls:
                tool_call_index = function_call.index
                tool_call_id = function_call.id
                
                if tool_call_id:
                    self.chatting_tool_call[tool_call_index]['id'] = tool_call_id
                
                returned_function_call = getattr(function_call, "function", '')
                returned_name = getattr(returned_function_call, "name", "")

                if returned_name:
                    self.chatting_tool_call[tool_call_index]["function"]["name"] += returned_name
                returned_arguments = getattr(returned_function_call, "arguments", "")

                if returned_arguments:
                    self.chatting_tool_call[tool_call_index]["function"]["arguments"] += returned_arguments
                    self.think_response += returned_arguments
                    self.think_response_signal.emit(self.request_id, self.think_response)
                    self.tool_response += returned_arguments
                    self.tool_response_signal.emit(self.request_id, self.tool_response)

    def _handle_tool_call(self, chathistory):
        """处理工具调用"""
        try:
            tool_calls_for_msg = []
            for idx, call in (self.chatting_tool_call or {}).items():
                args_str = call["function"].get("arguments", "")
                if not isinstance(args_str, str):
                    try:
                        args_str = json.dumps(args_str, ensure_ascii=False)
                    except Exception:
                        args_str = str(args_str)

                tool_calls_for_msg.append({
                    "id": call.get("id"),
                    "type": "function",
                    "function": {
                        "name": call["function"].get("name", ""),
                        "arguments": args_str
                    }
                })

            chathistory.append({
                "role": "assistant",
                "content": self.full_response or "",
                "tool_calls": tool_calls_for_msg,
                "reasoning_content": self.think_response,
                "info": self.last_chat_info
            })

            for _, call in (self.chatting_tool_call or {}).items():
                parsed_args = self._load_tool_arguments(call)
                call_for_exec = {
                    "id": call.get("id"),
                    "type": "function",
                    "function": {
                        "name": call["function"].get("name", ""),
                        "arguments": parsed_args
                    }
                }
                tool_result = self.function_manager.call_function(call_for_exec)
                if not isinstance(tool_result, str):
                    tool_result = json.dumps(tool_result, ensure_ascii=False)

                chathistory.append({
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "content": tool_result,
                    'info': call
                })

            return chathistory

        except Exception as e:
            print('Failed function calling:', type(e), e)
            self.completion_failed.emit('FFR-tool_call', f"Failed function calling: {e}")

    def _load_tool_arguments(self, function_call):
        """解析工具参数"""
        raw = function_call.get("function", {}).get("arguments", "")
        arguments = raw
        try:
            arguments = json.loads(raw)
        except Exception:
            try:
                import ast
                arguments = ast.literal_eval(raw)
            except Exception:
                arguments = raw
        return arguments

    def _to_serializable(self, obj):
        """转换为可序列化对象"""
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        
        if isinstance(obj, dict):
            return {k: self._to_serializable(v) for k, v in obj.items()}
        
        if isinstance(obj, list):
            return [self._to_serializable(item) for item in obj]
        
        if hasattr(obj, '__dict__'):
            return self._to_serializable(vars(obj))
        
        if hasattr(obj, 'model_dump'):
            return self._to_serializable(obj.model_dump())
        
        if hasattr(obj, 'dict'):
            return self._to_serializable(obj.dict())
        
        return str(obj)

    def _update_info(self, event):
        """更新聊天信息（适配 requests 返回结构）"""
        try:
            # 处理不同的事件类型（字典或对象）
            if isinstance(event, dict):
                usage_data = event.get('usage', {})
                model = event.get('model', '')
            else:
                usage_data = getattr(event, 'usage', {})
                model = getattr(event, 'model', '')

            usage_dict = self._to_serializable(usage_data)
            if not isinstance(usage_dict, dict):
                usage_dict = {'usage_data': usage_dict}

            self.last_chat_info = {
                **usage_dict,
                "model": model,
                "id": self.request_id,
                'time': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            return self.last_chat_info
        except Exception as e:
            print('failed info update', str(e))
            self.completion_failed.emit(self.request_id, 'failed info update:' + str(e))
            return {
                "id": self.request_id + ' failed info update ' + str(e),
                'time': time.strftime("%Y-%m-%d %H:%M:%S")
            }

    def _get_api_info(self, provider):
        """获取API信息（需要根据实际情况实现）"""
        # 这里需要根据你的实现来返回 API 信息
        # 返回格式: (url, api_key)
        return "", ""

    def _assembly_result_message(self):
        """组装结果消息"""
        if self.chatting_tool_call:
            message = self._handle_tool_call([])
        else:
            message = [{
                'role': 'assistant',
                'content': self.full_response,
                'reasoning_content': self.think_response,
                'info': self.last_chat_info
            }]
        return message
