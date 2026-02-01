import re

MEDIA_TYPES = {'image_url', 'image', 'input_audio', 'audio', 'video'}
#字符串处理工具
class StrTools:
    def _for_replace(text, replace_from, replace_to):
        """批量替换字符串，处理长度不匹配的情况"""
        replace_from_list = replace_from.split(';')
        replace_to_list = replace_to.split(';')
        
        # 调整 replace_to_list 的长度以匹配 replace_from_list
        replace_from_len = len(replace_from_list)
        # 截取 replace_to_list 的前 replace_from_len 个元素，不足部分补空字符串
        adjusted_replace_to = replace_to_list[:replace_from_len]  # 截断或保留全部
        # 补足空字符串直到长度等于 replace_from_len
        adjusted_replace_to += [''] * (replace_from_len - len(adjusted_replace_to))
        
        # 执行替换
        for i in range(replace_from_len):
            text = text.replace(replace_from_list[i], adjusted_replace_to[i])
        return text
    
    def _re_replace(text, replace_from, replace_to):
        """
        使用正则表达式替换文本中的内容。
        
        参数:
        - text: 原始字符串
        - replace_from: 由分号(";")分隔的正则表达式字符串
        - replace_to: 由分号(";")分隔的替换字符串
        
        返回:
        - 替换后的字符串
        """
        # 将 replace_from 和 replace_to 按分号分割成列表
        replace_from_list = replace_from.split(';')
        replace_to_list = replace_to.split(';')
        
        # 遍历 replace_from_list，根据规则替换
        for i, pattern in enumerate(replace_from_list):
            # 获取对应的替换字符串，如果 replace_to_list 长度不足，则使用空字符串
            replacement = replace_to_list[i] if i < len(replace_to_list) else ''
            # 使用 re.sub 进行替换
            text = re.sub(pattern, replacement, text)
        
        return text


    @staticmethod
    def vast_replace(text, replace_from, replace_to):
        """
        批量替换字符串，支持正则表达式和普通字符串替换。
        - text: 原始字符串,如果以 're:' 开头，则使用正则表达式替换
        - replace_from: 由分号(";")分隔的替换源字符串
        - replace_to: 由分号(";")分隔的替换目标字符串

        - 返回: 替换后的字符串
        """
        if replace_from.startswith('re:#'):
            # 如果以 're:#' 开头，则使用正则表达式替换
            text = StrTools._re_replace(text, replace_from[4:], replace_to)
        else:
            # 否则使用普通字符串替换
            text = StrTools._for_replace(text, replace_from, replace_to)
        
        return text
    
    @staticmethod
    def special_block_handler(obj,content,                      #incoming content
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
                if hasattr(obj, extra_params):
                    setattr(obj, extra_params, content)
            signal(request_id,content)
            return {"starter":True,"ender":False}
        return {"starter":False,"ender":False}

    @staticmethod
    def debug_chathistory(dic_chathistory,action='easy',LOGGER=None):
        """调试聊天记录"""
        actual_length = 0

        for i, message in enumerate(dic_chathistory):
            if action!='easy':
                LOGGER.info(f"对话 {i}:")
                LOGGER.info(f"Role: {message['role']}")
                LOGGER.info("-" * 20)
                LOGGER.info(f"Content: {message['content']}")
                LOGGER.info("-" * 20)
            
                # 新增工具调用打印逻辑
                if message['role'] == 'assistant' and 'tool_calls' in message:
                    LOGGER.info("工具调用列表：")
                    for j, tool_call in enumerate(message['tool_calls']):
                        func_info = tool_call.get('function', {})
                        name = func_info.get('name', '未知工具')
                        args = func_info.get('arguments', {})
                        LOGGER.info(f"  工具 {j+1}: {name}")
                        LOGGER.info(f"  参数: {args}, 类型: {type(args)}")
                        LOGGER.info("-" * 20)
                    actual_length += len(args)
                
                if message['content']:
                    actual_length += len(message['content'])

        LOGGER.info(f"实际长度: {actual_length}")
        LOGGER.info(f"实际对话轮数: {len(dic_chathistory)}")
        LOGGER.info(f"系统提示长度: {len(dic_chathistory[0]['content'])}")
        LOGGER.info("-" * 20)

        return {
            "actual_length": actual_length,
            "actual_rounds": len(dic_chathistory),
            "total_length": len(dic_chathistory),
            "system_prompt_length": len(dic_chathistory[0]['content'])
        }

    @staticmethod
    def remove_var(text):
        pattern = r'变量组开始.*?变量组结束'
        match = re.search(pattern, text, flags=re.DOTALL)
        if match:
            return text.replace(match.group(0),'')
        return text

    @staticmethod
    def combined_remove_var_vast_replace(content=None,setting=None,mod_enabled=False):
        if not setting or content:
            return content

        actual_response=content
        if setting.autoreplace_var:
            actual_response = StrTools.vast_replace(actual_response,setting.autoreplace_from,setting.autoreplace_to)
        if mod_enabled:
            actual_response = StrTools.remove_var(actual_response)
        return actual_response


    @staticmethod
    def get_chat_content_length(messages):
        target_types_set = MEDIA_TYPES
        _len = len
        _str = str

        total = 0

        for message in messages:

            content = message.get('content')
            if not content:
                continue

            # 快速类型检查
            if type(content) is str:
                total += _len(content)
                continue

            for item in content:
                try:
                    item_type = item['type']

                    if item_type == 'text':
                        total += _len(item['text'])

                    elif item_type in target_types_set:
                        total += 1000

                    else:
                        total += _len(_str(item))
                except KeyError:
                    total += _len(_str(item))

        return total