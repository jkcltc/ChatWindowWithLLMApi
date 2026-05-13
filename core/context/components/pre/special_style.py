from config import APP_SETTINGS
from core.session.enforce_repeat import RepeatProcessor

from core.context.base import ContextComponent
from core.context.model import Descriptor, PrePhase, ContextPayload


class SpecialStyleModifier(ContextComponent):
    """
    临时样式注入 + 强制降重。
    原 Preprocessor._process_special_styles
    """

    def descriptor(self) -> Descriptor:
        return Descriptor(
            name="special_style_modifier",
            phase=PrePhase.TRANSFORM,
            depth=10,
            description="temp_style + enforce_lower_repeat 注入",
        )

    def process(self, payload: ContextPayload) -> ContextPayload:
        messages = payload.messages
        if not messages:
            return payload

        pack = payload.pack
        temp_style = pack.optional.get('temp_style', '')
        force_text = pack.optional.get('enforce_lower_repeat_text', '') if APP_SETTINGS.force_repeat.enabled else ''

        if not force_text and APP_SETTINGS.force_repeat.enabled:
            should_cut, force_text = RepeatProcessor.analyze_repeats(messages)
            if should_cut:
                cut_length = min(len(messages), 4)
                if len(messages) > 4:
                    messages = [messages[0]] + messages[cut_length:]
                else:
                    messages = messages[cut_length:]

        if not temp_style and not force_text:
            payload.messages = messages
            return payload

        user_index = None
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "user":
                user_index = i
                break

        append_text = []
        if user_index is not None:
            if temp_style:
                append_text += [f"请使用该指定风格回答用户:{temp_style}"]
            if force_text:
                append_text += [f"你必须避免重复以下内容:{force_text}"]
            new_system_msg = {"role": "system", "content": '\n'.join(append_text)}
            messages.insert(user_index, new_system_msg)

        payload.messages = messages
        return payload
