# websearch/core/scraper.py
from __future__ import annotations
import re
import threading
from typing import Optional
import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from bs4 import BeautifulSoup
from lxml import etree

_thread_local = threading.local()

def _get_session() -> requests.Session:
    sess = getattr(_thread_local, "session", None)
    if sess is None:
        sess = requests.Session()
        adapter = HTTPAdapter(max_retries=3)
        sess.mount("http://", adapter)
        sess.mount("https://", adapter)
        _thread_local.session = sess
    return sess

def decode_html(resp: requests.Response) -> str:
    enc = resp.encoding
    if not enc or enc.lower() == "iso-8859-1":
        enc = resp.apparent_encoding or "utf-8"
    return resp.content.decode(enc, errors="replace")

def _is_http_url(url: str) -> bool:
    return bool(url) and re.match(r"^https?://", url) is not None

class RequestsScraper:
    def __init__(self, timeout: int = 12):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        }

    def scrape_text(self, url: str) -> Optional[str]:
        if not _is_http_url(url):
            return None

        sess = _get_session()
        try:
            resp = sess.get(url, headers=self.headers, timeout=self.timeout, allow_redirects=True)
            resp.raise_for_status()
        except RequestException:
            return None

        html = decode_html(resp)

        # 优先用 lxml 抽 body text；失败再用 bs4
        try:
            tree = etree.HTML(html)
            if tree is None:
                return None

            # 去掉 script/style/noscript
            for bad in tree.xpath("//script|//style|//noscript"):
                parent = bad.getparent()
                if parent is not None:
                    parent.remove(bad)

            texts = tree.xpath("//body//text()")
            text = " ".join(t.strip() for t in texts if t and t.strip())
            return text or None
        except Exception:
            try:
                soup = BeautifulSoup(html, "html.parser")
                for bad in soup(["script", "style", "noscript"]):
                    bad.decompose()
                body = soup.body
                return body.get_text(" ", strip=True) if body else soup.get_text(" ", strip=True)
            except Exception:
                return None