# websearch/core/service.py
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Sequence

from .models import SearchHit, WebResult
from .engines import BingSearchEngine, BaiduSearchEngine, SearchEngine
from .scraper import RequestsScraper
from .formatter import format_results
from .rag import RagFilter, RagDecision

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
        if engine_name == "bing":
            engine = BingSearchEngine(timeout=timeout)
        elif engine_name == "baidu":
            engine = BaiduSearchEngine(timeout=timeout)
        else:
            raise ValueError(f"Unknown engine: {engine_name}")

        scraper = RequestsScraper(timeout=timeout)
        self.service = WebSearchService(engine=engine, scraper=scraper, max_workers=max_workers)
        self.rag_filter = rag_filter

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
        results = self.service.search_and_scrape(query, limit)

        # 默认：直接摘要引用
        reference = format_results(results, abstract_only=True)

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