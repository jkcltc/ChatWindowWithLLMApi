from ..patch_manager import register_provider
from .commons import filter_and_transform_content

@register_provider("deepseek")
def patch_deepseek_logic(params, config):
    """
    DeepSeek Patch (Refreshed & Polite)
    功能：
    1. 移除 enable_thinking
    2. 多模态拦截通知 
    3. 多模态清洗
    4. 请求头注入
    """
    im = config.get('log_manager')

    # 截至 DeepSeek V3.2 只有 text，强制抛掉
    ability = ['text']

    # -------- 1. Thinking 逻辑处理 --------
    if 'enable_thinking' in params:
        params.pop('enable_thinking', None)

    # -------- 2. 多模态拦截预处理 --------
    if 'messages' in params and isinstance(params['messages'], list):
        new_messages = []
        forbidden_types = ['image_url', 'audio_url', 'input_audio']

        for msg in params['messages']:
            has_forbidden = False
            content = msg.get('content')

            # 只有当 content 是 list 时才需要检查
            if isinstance(content, list):
                for item in content:
                    if item.get('type') in forbidden_types:
                        has_forbidden = True
                        break

            # 如果有被禁止的类型，先在前面插一条 System Message
            if has_forbidden:
                warning_text = "[multimodal intercept]The appearance of this message indicates that the user has sent multimodal data that the current model does not support.You should inform the user that you are unable to read the content."
                new_messages.append({
                    "role": "system",
                    "content": warning_text
                })

            # 把原始消息放进去（等着后面被清洗）
            new_messages.append(msg)

        # 替换回原来的列表
        params['messages'] = new_messages

    # -------- 3. 多模态清洗 --------
    if 'messages' in params and isinstance(params['messages'], list):
        filter_and_transform_content(params['messages'], ability, "DeepSeek", im)

    # -------- 4. Header 注入 --------
    extra_headers = params.get('extra_headers', {})
    extra_headers.update({
        'User-Agent': "ChatWindowWithLLMApi-CWLA",
        "HTTP-Referer": "https://github.com/jkcltc/ChatWindowWithLLMApi/",
        "X-Title": "ChatWindowWithLLMApi-CWLA",
    })
    params['extra_headers'] = extra_headers

    return params