import re
from utils.tools.patch_manager import register_provider

@register_provider("openrouter")
def patch_openrouter_logic(params, config):
    """
    OpenRouter
    功能：
    1. 多模态格式整形 (Audio URL -> Input Audio)
    2. Thinking 字段映射
    3. 请求头注入
    """
    im = config.get('log_manager')

    # -------- 1. 多模态大整形 (Surgical Operation) --------
    # 只有当 params 里有 messages 且是列表时才处理
    if 'messages' in params and isinstance(params['messages'], list):
        _transform_multimodal_content(params['messages'], im)

    # -------- 2. Thinking 逻辑 --------
    if 'enable_thinking' in params:
        is_thinking = params.pop('enable_thinking', False)

        params["reasoning"] = {
            "exclude": False,
            "enabled": is_thinking
        }

        if is_thinking and (effort_level := config.get('reasoning_effort')):
            effort_map = {1: "low", 2: "medium", 3: "high"}
            if effort_level in effort_map:
                params["reasoning"]["effort"] = effort_map[effort_level]

    # -------- 3. Header 注入 --------
    extra_headers = params.get('extra_headers', {})
    extra_headers.update({
        "HTTP-Referer": "https://github.com/jkcltc/ChatWindowWithLLMApi/",
        "X-Title": "ChatWindowWithLLMApi-CWLA",
    })
    params['extra_headers'] = extra_headers

    return params


def _transform_multimodal_content(messages, im=None):
    """
    私有助手：遍历消息，把 SiliconFlow 格式的多模态数据
    扭转成 OpenRouter (OpenAI) 兼容格式
    """
    for msg in messages:
        content = msg.get('content')
        # 只处理 List 类型的 content (多模态)
        if not isinstance(content, list):
            continue

        # 遍历 content 中的每一个 item
        for item in content:
            item_type = item.get('type')

            # -------------------------------------------------
            # CASE A: 音频处理 (audio_url -> input_audio)
            # 硅基: type='audio_url', audio_url={'url': 'data:audio/wav;base64,xxxxx'}
            # OR  : type='input_audio', input_audio={'data': 'xxxxx', 'format': 'wav'}
            # -------------------------------------------------
            if item_type == 'audio_url':
                audio_obj = item.get('audio_url', {})
                raw_url = audio_obj.get('url', '')

                if not raw_url:
                    continue

                # 提取 Base64 数据和格式
                # 尝试解析 data URI scheme: data:audio/wav;base64,......
                # 如果解析不出，默认只要是 Base64 就硬塞
                fmt = 'wav' # 默认格式
                b64_data = raw_url

                # 正则匹配头部，比如 data:audio/mp3;base64,
                match = re.match(r'^data:audio/([a-zA-Z0-9]+);base64,(.+)$', raw_url)
                if match:
                    fmt = match.group(1) # 拿到 mp3, wav 等
                    b64_data = match.group(2) # 拿到去掉头部的纯 base64
                else:
                    # 如果不是标准头，尝试简单的 split，或者就是纯 raw base64
                    if "base64," in raw_url:
                        b64_data = raw_url.split("base64,")[1]

                # 开始整形！
                # 1. 改类型
                item['type'] = 'input_audio'
                # 2. 构造新结构
                item['input_audio'] = {
                    "data": b64_data,
                    "format": fmt
                }
                # 3. 销毁旧结构 (毁尸灭迹，防止 API 报错)
                item.pop('audio_url', None)

                if im:
                    im.log(f"[OpenRouter] 转化音频流: {fmt} 格式", level="debug")

            # -------------------------------------------------
            # CASE B: 图片处理 (PDF/Image)
            # 大部分情况下 image_url 是兼容的，但要注意 PDF
            # -------------------------------------------------
            elif item_type == 'image_url':
                # 一致
                pass
