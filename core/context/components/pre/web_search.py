from typing import TYPE_CHECKING

from config import APP_SETTINGS

from core.context.base import ContextComponent
from core.context.model import Descriptor, PrePhase, ContextPayload

if TYPE_CHECKING:
    from service.web_search import WebSearchFacade


class WebSearchInjector(ContextComponent):
    """
    搜索结果注入到 last user 前。
    原 Preprocessor._handle_web_search_results
    """

    def __init__(self):
        self.search_facade: "WebSearchFacade | None" = None
        self.return_search_result = None

    def web_enabled(self, search_facade: "WebSearchFacade", return_search_result=None):
        self.search_facade = search_facade
        self.return_search_result = return_search_result

    def descriptor(self) -> Descriptor:
        return Descriptor(
            name="web_search_injector",
            phase=PrePhase.INJECT,
            depth=0,
            description="搜索结果注入到 last user 前",
        )

    def process(self, payload: ContextPayload) -> ContextPayload:
        messages = payload.messages
        pack = payload.pack
        search_result = pack.optional.get('web_search_result', '')

        # 路径1: pack 中已有预搜索结果，直接注入
        if search_result:
            if messages[-1]["role"] == "user":
                prompt_text = f"搜索引擎提供的结果:\n{search_result}\n请根据以上搜索结果回答用户的提问。"
                new_msg = {"role": "system", "content": prompt_text}
                messages.insert(-1, new_msg)
            payload.messages = messages
            return payload

        # 路径2: 配置启用搜索，执行在线搜索
        if APP_SETTINGS.web_search.web_search_enabled:
            if not self.search_facade:
                raise RuntimeError(
                    "web_search_injector: search_facade 未注入，"
                    "请确认 _ensure_web_ability() 已被调用"
                )

            ct = pack.chat_session.history[-1]['content']
            if isinstance(ct, list):
                query = ''
                for item in ct:
                    if item['type'] == 'text':
                        query = item['text']
                        break
            elif isinstance(ct, str):
                query = ct
            else:
                query = ''

            if not query:
                payload.messages = messages
                return payload

            web_cfg = APP_SETTINGS.web_search
            api_cfg = APP_SETTINGS.api

            # 确定是否使用 RAG
            use_rag = web_cfg.use_llm_reformat

            # 准备 RAG 参数
            rag_url = rag_key = rag_model = ""
            if use_rag:
                rag_pack = web_cfg.reformat_config
                provider = api_cfg.providers.get(rag_pack.provider)
                if not provider:
                    raise ValueError(f"Provider not found: {rag_pack.provider}")
                rag_url = provider.url
                rag_key = provider.key
                rag_model = rag_pack.model

            # 执行搜索
            result = self.search_facade.run(
                query=query,
                limit=web_cfg.search_results_num,
                use_rag=use_rag,
                rag_provider_url=rag_url,
                rag_provider_key=rag_key,
                rag_model=rag_model,
            )
            print("web_run:",result)
            if result['reference']:
                prompt_text = f"搜索引擎提供的结果:\n{result['reference']}\n请根据以上搜索结果回答用户的提问。"
                new_msg = {"role": "system", "content": prompt_text}
                messages.insert(-1, new_msg)
                if self.return_search_result:
                    self.return_search_result(result)

        payload.messages = messages
        return payload
