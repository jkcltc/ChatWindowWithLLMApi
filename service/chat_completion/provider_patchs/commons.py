import re

def filter_and_transform_content(messages, ability, provider_type, im=None):
    """
    公共清洗逻辑：
    1. 根据 input_ability (text, image, audio) 剔除不支持的模态。
    2. 执行格式转换 (如 Audio URL -> Input Audio)。
    """
    if not isinstance(ability, list):
        ability = ['text'] 

    for msg in messages:
        content = msg.get('content')
        if isinstance(content, str):
            continue

        if isinstance(content, list):
            new_content = []
            for item in content:
                item_type = item.get('type')

                # 1. 文本
                if item_type == 'text':
                    new_content.append(item)

                # 2. 图片
                elif item_type == 'image_url':
                    if 'image' in ability:
                        new_content.append(item)
                    elif im:
                        im.log(f"[{provider_type}] 自动剔除不支持的图片", level="debug")

                # 3. 音频
                elif item_type in ['audio_url', 'input_audio']:
                    if 'audio' in ability:
                        processed = _transform_audio_item(item)
                        if processed:
                            new_content.append(processed)
                    elif im:
                        im.log(f"[{provider_type}] 自动剔除不支持的音频", level="debug")

            if not new_content:
                msg['content'] = "..." 
            else:
                msg['content'] = new_content

def _transform_audio_item(item):
    """私有助手：音频格式标准化"""
    raw_url = ""
    if item.get('type') == 'audio_url':
        raw_url = item.get('audio_url', {}).get('url', '')
    elif item.get('type') == 'input_audio':
        return item

    if not raw_url:
        return None

    # 简单的 Base64 提取逻辑
    fmt = 'wav'
    b64_data = raw_url
    match = re.match(r'^data:audio/([a-zA-Z0-9]+);base64,(.+)$', raw_url)
    if match:
        fmt = match.group(1)
        b64_data = match.group(2)
    elif "base64," in raw_url:
        b64_data = raw_url.split("base64,")[1]

    return {
        "type": "input_audio",
        "input_audio": {
            "data": b64_data,
            "format": fmt
        }
    }
