from __future__ import annotations
import copy
from typing import TYPE_CHECKING

from core.session.data import ChatCompletionPack
from core.session.session_model import ChatMessage
from config import APP_SETTINGS

if TYPE_CHECKING:
    from service.web_search import WebSearchFacade


import time
from common import LOGMANAGER
from utils.str_tools import StrTools  
from service.chat_completion import GlobalPatcher

LOGGER = LOGMANAGER

class Preprocessor:
    """
    请求预处理器。
    
    负责将 ChatCompletionPack 转换为 API 请求参数。
    与 RequestWorkflowManager 分离，专注于数据转换逻辑。
    """
    
    def __init__(self,search_facade:"WebSearchFacade"):
        self.search_facade = search_facade
    
    def prepare_message(self, pack: ChatCompletionPack):
        """
        预处理消息并构建API参数。
        
        Args:
            pack: 包含对话历史、模型信息、API供应商及运行时选项的数据包
            
        Returns:
            (messages, params) 元组
        """


        start = time.perf_counter()
        
        # 1. 计算合适的轮数并获取原始数据
        raw_messages = self._get_raw_messages(pack, APP_SETTINGS.generation.max_message_rounds)
        
        # 2. 深复制原始消息，之后所有操作都在副本上进行
        messages = copy.deepcopy(raw_messages)
        
        # 3. 按顺序应用所有处理
        messages = self._handle_mod_functions(messages, pack)
        messages = self._fix_chat_history(messages, pack.chat_session.history)
        messages = self._process_special_styles(messages, pack)
        messages = self._handle_long_chat_placement(messages)
        messages = self._handle_user_and_char(messages, pack)
        messages = self._handle_multimodal_format(messages)
        messages = self._handle_web_search_results(messages, pack)
        messages = self._purge_message(messages)
        
        # 4. 构建请求参数
        has_tools = len(pack.tool_list) > 0
        params = self._build_request_params(
            messages, 
            pack, 
            stream=APP_SETTINGS.generation.stream_receive, 
            tools=has_tools
        )
        params = self._handle_provider_patch(params, pack)

        LOGGER.info(f'发送长度: {StrTools.get_chat_content_length(messages)}，消息数: {len(messages)}')
        LOGGER.info(f'消息打包耗时:{(time.perf_counter()-start)*1000:.2f}ms')
        
        return messages, params
    
    def _get_raw_messages(self, pack: ChatCompletionPack, max_rounds: int):
        """获取原始消息（不进行深复制）"""
        history = pack.chat_session.history
        if not history:
            return []
        if len(history) >= max_rounds and history[-(max_rounds-1):][0]["role"] == "system":
            max_rounds += 1
        
        start_index = max(1, len(history) - (max_rounds - 1))
        return [history[0]] + history[start_index:]
    
    def _handle_mod_functions(self, messages, pack: ChatCompletionPack):
        """处理mod函数"""
        for func in pack.mod:
            messages = func(messages)
        return messages
    
    def _purge_message(self, messages):
        """清理不需要的字段"""
        new_messages = []
        not_needed = ['info']
        
        for item in messages:
            temp_dict = {}
            for key, value in item.items():
                if key not in not_needed:
                    temp_dict[key] = value
            new_messages.append(temp_dict)
        return new_messages
    
    def _process_special_styles(self, messages, pack: ChatCompletionPack):
        """处理特殊样式文本和强制降重 - 改为User前插入System"""
        if not messages:
            return messages
        
        temp_style = pack.optional.get('temp_style', '')
        force_text = pack.optional.get('enforce_lower_repeat_text', '') if APP_SETTINGS.force_repeat.enabled else ''
        
        if not temp_style and not force_text:
            return messages
        
        if messages[-1]["role"] == "user":
            append_text = f'【{temp_style}|{force_text}】'
            new_system_msg = {"role": "system", "content": append_text}
            messages.insert(-1, new_system_msg)
        
        return messages
    
    def _handle_web_search_results(self, messages:list, pack: ChatCompletionPack):
        """处理网络搜索结果 - 改为User前插入System"""
        search_result = pack.optional.get('web_search_result', '')
        if search_result:
            if messages[-1]["role"] == "user":
                prompt_text = f"搜索引擎提供的结果:\n{search_result}\n请根据以上搜索结果回答用户的提问。"
                new_msg = {"role": "system", "content": prompt_text}
                messages.insert(-1, new_msg)
        
            return messages
        
        if not search_result and APP_SETTINGS.web_search.web_search_enabled:
            ct=pack.chat_session.history[-1]['content']
            if type(ct) == list:
                for item in ct:
                    if item['type'] == 'text':
                        query=item['text']
                        break
            elif type(ct) == str:
                query=ct

            web_cfg = APP_SETTINGS.web_search
            api_cfg = APP_SETTINGS.api
            
            # 确定是否使用 RAG
            use_rag = web_cfg.use_llm_reformat
            
            # 准备 RAG 参数
            rag_url = rag_key = rag_model = ""
            if use_rag:
                pack = web_cfg.reformat_config  # LLMUsagePack(provider/model)
                provider = api_cfg.providers.get(pack.provider)
                if not provider:
                    raise ValueError(f"Provider not found: {pack.provider}")
                
                rag_url = provider.url
                rag_key = provider.key
                rag_model = pack.model
            
            # 执行搜索
            result = self.search_facade.run(
                query=query,
                limit=web_cfg.search_results_num,
                use_rag=use_rag,
                rag_provider_url=rag_url,
                rag_provider_key=rag_key,
                rag_model=rag_model,
            )
            if result:
                prompt_text = f"搜索引擎提供的结果:\n{search_result}\n请根据以上搜索结果回答用户的提问。"
                new_msg = {"role": "system", "content": prompt_text}
                messages.insert(-1, new_msg)
        else:
            return messages

    def _fix_chat_history(self, messages: list, full_history: list):
        """修复被截断的聊天记录，保证工具调用的完整性"""
        if len(messages) > 1 and messages[1]['role'] != 'user':
            current_length = len(messages)
            cutten_len = len(full_history) - current_length
            
            if cutten_len > 0:
                for item in reversed(full_history[:cutten_len+1]):
                    if item['role'] != 'user':
                        messages.insert(1, copy.deepcopy(item))
                    elif item['role'] == 'user':
                        messages.insert(1, copy.deepcopy(item))
                        break
        return messages
    
    def _handle_long_chat_placement(self, messages:list[ChatMessage]):
        """处理长对话总结 (LCI) 的位置"""

        placement = APP_SETTINGS.lci.placement
        
        if placement == "对话第一位" and len(messages) >= 3:
            lci_msg = messages[1]
            next_msg = messages[2] # 获取下一条

            if lci_msg['role'] == 'system' and lci_msg.get('info', {}).get('lci'):
                # 合并内容
                next_msg['content'] = lci_msg['content'] + "\n" + next_msg['content']
                # 移除 LCI 消息
                messages.pop(1)

        return messages
    
    def _handle_user_and_char(self, messages:list[ChatMessage], pack: ChatCompletionPack):
        """处理用户和角色名称替换 & 为每条消息注入name字段"""
        if not messages:
            return messages

        names_config = pack.chat_session.name
        
        ai_name = names_config.get('assistant')
        if not ai_name:
            ai_name = APP_SETTINGS.names.ai if APP_SETTINGS.names.ai else pack.model
        
        user_name = names_config.get('user')
        if not user_name:
            user_name = APP_SETTINGS.names.user if APP_SETTINGS.names.user else 'user'
        
        for item in messages:
            role = item.get('role')
            if APP_SETTINGS.names.character_enforce:
                if role == 'user':
                    item['name'] = user_name
                elif role == 'assistant':
                    item['name'] = ai_name
            
            if role == 'system':
                content = item.get('content', '')
                if '{{user}}' in content:
                    content = content.replace('{{user}}', user_name)
                if '{{char}}' in content:
                    content = content.replace('{{char}}', ai_name)
                if '{{model}}' in content:
                    content = content.replace('{{model}}', pack.model)
                if '{{time}}' in content:
                    import time
                    content = content.replace('{{time}}', time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
                item['content'] = content
        
        return messages
    
    def _handle_multimodal_format(self, messages):
        """处理多模态格式 (将 info.multimodal 合并入 content)"""
        for single_message in messages:
            if 'info' in single_message and 'multimodal' in single_message['info']:
                text_content = single_message.get('content', '')
                text_message = [{"type": "text", "text": text_content}]
                multimodal_data = single_message['info']['multimodal']
                single_message['content'] = text_message + multimodal_data
        return messages
    
    def _handle_provider_patch(self, params, pack: ChatCompletionPack):
        """应用特定供应商的补丁"""

        provider_type = pack.provider.provider_type
        
        patcher = GlobalPatcher()
        config_context = {
            "reasoning_effort": APP_SETTINGS.generation.reasoning_effort,
            'provider_buildin_search_enabled': APP_SETTINGS.web_search.enable_provider_buildin,
            'input_ability': ['text', 'image', 'audio']
        }
        return patcher.patch(params, provider_type, config_context)
    
    def _build_request_params(self, messages, pack: ChatCompletionPack, stream=True, tools=False):
        """构建请求参数"""
        params = {
            'model': pack.model,
            'messages': messages,
            'stream': stream
        }
        
        gen_settings = APP_SETTINGS.generation
        
        if gen_settings.top_p_enable:
            params['top_p'] = float(gen_settings.top_p)
        if gen_settings.temperature_enable:
            params['temperature'] = float(gen_settings.temperature)
        if gen_settings.presence_penalty_enable:
            params['presence_penalty'] = float(gen_settings.presence_penalty)
        
        if gen_settings.thinking_enabled:
            params['enable_thinking'] = True
        
        if tools and pack.tool_list:
            params['tools'] = pack.tool_list
        
        return params
