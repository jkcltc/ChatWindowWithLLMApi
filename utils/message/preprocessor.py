from CWLA_main import MainWindow#临时用来反查这tm到底引用了哪个支持服务

import time,copy,sys
from utils.info_module import LOGMANAGER
from utils.tools.str_tools import StrTools
from utils.tools.patch_manager import GlobalPatcher

LOGGER=LOGMANAGER

class MessagePreprocessor:
    def __init__(self, god_class):
        self.god:MainWindow = god_class
        self.stream = True

    def prepare_message(self, tools=False):
        """预处理消息并构建API参数"""
        start = time.perf_counter()
        
        # 1. 在最开始获取原始数据并深复制一次
        better_round = self._calculate_better_round()
        raw_messages = self._get_raw_messages(better_round)
        
        # 2. 深复制原始消息，之后所有操作都在副本上进行
        messages = copy.deepcopy(raw_messages)

        # 3. 按顺序应用所有处理，都操作深复制后的 messages
        messages = self._fix_chat_history(messages)
        messages = self._handle_web_search_results(messages)
        messages = self._process_special_styles(messages)
        messages = self._handle_long_chat_placement(messages)
        messages = self._handle_user_and_char(messages)
        messages = self._handle_multimodal_format(messages)
        messages = self._handle_mod_functions(messages)
        messages = self._purge_message(messages)
        
        # 4. 构建请求参数
        params = self._build_request_params(messages, stream=self.stream, tools=tools)
        params = self._handle_provider_patch(params)

        LOGGER.info(f'发送长度: {StrTools.get_chat_content_length(messages)}，消息数: {len(messages)}')
        LOGGER.info(f'消息打包耗时:{(time.perf_counter()-start)*1000:.2f}ms')
        return messages, params

    def _get_raw_messages(self, better_round):
        """获取原始消息（不进行深复制）"""
        history = self.god.chathistory
        if history[-(better_round-1):][0]["role"] == "system":
            better_round += 1
        return [history[0]] + history[-(better_round-1):]

    def _calculate_better_round(self):
        """计算合适的消息轮数"""
        history = self.god.chathistory
        if (len(str(history[-(self._fix_max_rounds()-1):])) - len(str(history[0]))) < 1000:
            return self._fix_max_rounds(False, 2*self._fix_max_rounds())
        return self._fix_max_rounds() - 1

    def _fix_max_rounds(self, max_round_bool=True, max_round=None):
        if max_round_bool:
            return min(self.god.max_message_rounds, len(self.god.chathistory))
        else:
            return min(max_round, len(self.god.chathistory))

    def _purge_message(self, messages):
        """清理不需要的字段（操作深复制后的消息）"""
        new_messages = []
        not_needed = ['info']  # 'reasoning_content'
        
        for item in messages:
            temp_dict = {}
            for key, value in item.items():
                if key not in not_needed:
                    temp_dict[key] = value
            new_messages.append(temp_dict)
        return new_messages

    def _process_special_styles(self, messages):
        """处理特殊样式文本（操作深复制后的消息）"""
        if (self.god.chathistory[-1]["role"] == "user" and self.god.temp_style != '') \
            or self.god.enforce_lower_repeat_text != '':
            append_text = f'【{self.god.temp_style}{self.god.enforce_lower_repeat_text}】'
            messages[-1]["content"] = append_text + messages[-1]["content"]
        return messages

    def _handle_web_search_results(self, messages):
        """处理网络搜索结果（操作深复制后的消息）"""
        if self.god.web_search_enabled:
            self.god.web_searcher.wait_for_search_completion()
            if self.god.web_searcher.rag_checkbox.isChecked():
                results = self.god.web_searcher.rag_result
            else:
                results = self.god.web_searcher.tool.format_results()
            messages[-1]["content"] += "\n[system]搜索引擎提供的结果:\n" + results
        return messages

    def _fix_chat_history(self, messages:list):
        """
        修复被截断的聊天记录，保证工具调用的完整性
        （注意：这个方法会插入消息，插入时需要深复制）
        """
        # 仅当第二条消息不是用户时触发修复（第一条是system）
        if len(messages) > 1 and messages[1]['role'] != 'user':  
            full_history = self.god.chathistory
            current_length = len(messages)
            cutten_len = len(full_history) - current_length
            
            if cutten_len > 0:
                # 反向遍历缺失的消息，插入时需要深复制
                for item in reversed(full_history[:cutten_len+1]):
                    if item['role'] != 'user':
                        messages.insert(1, copy.deepcopy(item))
                    if item['role'] == 'user':
                        messages.insert(1, copy.deepcopy(item))
                        break
        return messages

    def _handle_long_chat_placement(self, messages):
        """处理长对话位置"""
        if self.god.long_chat_placement == "对话第一位":
            if len(messages) >= 2 and "**已发生事件和当前人物形象**" in messages[0]["content"]:
                try:
                    header, history_part = messages[0]["content"].split(
                        "**已发生事件和当前人物形象**", 1)
                    messages[0]["content"] = header.strip()
                    if history_part.strip():
                        messages[1]["content"] = f"{messages[1]['content']}\n{history_part.strip()}"
                except ValueError:
                    pass
        return messages

    def _handle_user_and_char(self, messages):
        """处理用户和角色名称"""
        if not self.god.name_ai:
            ai_name = self.god.model_combobox.currentText()
        else:
            ai_name = self.god.name_ai
            
        if not self.god.name_user:
            user_name = 'user'
        else:
            user_name = self.god.name_user
            
        item = messages[0]
        if item['role'] == 'system':
            if '{{user}}' in item['content']:
                item['content'] = item['content'].replace('{{user}}', user_name)
            if '{{char}}' in item["content"]:
                item['content'] = item['content'].replace('{{char}}', ai_name)
            if '{{model}}' in item['content']:
                item['content'] = item['content'].replace('{{model}}', self.god.model_combobox.currentText())
            if '{{time}}' in item["content"]:
                item['content'] = item['content'].replace('{{time}}', time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
        return messages

    def _handle_mod_functions(self, messages):
        """处理模块功能"""
        messages = self._handle_status_manager(messages)
        messages = self._handle_story_creator(messages)
        return messages
    
    # mod functions
    def _handle_status_manager(self, messages):
        """处理状态管理器"""
        if not "mods.status_monitor" in sys.modules:
            return messages
        if not self.god.mod_configer.status_monitor_enable_box.isChecked():
            return messages
        
        text = messages[-1]['content']
        status_text = self.god.mod_configer.status_monitor.get_simplified_variables()
        use_ai_func = self.god.mod_configer.status_monitor.get_ai_variables(use_str=True)
        text = status_text + use_ai_func + text
        messages[-1]['content'] = text
        return messages
    
    def _handle_story_creator(self, messages):
        """处理故事创建器"""
        if not "mods.story_creator" in sys.modules:
            LOGGER.info('no mods.story_creator')
            return messages
        if not self.god.mod_configer.enable_story_insert.isChecked():
            return messages
        return self.god.mod_configer.story_creator.process_income_chat_history(messages)

    # 0.25.3 enable_thinking
    def _handle_provider_patch(self, params):
        # url作为判断供应商的标识
        url_text = self.god.api_var.currentText()
        provider_url = self.god.api[url_text][0]

        patcher = GlobalPatcher()
        config_context = {
            "reasoning_effort": self.god.reasoning_effort,
        }
        new_params = patcher.patch(params, provider_url, config_context)
        return new_params

    def _build_request_params(self, messages, stream=True, tools=False):
        """构建请求参数（含Function Call支持）"""
        params = {
            'model': self.god.model_combobox.currentText(),
            'messages': messages,
            'stream': stream
        }
        
        # 添加现有参数
        if self.god.top_p_enable:
            params['top_p'] = float(self.god.top_p)
        if self.god.temperature_enable:
            params['temperature'] = float(self.god.temperature)
        if self.god.presence_penalty_enable:
            params['presence_penalty'] = float(self.god.presence_penalty)
        
        # 打开思考功能
        if self.god.thinking_enabled:
            params['enable_thinking'] = True

        function_definitions = []
        manager = self.god.function_manager
        function_definitions = manager.get_selected_functions()
        if function_definitions:
            params['tools'] = function_definitions
        return params

     # 0.25.4 multimodal
    def _handle_multimodal_format(self, messages):
        """处理多模态格式"""
        for single_message in messages:
            if 'multimodal' in single_message['info']:
                text_message = [
                        {
                            "type": "text",
                            "text": single_message['content']
                        }
                    ]
                multimodal_message = single_message['info']['multimodal']
                single_message['content'] = text_message + multimodal_message
        return messages