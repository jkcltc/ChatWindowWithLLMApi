# websearch/core/engines.py
from __future__ import annotations
import logging
import re
import xml.etree.ElementTree as ET
from html import unescape
from typing import List, Protocol
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from .models import SearchHit

logger = logging.getLogger(__name__)

class SearchEngine(Protocol):
    def search(self, query: str, limit: int) -> List[SearchHit]: ...

def _clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s

def _strip_html_tags(s: str) -> str:
    """移除 HTML 标签，保留纯文本"""
    return re.sub(r"<[^>]+>", " ", s or "")

class BingSearchEngine:
    """Bing RSS 搜索 — 使用 Bing RSS/XML 接口，绕过 HTML 页面的 CAPTCHA 拦截"""

    RSS_URL = "https://www.bing.com/search?format=rss&mkt=zh-CN&setlang=zh-cn&q="

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    def search(self, query: str, limit: int) -> List[SearchHit]:
        url = self.RSS_URL + quote(query)
        resp = requests.get(url, headers=self.headers, timeout=self.timeout)
        resp.raise_for_status()

        logger.debug(
            "[BingRSS] request url=%s, final url=%s, status=%s",
            url, resp.url, resp.status_code,
        )

        hits: List[SearchHit] = []

        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError:
            # 尝试用 bytes 解析（处理编码声明问题）
            try:
                root = ET.fromstring(resp.content)
            except ET.ParseError as e:
                logger.warning(
                    "[BingRSS] XML parse error for query=%r status=%s ct=%s: %s",
                    query, resp.status_code, resp.headers.get("content-type"), e,
                )
                return hits

        rank = 1
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")

            title = title_el.text if title_el is not None and title_el.text else ""
            link = link_el.text if link_el is not None and link_el.text else ""
            raw_desc = desc_el.text if desc_el is not None and desc_el.text else ""

            title = _clean_text(title)
            link = link.strip()
            snippet = _clean_text(unescape(_strip_html_tags(raw_desc)))

            if not link or not title:
                continue

            hits.append(SearchHit(
                rank=rank, title=title, url=link, snippet=snippet, source="bing_rss",
            ))
            rank += 1
            if rank > limit:
                break

        if not hits:
            logger.warning(
                "[BingRSS] 0 items parsed for query=%r final_url=%s status=%s xml_len=%d",
                query, resp.url, resp.status_code, len(resp.text),
            )

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

        logger.debug("[BaiduSearch] request url=%s, final url=%s, status=%s",
                     url, resp.url, resp.status_code)

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

        if not hits:
            title_tag = soup.title.string if soup.title else "(no title)"
            has_verify = bool(soup.select("#verify, #vcode, .verify-wrap"))
            logger.warning(
                "[BaiduSearch] 0 results for query=%r  final_url=%s  page_title=%r  verify_like=%s  html_len=%d",
                query, resp.url, title_tag, has_verify, len(resp.text),
            )

        return hits