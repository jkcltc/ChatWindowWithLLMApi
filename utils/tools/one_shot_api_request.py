from PyQt6.QtCore import QObject,pyqtSignal
import threading
import openai
import time
import json
import requests
from utils.tool_core import get_tool_registry

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

def extract_api_info(provider, api_config=None):
    """
    提取API信息，支持多种api_config格式
    :param provider: 提供商名称
    :param api_config: API配置信息
    :return: (api_key, url, provider_type)
    """
    def is_api_config_object(obj):
        """判断是否为 ApiConfig 数据类"""
        return hasattr(obj, 'providers') and hasattr(obj, 'endpoints')

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
        不使用输入的provider参数是因为防止有人把供应商A写成供应商B
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
        return None,None,None
        #api_key, url = self._get_api_info(provider)
    
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
    
    elif is_api_config_object(api_config):
        if provider not in api_config.providers:
            raise ValueError(f'Provider "{provider}" not found in api_config')
        config = api_config.providers[provider]
        url = config.url
        api_key = config.key
    
    else:
        #self.completion_failed.emit('FFR-set_provider', 'Unrecognized structure')
        raise ValueError('Unrecognized structure' + str(api_config))
    return api_key, url, get_provider_type(url)
class FullFunctionRequestHandler(QObject):
    # CoT
    think_event_signal = pyqtSignal(str, str)
    think_response_signal = pyqtSignal(str, str)

    # 常规推理内容
    ai_event_response = pyqtSignal(str, str)
    ai_response_signal = pyqtSignal(str, str)

    # 工具调用（参数）
    tool_response_signal = pyqtSignal(str, str)

    # 日志
    log_signal = pyqtSignal(str)

    # 警告
    warning_signal = pyqtSignal(str)

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
        self.function_manager = get_tool_registry()
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
        self.last_chat_info = {
            "id": self.request_id,
            'time': time.strftime("%Y-%m-%d %H:%M:%S")
        }

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
        if api_config:
            try:
                api_key, url, provider_type = extract_api_info(provider, api_config)
            except ValueError as e:
                self.completion_failed.emit('FFR-set_provider', str(e))
        else:
            api_key, url, provider_type = self._get_api_info(provider)
        self.base_url = url.rstrip('/')
        self.api_key = api_key
        self.provider_type = provider_type

    def _handle_stream_request(self, request_data, headers):
        """处理流式请求"""
        url = f"{self.base_url}/chat/completions"
        temp_response = ""
        flag_id_received_from_completion = False
        response=None
        try:
            response = self.session.post(
                url, 
                json=request_data, 
                headers=headers, 
                stream=True,
                timeout=180
            )
            if response.status_code != 200:
                raise Exception(json.dumps(response.json(), indent=2, ensure_ascii=False))

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
                            self.last_chat_info['id']=self.request_id
                            flag_id_received_from_completion = True
                        if 'choices' not in event or not event['choices']:
                            continue

                        choice = event['choices'][0]

                        delta_data = choice.get('delta', {})
                        content = DeltaObject(delta_data)
                        
                        # 处理内容
                        if hasattr(content, "content") and content.content:
                            temp_response += content.content
                        self._handle_response(content, temp_response)

                    except json.JSONDecodeError:
                        self.log_signal(f'FFR streaming-JSONDecodeError,id:{self.request_id}')
                        continue

            # 获取最后一个有效事件用于检查完成原因
            if 'event' in locals():
                self.check_finish_reason(event)
                self._update_info(event)

        except Exception as e:
            self.completion_failed.emit(
                self.request_id, 
                f'''Stream request failed.
Error code :
```json
{e}
```'''
#Request payload :
#```json
#{json.dumps(request_data, indent=2, ensure_ascii=False)}
#```'''
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
            self.completion_failed.emit(
                self.request_id, 
                f'Non-stream request failed: {e}'
            )

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
                    "stop": "对话正常结束。",
                    "length": "对话因长度限制提前结束。",
                    "content_filter": "对话因内容过滤提前结束。",
                    "function_call": "AI发起了工具调用。",
                    "null": "未完成或进行中",
                    None: "对话结束，未返回完成原因。"
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
                
                if not tool_call_index in self.chatting_tool_call:
                    self.chatting_tool_call[tool_call_index] = {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {"name": "", "arguments": ""}
                }
                if tool_call_id:
                    self.chatting_tool_call[tool_call_index]['id'] = tool_call_id
                
                returned_function_call = getattr(function_call, "function", '')
                returned_name = getattr(returned_function_call, "name", "")

                if returned_name:
                    self.chatting_tool_call[tool_call_index]["function"]["name"] += returned_name
                returned_arguments = getattr(returned_function_call, "arguments", "")

                if returned_arguments:
                    self.chatting_tool_call[tool_call_index]["function"]["arguments"] += returned_arguments
                    #self.think_response += returned_arguments
                    #self.think_response_signal.emit(self.request_id, self.think_response)
                    # 准备只用tool_response转发
                    self.tool_response += returned_arguments
                    self.tool_response_signal.emit(tool_call_id, self.tool_response)

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
                try:
                    exec_result = self.function_manager.call_from_openai(call_for_exec)
                    self.log_signal.emit(f"工具调用结果: {exec_result}")
                    if  exec_result['ok']:
                        tool_result = exec_result['result']
                    else:
                        tool_result = f"工具执行出错: {exec_result['message']}"
                        self.warning_signal.emit(tool_result)

                except Exception as e:
                    tool_result= f"工具解析出错: {e}"

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
                usage_data = event.get('usage')
                model = event.get('model', '')
            else:
                usage_data = getattr(event, 'usage', None)
                model = getattr(event, 'model', '')

            # 构建基础信息（始终更新）
            self.last_chat_info = {
                "id": self.request_id,
                "model": model,
                "time": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            # 只有当 usage_data 存在且有效时才添加 usage 信息
            if usage_data:
                usage_dict = self._to_serializable(usage_data)
                if isinstance(usage_dict, dict):
                    # 将 usage 信息合并到 last_chat_info
                    self.last_chat_info.update(usage_dict)
                elif usage_dict:
                    # 如果不是字典但有值，作为单独字段存储
                    self.last_chat_info['usage_data'] = usage_dict

            return self.last_chat_info

        except Exception as e:
            self.completion_failed.emit(self.request_id, 'failed info update:' + str(e))
            # 即使出错也确保基础信息存在
            self.last_chat_info = {
                "id": self.request_id,
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "error": str(e)
            }
            return self.last_chat_info


    def _get_api_info(self, provider):
        """获取API信息（需要根据实际情况实现）"""
        return "", "", ''

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


class APIRequestHandler(FullFunctionRequestHandler):
    # 兼容旧版对外信号
    response_received = pyqtSignal(str)            # 接收到部分响应（正文）
    reasoning_response_received = pyqtSignal(str)  # 接收到部分推理内容（思考链）
    request_completed = pyqtSignal(str)            # 请求完成（完整正文）
    error_occurred = pyqtSignal(str)               # 请求出错

    def __init__(self, api_config={}, parent=None,enable_debug=False):
        """
        初始化API请求处理器（子类化 FullFunctionRequestHandler）
        :param api_config: API配置信息
        :param parent: 兼容参数（未使用）
        """
        super().__init__()
        # 兼容旧字段
        self.api_config = api_config or {}
        self.client = None
        self.current_thread = None
        self.response = None  # 占位，兼容旧属性
        self.model = None
        self.provider_type = "openai_compatible"

        # 复用父类状态
        self.full_response = ""
        self.think_response = ""

        # 桥接 FullFunctionRequestHandler 的信号到旧信号接口
        self.ai_event_response.connect(self._bridge_ai_event_response)
        self.think_event_signal.connect(self._bridge_think_event)
        self.request_finished.connect(self._bridge_request_finished)
        self.completion_failed.connect(self._bridge_error)

        if enable_debug:
            self.think_event_signal.connect(lambda _,t:print(t,end=''))
            self.ai_event_response.connect(lambda _,t:print(t,end=''))
            self.request_completed.connect(lambda _,t:print(t,end=''))
            self.completion_failed.connect(lambda _,t:print(t,end=''))
            self.error_occurred.connect(lambda _,t:print(t,end=''))
 

    def set_provider(self, provider, model, api_config=None):
        """
        设置API提供商和配置信息
        """
        try:
            api_key, url, provider_type = extract_api_info(provider, api_config)
        except ValueError as e:
            self.error_occurred.emit(f"API配置错误: {str(e)}")
            return
        if api_config:
            self.api_config = api_config
        self.base_url = (url or '').rstrip('/')
        self.api_key = api_key
        self.provider_type = provider_type
        self.model = model

    def send_request(self, message, model=''):
        """
        发送API请求（线程安全方式）
        :param message: 提示词（OpenAI Chat messages 数组或字符串）
        :param model: 使用的模型,若为空则使用 set_provider 设置的默认模型
        """
        target_model = model if model else self.model

        # 兼容 message 为字符串或 messages 数组
        if isinstance(message, str):
            messages_payload = [{"role": "user", "content": message}]
        else:
            messages_payload = message

        def _run():
            # 兜底：若未配置 provider，尝试 default
            if not getattr(self, 'base_url', None) or not getattr(self, 'api_key', None):
                try:
                    api_key, url, provider_type = extract_api_info('default', self.api_config)
                    self.base_url = (url or '').rstrip('/')
                    self.api_key = api_key
                    self.provider_type = provider_type
                except ValueError as e:
                    self.error_occurred.emit(f"API配置错误: {str(e)}")
                    return

            # 重置聚合态（与旧实现一致）
            self.full_response = ""
            self.think_response = ""

            params = {
                "model": target_model,
                "messages": messages_payload,
                "stream": True
            }
            try:
                # 直接使用父类的请求发送流程（流式/非流式、工具调用、思考链处理等）
                super(APIRequestHandler, self).send_request(params)
            except Exception as e:
                self.error_occurred.emit(f"API请求错误: {str(e)}")

        self.current_thread = threading.Thread(target=_run, daemon=True)
        self.current_thread.start()

    # -------------------------
    # 信号桥接
    # -------------------------
    def _bridge_ai_event_response(self, request_id: str, chunk: str):
        if chunk:
            self.response_received.emit(chunk)

    def _bridge_think_event(self, request_id: str, chunk: str):
        if chunk:
            self.reasoning_response_received.emit(chunk)

    def _bridge_request_finished(self, message_list):
        self.request_completed.emit(self.full_response or "")

    def _bridge_error(self, request_id: str, err: str):
        self.error_occurred.emit(err or "未知错误")
