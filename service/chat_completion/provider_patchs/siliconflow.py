from ..patch_manager import register_provider
# 别忘了从隔壁把公共工具借过来
from .commons import filter_and_transform_content

@register_provider("siliconflow")
def patch_openai_compatible_logic(params, config:dict):
    """
    siliconflow
    """
    im = config.get('log_manager')

    ability = config.get('input_ability', ['text', 'image', 'audio']) 

    reasoning= config.get('reasoning_effort',0)

    # -------- 1. 多模态标准化 --------
    # 硅基流动需要 audio_url 格式，不能转成 OpenAI 的 input_audio
    if 'messages' in params and isinstance(params['messages'], list):
        filter_and_transform_content(
            params['messages'], ability, "siliconflow", im,
            audio_output_format="audio_url"
        )

    # -------- 2. Header --------
    extra_headers = params.get('extra_headers', {})
    extra_headers.update({
        'User-Agent': "ChatWindowWithLLMApi-CWLA",
        "HTTP-Referer": "https://github.com/jkcltc/ChatWindowWithLLMApi/",
        "X-Title": "ChatWindowWithLLMApi-CWLA",
    })
    params['extra_headers'] = extra_headers

    return params
