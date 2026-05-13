# websearch/core/service.py
from __future__ import annotations
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Sequence

from .models import SearchHit, WebResult
from .engines import BingSearchEngine, BaiduSearchEngine, SearchEngine
from .scraper import RequestsScraper
from .formatter import format_results
from .rag import RagFilter, RagDecision

logger = logging.getLogger(__name__)

_ENGINES = {
    "bing": BingSearchEngine,
    "baidu": BaiduSearchEngine,
}

# 互为备用的引擎对
_FALLBACK_MAP = {
    "bing": "baidu",
    "baidu": "bing",
}

class WebSearchService:
    def __init__(
        self,
        *,
        engine: SearchEngine,
        scraper: RequestsScraper,
        max_workers: int = 6,
    ):
        self.engine = engine
        self.scraper = scraper
        self.max_workers = max_workers

    def search_and_scrape(self, query: str, limit: int) -> List[WebResult]:
        hits = self.engine.search(query, limit)

        results: List[WebResult] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            fut_map = {ex.submit(self.scraper.scrape_text, h.url): h for h in hits}

            for fut in as_completed(fut_map):
                hit = fut_map[fut]
                text = None
                try:
                    text = fut.result()
                except Exception:
                    text = None

                content = text or hit.snippet
                results.append(WebResult(hit=hit, content=content))

        results.sort(key=lambda r: r.hit.rank)
        return results

class WebSearchFacade:
    """
    同步业务入口
    - search + 并发抓取
    - 可选 rag 决策
    - 返回给下一步用的 reference 文本
    """
    def __init__(
        self,
        *,
        engine_name: str,
        max_workers: int = 6,
        timeout: int = 12,
        rag_filter: Optional[RagFilter] = None,
    ):
        if engine_name not in _ENGINES:
            raise ValueError(f"Unknown engine: {engine_name}")

        self.engine_name = engine_name
        self.timeout = timeout
        self.scraper = RequestsScraper(timeout=timeout)
        self.max_workers = max_workers
        self.rag_filter = rag_filter

    def _make_service(self, engine: SearchEngine) -> WebSearchService:
        return WebSearchService(engine=engine, scraper=self.scraper, max_workers=self.max_workers)

    def _create_engine(self, name: str) -> SearchEngine:
        return _ENGINES[name](timeout=self.timeout)

    def run(
        self,
        *,
        query: str,
        limit: int,
        use_rag: bool = False,
        rag_provider_url: str = "",
        rag_provider_key: str = "",
        rag_model: str = "",
    ) -> dict:
        engine = self._create_engine(self.engine_name)
        service = self._make_service(engine)
        results = service.search_and_scrape(query, limit)

        # 主引擎返回空结果时，自动尝试备用引擎
        if not results:
            fallback_name = _FALLBACK_MAP.get(self.engine_name)
            if fallback_name:
                logger.info(
                    "[WebSearch] %s returned 0 results, falling back to %s for query=%r",
                    self.engine_name, fallback_name, query,
                )
                fb_engine = self._create_engine(fallback_name)
                fb_service = self._make_service(fb_engine)
                results = fb_service.search_and_scrape(query, limit)

        # 默认：直接摘要引用
        reference = format_results(results, abstract_only=True)
        print("referenced:",reference)

        if use_rag and self.rag_filter:
            decision = self.rag_filter.decide(
                query=query,
                results=results,
                provider_url=rag_provider_url,
                provider_key=rag_provider_key,
                model=rag_model,
            )
            if decision:
                if decision.enough_intel:
                    reference = format_results(results, abstract_only=True)
                else:
                    if decision.useful_result:
                        reference = format_results(results, abstract_only=False, allowed_ranks=decision.useful_result)
                    else:
                        reference = "Result: Rag模型报告没有有效的搜索结果"

        return {
            "query": query,
            "results": results,      # 结构化，供 UI/调试
            "reference": reference,  # 给工作流下一步拼 prompt 用
        }