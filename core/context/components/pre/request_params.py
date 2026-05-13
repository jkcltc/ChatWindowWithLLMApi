from config import APP_SETTINGS

from core.context.base import ContextComponent
from core.context.model import Descriptor, PrePhase, ContextPayload


class RequestParamsBuilder(ContextComponent):
    """
    构建 API 请求参数 dict。
    原 Preprocessor._build_request_params
    """

    def descriptor(self) -> Descriptor:
        return Descriptor(
            name="request_params_builder",
            phase=PrePhase.FINALIZE,
            depth=20,
            description="构建 API 请求参数 dict",
        )

    def process(self, payload: ContextPayload) -> ContextPayload:
        messages = payload.messages
        pack = payload.pack
        has_tools = len(pack.tool_list) > 0

        params = {
            'model': pack.model,
            'messages': messages,
            'stream': APP_SETTINGS.generation.stream_receive,
        }

        gen_settings = APP_SETTINGS.generation

        if gen_settings.top_p_enable:
            params['top_p'] = float(gen_settings.top_p)
        if gen_settings.temperature_enable:
            params['temperature'] = float(gen_settings.temperature)
        if gen_settings.presence_penalty_enable:
            params['presence_penalty'] = float(gen_settings.presence_penalty)

        if gen_settings.thinking_enabled:
            params['enable_thinking'] = True

        if has_tools and pack.tool_list:
            params['tools'] = pack.tool_list

        payload.params = params
        return payload
