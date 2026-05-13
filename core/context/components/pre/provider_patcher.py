from config import APP_SETTINGS
from service.chat_completion import GlobalPatcher

from core.context.base import ContextComponent
from core.context.model import Descriptor, PrePhase, ContextPayload


class ProviderPatcher(ContextComponent):
    """
    应用 provider 特定补丁。
    原 Preprocessor._handle_provider_patch
    """

    def descriptor(self) -> Descriptor:
        return Descriptor(
            name="provider_patcher",
            phase=PrePhase.FINALIZE,
            depth=30,
            description="应用 provider 特定补丁",
        )

    def process(self, payload: ContextPayload) -> ContextPayload:
        pack = payload.pack
        provider_type = pack.provider.provider_type

        patcher = GlobalPatcher()
        config_context = {
            "reasoning_effort": APP_SETTINGS.generation.reasoning_effort,
            'provider_buildin_search_enabled': APP_SETTINGS.web_search.enable_provider_buildin,
            'input_ability': ['text', 'image', 'audio']
        }
        payload.params = patcher.patch(payload.params, provider_type, config_context)
        return payload
