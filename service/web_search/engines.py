# websearch/core/engines.py
from __future__ import annotations
import re
from typing import List, Protocol
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup

from .models import SearchHit

class SearchEngine(Protocol):
    def search(self, query: str, limit: int) -> List[SearchHit]: ...

def _clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s

class BingSearchEngine:
    SEARCH_URL = "https://www.bing.com/search?q="

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        }

    def search(self, query: str, limit: int) -> List[SearchHit]:
        url = self.SEARCH_URL + quote(query)
        resp = requests.get(url, headers=self.headers, timeout=self.timeout)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        hits: List[SearchHit] = []
        rank = 1

        # 常见结构：li.b_algo h2 a + div.b_caption p
        for li in soup.select("li.b_algo"):
            a = li.select_one("h2 a")
            if not a:
                continue
            link = a.get("href", "").strip()
            title = _clean_text(a.get_text(" ", strip=True))

            p = li.select_one(".b_caption p") or li.select_one("p")
            snippet = _clean_text(p.get_text(" ", strip=True) if p else "")

            if not link or not title:
                continue

            hits.append(SearchHit(rank=rank, title=title, url=link, snippet=snippet, source="bing"))
            rank += 1
            if rank > limit:
                break

        return hits

class BaiduSearchEngine:
    SEARCH_URL = "https://www.baidu.com/s?wd="

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def search(self, query: str, limit: int) -> List[SearchHit]:
        url = self.SEARCH_URL + quote(query)
        resp = requests.get(url, headers=self.headers, timeout=self.timeout)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        hits: List[SearchHit] = []
        rank = 1

        # 常见结构：div#content_left 下的 div.result 或 div.c-container
        for item in soup.select("#content_left .result, #content_left .c-container"):
            a = item.select_one("h3 a")
            if not a:
                continue
            link = a.get("href", "").strip()  # 可能是 baidu 跳转链接，后续抓取会自动重定向
            title = _clean_text(a.get_text(" ", strip=True))

            abstract = item.select_one(".c-abstract") or item.select_one(".content-right_8Zs40") or item.select_one("span.content-right_8Zs40")
            snippet = _clean_text(abstract.get_text(" ", strip=True) if abstract else item.get_text(" ", strip=True))

            if not link or not title:
                continue

            hits.append(SearchHit(rank=rank, title=title, url=link, snippet=snippet, source="baidu"))
            rank += 1
            if rank > limit:
                break

        return hits