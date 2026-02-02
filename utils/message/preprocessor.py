import copy
import time
import sys
from utils.message.data import ChatCompletionPack
from utils.setting import APP_SETTINGS,APP_RUNTIME
from utils.info_module import LOGMANAGER
LOGGER = LOGMANAGER

#from utils.message.data import ChatCompletionPack
# from utils.api.patcher import GlobalPatcher 
from utils.tools.str_tools import StrTools 

from utils.preset_data import LongChatImprovePersetVars

#发送消息前处理器的patch
class PreprocessorPatch:
    def __init__(self, god_class):
        self.god = god_class

    def prepare_patch(self):
        """预处理消息并构建API参数"""
        
        web_search_results = self._handle_web_search_results()
        enforce_lower_repeat_text = APP_RUNTIME.force_repeat.text 
        temp_style=self.god.temp_style

        pack=ChatCompletionPack(
            chathistory=self.god.chathistory,
            model=self.god.model_combobox.currentText(),
            provider = APP_SETTINGS.api.providers[self.god.api_var.currentText()],

            tool_list=self.god.function_manager.get_selected_functions(),
            
            optional = {
                "temp_style":temp_style,
                'web_search_result':web_search_results,
                'enforce_lower_repeat_text':enforce_lower_repeat_text,
            },

            mod=[self._handle_mod_functions],

        )
        return pack


    def _handle_web_search_results(self):
        user_input=self.god.chathistory[-1]['content']
        if isinstance(user_input,list):
            for item in user_input:
                if item['type']=='text':
                    user_input=item['text']
                    break
        if APP_SETTINGS.web_search.web_search_enabled:
            self.god.web_searcher.perform_search(user_input)
            self.god.web_searcher.wait_for_search_completion()
            if APP_SETTINGS.web_search.use_llm_reformat:
                results = self.god.web_searcher.rag_result
            else:
                results = self.god.web_searcher.tool.format_results()
            return results

    def _handle_mod_functions(self, messages):
        """处理模块功能"""
        messages = self._handle_status_manager(messages)
        messages = self._handle_story_creator(messages)
        return messages
    
    # mod functions
    def _handle_status_manager(self, messages):
        """
        处理状态管理器的上下文注入。
        如果启用了状态监控，将 simplified_variables 和 ai_variables 作为 system 消息
        插入到倒数第二条位置（用户最新消息之前）。
        """
        # 1. 基础检查：模块是否加载
        if "mods.status_monitor" not in sys.modules:
            return messages

        # 2. 基础检查：功能是否开启
        if not self.god.mod_configer.status_monitor_enable_box.isChecked():
            return messages

        # 获取监视器实例
        monitor = self.god.mod_configer.status_monitor

        # 3. 收集要插入的上下文消息
        context_messages = []

        # --- 提取状态文本 ---
        status_text = monitor.get_simplified_variables()
        if status_text and status_text.strip():
            context_messages.append({
                "role": "system",
                "content": status_text
            })

        # --- 提取AI变量/函数 ---
        ai_funcs_text = monitor.get_ai_variables(use_str=True)
        if ai_funcs_text and ai_funcs_text.strip():
            context_messages.append({
                "role": "system",
                "content": ai_funcs_text
            })

        # 4. 执行插入操作
        # 如果没有上下文要插，就直接返回原样
        if not context_messages:
            return messages


        messages[-1:-1] = context_messages
        return messages


    def _handle_story_creator(self, messages):
        """处理故事创建器"""
        if not "mods.story_creator" in sys.modules:
            LOGGER.info('no mods.story_creator')
            return messages
        if not self.god.mod_configer.enable_story_insert.isChecked():
            return messages
        return self.god.mod_configer.story_creator.process_income_chat_history(messages)


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
        messages = self._handle_mod_functions(messages,pack)
        messages = self._fix_chat_history(messages, pack.chathistory)
        messages = self._handle_web_search_results(messages, pack)
        messages = self._process_special_styles(messages, pack)
        messages = self._handle_long_chat_placement(messages)
        messages = self._handle_user_and_char(messages, pack)
        messages = self._handle_multimodal_format(messages)

        messages = self._purge_message(messages)

        # 4. 构建请求参数
        # tools=True/False 的判断逻辑通常由上层决定传入 pack.tool_list 是否为空
        has_tools = len(pack.tool_list) > 0
        params = self._build_request_params(
            messages, 
            pack, 
            stream=APP_SETTINGS.
            generation.stream_receive, 
            tools=has_tools
        )
        params = self._handle_provider_patch(params, pack)

        print(params)

        LOGGER.info(f'发送长度: {StrTools.get_chat_content_length(messages)}，消息数: {len(messages)}')
        LOGGER.info(f'消息打包耗时:{(time.perf_counter()-start)*1000:.2f}ms')
        return messages, params

    def _handle_mod_functions(self, messages, pack: ChatCompletionPack):
        """处理mod函数"""
        for func in pack.mod:
            messages = func(messages)
        return messages
    
    def _get_raw_messages(self, pack: ChatCompletionPack, max_rounds: int):
        """获取原始消息（不进行深复制）"""
        history = pack.chathistory
        if not history:
            return []
        if len(history) >= max_rounds and history[-(max_rounds-1):][0]["role"] == "system":
            max_rounds += 1

        start_index = max(1, len(history) - (max_rounds - 1))

        return [history[0]] + history[start_index:]

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
        """处理特殊样式文本和强制降重 - 改为User前插入System"""
        if not messages:
            return messages

        temp_style = pack.optional.get('temp_style', '')
        force_text = pack.optional.get('enforce_lower_repeat_text', '') if APP_SETTINGS.force_repeat.enabled else ''

        # 如两个变量都空，直接返回
        if not temp_style and not force_text:
            return messages

        # 仅当最后一条是 user 时，在其前方插入系统提示
        if messages[-1]["role"] == "user":
            append_text = f'【{temp_style}|{force_text}】'

            # 构造要插入的系统消息
            new_system_msg = {"role": "system", "content": append_text}
            messages.insert(-1, new_system_msg)

        return messages

    def _handle_web_search_results(self, messages, pack: ChatCompletionPack):
        """处理网络搜索结果 - 改为User前插入System"""
        search_result = pack.optional.get('web_search_result', '')

        # 如果搜索结果为空或消息列表为空，直接返回原消息列表
        if APP_SETTINGS.web_search.web_search_enabled and search_result and messages:

            if messages[-1]["role"] == "user":
                prompt_text = f"搜索引擎提供的结果:\n{search_result}\n请根据以上搜索结果回答用户的提问。"

                new_msg = {"role": "system", "content": prompt_text}

                messages.insert(-1, new_msg)

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
        """处理用户和角色名称替换 & 为每条消息注入name字段"""
        if not messages:
            return messages

        # 1. 获取用户和角色名称 
        first_msg_info = messages[0].get("info", {}) if isinstance(messages[0], dict) else {}
        names_config = first_msg_info.get("name", {})

        # 获取AI名字
        ai_name = names_config.get('assistant')
        if not ai_name:
            ai_name = APP_SETTINGS.names.ai if APP_SETTINGS.names.ai else pack.model

        # 获取用户名字
        user_name = names_config.get('user')
        if not user_name:
            user_name = APP_SETTINGS.names.user if APP_SETTINGS.names.user else 'user'

        # 2. 遍历所有消息，该贴标签的贴标签，该换内容的换内容
        for item in messages:
            role = item.get('role')
            if APP_SETTINGS.generation.character_enforce:
                # 给 User 和 Assistant 注入 name 字段
                if role == 'user':
                    item['name'] = user_name
                elif role == 'assistant':
                    item['name'] = ai_name

            # 3. 针对 System 消息进行模板变量替换
            if role == 'system':
                content = item.get('content', '')
                if '{{user}}' in content:
                    content = content.replace('{{user}}', user_name)
                if '{{char}}' in content:
                    content = content.replace('{{char}}', ai_name)
                if '{{model}}' in content:
                    content = content.replace('{{model}}', pack.model)
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

    #class ProviderConfig(BaseSettings):
    #   """单个供应商的配置结构"""
    #   url: str = ""
    #   key: str = ""
    #   models: List[str] = Field(default_factory=list)
    #   provider_type : str = "openai_compatible"

    def _handle_provider_patch(self, params, pack: ChatCompletionPack):
        """应用特定供应商的补丁"""
        # 从配置中通过 provider key 获取 URL
        provider_type=pack.provider.provider_type

        # 需要引入 GlobalPatcher
        from utils.tools.patch_manager import GlobalPatcher # 延迟导入避免循环依赖

        patcher = GlobalPatcher()
        config_context = {
            "reasoning_effort": APP_SETTINGS.generation.reasoning_effort,
            'provider_buildin_search_enabled': APP_SETTINGS.web_search.enable_provider_buildin,
            # 占位符 等待设置重构
            'input_ability':['text','image','audio']
        }
        new_params = patcher.patch(params, provider_type, config_context)
        return new_params

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

        # 思考功能
        if gen_settings.thinking_enabled:
            params['enable_thinking'] = True

        # 工具调用
        if tools and pack.tool_list:
            params['tools'] = pack.tool_list

        return params
