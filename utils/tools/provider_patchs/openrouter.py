from utils.tools.patch_manager import register_provider
from .commons import filter_and_transform_content

@register_provider("openrouter")
def patch_openrouter_logic(params, config):
    """
    OpenRouter Patch
    功能：
    1. 多模态格式整形 (Audio URL -> Input Audio)
    2. Thinking 字段映射
    3. Web Search (Plugins 注入)
    4. 请求头注入
    """
    im = config.get('log_manager')
    ability = config.get('input_ability', ['text', 'image', 'audio'])

    # -------- 1. Thinking 逻辑 --------
    if 'enable_thinking' in params:
        is_thinking = params.pop('enable_thinking', False)
        params["reasoning"] = { "exclude": False, "enabled": is_thinking }
        if is_thinking and (effort := config.get('reasoning_effort')):
            effort_map = {1: "low", 2: "medium", 3: "high"}
            if effort in effort_map:
                params["reasoning"]["effort"] = effort_map[effort]

    # -------- 2. Web Search (新增) --------
    if config.get('provider_buildin_search_enabled', False):
        # 检查是否已经有 plugins 字段（虽然通常没有）
        plugins = params.get('plugins', [])

        # 防止重复添加
        if not any(p.get('id') == 'web' for p in plugins):
            # 默认配置：不指定 engine
            # max_results 默认为 5 
            plugins.append({
                "id": "web"
            })
            if im:
                im.log("[OpenRouter] 已注入 Web Search 插件", level="debug")

        params['plugins'] = plugins

    # -------- 3. 多模态清洗 --------
    if 'messages' in params and isinstance(params['messages'], list):
        filter_and_transform_content(params['messages'], ability, "OpenRouter", im)

    # -------- 4. Header 注入 --------
    extra_headers = params.get('extra_headers', {})
    extra_headers.update({
        "HTTP-Referer": "https://github.com/jkcltc/ChatWindowWithLLMApi/",
        "X-Title": "ChatWindowWithLLMApi-CWLA",
    })
    params['extra_headers'] = extra_headers

    return params