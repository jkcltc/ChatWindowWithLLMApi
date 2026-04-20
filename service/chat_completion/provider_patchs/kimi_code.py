from ..patch_manager import register_provider
from .commons import filter_and_transform_content

@register_provider("kimi_code")
def patch_kimi_code_logic(params, config):
    """
    Kimi Code 补丁逻辑
    功能：
    1. 清理非标准参数
    2. 多模态标准化
    3. 添加Kilo Code特定头部
    """
    im = config.get('log_manager')
    
    # 获取配置中的能力列表，如果没配，就默认给 text, image, audio
    ability = config.get('input_ability', ['text', 'image', 'audio']) 
    
    # 获取版本信息，默认使用配置中的版本或固定版本
    version = config.get('version', '5.2.2')
    
    # -------- 1. 参数清洗 --------
    # 清理非标准参数
    if 'enable_thinking' in params:
        params.pop('enable_thinking', None)
    
    # -------- 2. 多模态标准化 --------
    if 'messages' in params and isinstance(params['messages'], list):
        filter_and_transform_content(params['messages'], ability, "Kimi_Code", im)
    
    # -------- 3. Header --------
    extra_headers = params.get('extra_headers', {})
    extra_headers.update({
        "HTTP-Referer": "https://kilocode.ai",
        "X-Title": "Kilo Code",
        "X-KiloCode-Version": version,
        "User-Agent": f"Kilo-Code/{version}",
    })
    params['extra_headers'] = extra_headers
    #params['stream'] = False
    
    return params