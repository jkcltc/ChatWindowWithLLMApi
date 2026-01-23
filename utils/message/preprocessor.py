import copy
import time
import sys
import logging
from typing import List, Dict, Any ,Optional ,Callable

from utils.setting.data import APP_SETTINGS
#from utils.message.data import ChatCompletionPack
# from utils.api.patcher import GlobalPatcher 
from utils.tools.str_tools import StrTools 
from dataclasses import dataclass ,field
from utils.preset_data import LongChatImprovePersetVars

def _identity(x):
    return x
@dataclass
class ChatCompletionPack:
    """
    用于在不同组件间传递对话请求所需的完整上下文包。
    """
    chathistory: List[Dict[str, Any]]

    model_name: str

    api_provider: str

    tool_list: List[str] = field(default_factory=list)
    """function_manager.selected_tools=>list"""

    optional:dict = field(default_factory={
        "temp_style":'',
        'web_search_result':'',
        'enforce_lower_repeat_text':'',
    })

    mod: Optional[Callable] = field(default=_identity) 

from utils.info_module import LOGMANAGER
LOGGER = LOGMANAGER

class MessagePreprocessor:
    def __init__(self):
        pass

    def prepare_message(self, pack: ChatCompletionPack):
        """
        预处理消息并构建API参数
        Args:
            pack: 包含对话历史、模型信息、API供应商及运行时选项的数据包
        """
        start = time.perf_counter()

        # 1. 计算合适的轮数并获取原始数据
        raw_messages = self._get_raw_messages(pack, APP_SETTINGS.generation.max_message_rounds)

        # 2. 深复制原始消息，之后所有操作都在副本上进行
        messages = copy.deepcopy(raw_messages)

        # 3. 按顺序应用所有处理
        messages = self._fix_chat_history(messages, pack.chathistory)
        messages = self._handle_web_search_results(messages, pack)
        messages = self._process_special_styles(messages, pack)
        messages = self._handle_long_chat_placement(messages)
        messages = self._handle_user_and_char(messages, pack)
        messages = self._handle_multimodal_format(messages)

        messages = pack(messages) 

        messages = self._purge_message(messages)

        # 4. 构建请求参数
        # tools=True/False 的判断逻辑通常由上层决定传入 pack.tool_list 是否为空
        has_tools = len(pack.tool_list) > 0
        params = self._build_request_params(messages, pack, stream=APP_SETTINGS.generation.stream_receive, tools=has_tools)
        params = self._handle_provider_patch(params, pack)

        LOGGER.info(f'发送长度: {StrTools.get_chat_content_length(messages)}，消息数: {len(messages)}')
        LOGGER.info(f'消息打包耗时:{(time.perf_counter()-start)*1000:.2f}ms')
        return messages, params

    def _get_raw_messages(self, pack: ChatCompletionPack, max_rounds: int):
        """获取原始消息（不进行深复制）"""
        history = pack.chathistory
        if not history:
            return []
        if len(history) >= max_rounds and history[-(max_rounds-1):][0]["role"] == "system":
            max_rounds += 1

        # 始终包含第一条 (System Prompt) + 最近的 N 条
        return [history[0]] + history[-(max_rounds-1):]

    def _purge_message(self, messages):
        """清理不需要的字段"""
        new_messages = []
        # 'reasoning_content' 有时需要保留取决于下游，这里沿用原逻辑清除 'info'
        not_needed = ['info'] 

        for item in messages:
            temp_dict = {}
            for key, value in item.items():
                if key not in not_needed:
                    temp_dict[key] = value
            new_messages.append(temp_dict)
        return new_messages

    def _process_special_styles(self, messages, pack: ChatCompletionPack):
        """处理特殊样式文本和强制降重"""
        if not messages:
            return messages

        temp_style = pack.optional.get('temp_style', '')
        force_text = pack.optional.get('enforce_lower_repeat_text','') if APP_SETTINGS.force_repeat.enforce_lower_repeat_var else ''

        # 仅当最后一条是 user 且有样式或强制文本时追加
        if (messages[-1]["role"] == "user" and temp_style) or force_text:
            append_text = f'【{temp_style}|{force_text}】'
            messages[-1]["content"] = append_text + messages[-1]["content"]

        return messages

    def _handle_web_search_results(self, messages, pack: ChatCompletionPack):
        """处理网络搜索结果"""

        search_result = pack.optional.get('web_search_result', '')

        if APP_SETTINGS.web_search.web_search_enabled and search_result and messages:
            messages[-1]["content"] = "[system]搜索引擎提供的结果:\n" + search_result + "现在，根据搜索引擎提供的结果回答用户的以下问题：" + messages[-1]["content"]

        return messages

    def _fix_chat_history(self, messages: list, full_history: list):
        """
        修复被截断的聊天记录，保证工具调用的完整性
        """
        if len(messages) > 1 and messages[1]['role'] != 'user':
            current_length = len(messages)
            cutten_len = len(full_history) - current_length

            if cutten_len > 0:
                # 反向遍历缺失的消息，插入时需要深复制
                for item in reversed(full_history[:cutten_len+1]):
                    # 如果遇到非 User 消息 (Assistant/Tool)，插入
                    if item['role'] != 'user':
                        messages.insert(1, copy.deepcopy(item))
                    # 遇到 User 消息停止，保证对话连贯性
                    if item['role'] == 'user':
                        messages.insert(1, copy.deepcopy(item))
                        break
        return messages

    def _handle_long_chat_placement(self, messages):
        """处理长对话总结 (LCI) 的位置"""
        placement = APP_SETTINGS.lci.placement

        if placement == "对话第一位" and len(messages) >= 2:
            content = messages[0].get("content", "")
            marker = LongChatImprovePersetVars.before_last_summary

            if marker in content:
                try:
                    header, history_part = content.split(marker, 1)
                    messages[0]["content"] = header.strip()
                    if history_part.strip():
                        messages[1]["content"] = f"{messages[1]['content']}\n{history_part.strip()}"
                except ValueError:
                    pass
        return messages

    def _handle_user_and_char(self, messages, pack: ChatCompletionPack):
        """处理用户和角色名称替换"""
        if not messages:
            return messages
        
        item = messages[0]
        # 优先使用配置名，否则回退
        ai_name=item ["info"]["name"]['assistant']
        if not ai_name:
            ai_name = APP_SETTINGS.names.ai if APP_SETTINGS.names.ai else pack.model_name
        user_name=item ["info"]["name"]['user']
        if not user_name:
            user_name = APP_SETTINGS.names.user if APP_SETTINGS.names.user else 'user'

        if item['role'] == 'system':
            content = item.get('content', '')
            if '{{user}}' in content:
                content = content.replace('{{user}}', user_name)
            if '{{char}}' in content:
                content = content.replace('{{char}}', ai_name)
            if '{{model}}' in content:
                content = content.replace('{{model}}', pack.model_name)
            if '{{time}}' in content:
                content = content.replace('{{time}}', time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
            item['content'] = content

        return messages

    def _handle_multimodal_format(self, messages):
        """处理多模态格式 (将 info.multimodal 合并入 content)"""
        for single_message in messages:
            if 'info' in single_message and 'multimodal' in single_message['info']:
                text_content = single_message.get('content', '')
                text_message = [
                        {
                            "type": "text",
                            "text": text_content
                        }
                    ]
                multimodal_data = single_message['info']['multimodal']
                single_message['content'] = text_message + multimodal_data
        return messages

    def _handle_provider_patch(self, params, pack: ChatCompletionPack):
        """应用特定供应商的补丁"""
        # 从配置中通过 provider key 获取 URL
        provider_config = APP_SETTINGS.api.providers.get(pack.api_provider)
        provider_url = provider_config.url if provider_config else ""

        # 需要引入 GlobalPatcher
        from utils.tools.patch_manager import GlobalPatcher # 延迟导入避免循环依赖

        patcher = GlobalPatcher()
        config_context = {
            "reasoning_effort": APP_SETTINGS.generation.reasoning_effort,
        }
        new_params = patcher.patch(params, provider_url, config_context)
        return new_params

    def _build_request_params(self, messages, pack: ChatCompletionPack, stream=True, tools=False):
        """构建请求参数"""
        params = {
            'model': pack.model_name,
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

        # 思考功能
        if gen_settings.thinking_enabled:
            params['enable_thinking'] = True

        # 工具调用
        if tools and pack.tool_list:
            params['tools'] = pack.tool_list

        return params
