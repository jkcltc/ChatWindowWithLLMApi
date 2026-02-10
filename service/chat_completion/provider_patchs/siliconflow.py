from ..patch_manager import register_provider
# 别忘了从隔壁把公共工具借过来
from .commons import filter_and_transform_content

@register_provider("siliconflow")
def patch_openai_compatible_logic(params, config):
    """
    siliconflow
    """
    im = config.get('log_manager')

    ability = config.get('input_ability', ['text', 'image', 'audio']) 

    # -------- 1. 多模态标准化 --------
    if 'messages' in params and isinstance(params['messages'], list):
        filter_and_transform_content(params['messages'], ability, "OpenAI_Compat", im)

    # -------- 2. Header --------
    extra_headers = params.get('extra_headers', {})
    extra_headers.update({
        'User-Agent': "ChatWindowWithLLMApi-CWLA",
        "HTTP-Referer": "https://github.com/jkcltc/ChatWindowWithLLMApi/",
        "X-Title": "ChatWindowWithLLMApi-CWLA",
    })
    params['extra_headers'] = extra_headers

    return params