from ..patch_manager import register_provider
from .commons import filter_and_transform_content

# =================================================================
#  4. Baidu (Qianfan)
# =================================================================
@register_provider("baidu")
def patch_baidu_logic(params, config):
    im = config.get('log_manager')
    ability = config.get('input_ability', ['text'])

    # 1. Thinking 参数平铺
    if 'enable_thinking' in params:
        params['enable_thinking'] = bool(params['enable_thinking'])

    if effort := config.get('reasoning_effort'):
        effort_map = {1: "low", 2: "medium", 3: "high"}
        if effort in effort_map:
            params['reasoning_effort'] = effort_map[effort]

    # 2. 联网搜索 (适配新字段 provider_buildin_search_enabled)
    if config.get('provider_buildin_search_enabled', False):
        params['web_search'] = {
            "enable": True,
            "search_mode": "auto",
            "enable_citation": True
        }

    # 3. 内容清洗
    if 'messages' in params and isinstance(params['messages'], list):
        filter_and_transform_content(params['messages'], ability, "Baidu", im)

        # 百度特供：如果清洗后发现只剩文本且原本是 list，尽量转为纯 string
        # 避免某些旧模型报错 336003
        for msg in params['messages']:
            content = msg.get('content')
            if isinstance(content, list):
                # 简单判断：如果全是 text 类型，就拼起来
                is_all_text = all(item.get('type') == 'text' for item in content)
                if is_all_text:
                    full_text = "".join([item.get('text', '') for item in content])
                    msg['content'] = full_text if full_text.strip() else "..."

    # 4. Header
    extra_headers = params.get('extra_headers', {})
    extra_headers.update({
        'User-Agent': "ChatWindowWithLLMApi-CWLA",
        "HTTP-Referer": "https://github.com/jkcltc/ChatWindowWithLLMApi/",
        "X-Title": "ChatWindowWithLLMApi-CWLA",
    })
    params['extra_headers'] = extra_headers
    return params
