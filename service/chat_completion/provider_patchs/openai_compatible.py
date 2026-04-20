from ..patch_manager import register_provider
# 别忘了从隔壁把公共工具借过来
from .commons import filter_and_transform_content

@register_provider("openai_compatible")
def patch_openai_compatible_logic(params, config):
    """
    OpenAI Compatible / Generic (Modular Version)
    功能：
    1. 清理非标准参数
    2. 多模态标准化
    """
    im = config.get('log_manager')

    # 获取配置中的能力列表，如果没配，就默认给 text, image, audio
    ability = config.get('input_ability', ['text', 'image', 'audio']) 

    # -------- 1. 参数清洗 --------
    # 既然是通用兼容模式，就不要传那些奇奇怪怪的私有参数了
    if 'enable_thinking' in params:
        params.pop('enable_thinking', None)

    # -------- 2. 多模态标准化 --------
    if 'messages' in params and isinstance(params['messages'], list):
        filter_and_transform_content(params['messages'], ability, "OpenAI_Compat", im)

    # -------- 3. Header --------
    # 孩子们，我不准备告诉服务器我是谁

    return params