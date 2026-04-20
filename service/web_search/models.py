# websearch/core/models.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List

@dataclass(frozen=True)
class SearchHit:
    rank: int
    title: str
    url: str
    snippet: str
    source: str = ""

@dataclass(frozen=True)
class WebResult:
    hit: SearchHit
    content: str  # 抓到正文用正文，抓不到就回退 snippet