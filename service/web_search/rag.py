# websearch/core/rag.py
from __future__ import annotations
import json
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence

try:
    # openai>=1.x
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore

from .models import WebResult
from .formatter import format_results

@dataclass(frozen=True)
class RagDecision:
    enough_intel: bool
    useful_result: List[int]

def _extract_json_objects(text: str) -> List[dict]:
    candidates = re.findall(r"\{[\s\S]*?\}", text)
    out = []
    for c in candidates:
        try:
            out.append(json.loads(c))
        except json.JSONDecodeError:
            continue
    return out

class RagFilter:
    """
    用 LLM 判断：仅摘要是否足够，如果不够则返回有用的结果序号 useful_result
    """
    def __init__(self, prefix: str, suffix: str):
        self.prefix = prefix
        self.suffix = suffix

    def decide(
        self,
        *,
        query: str,
        results: Sequence[WebResult],
        provider_url: str,
        provider_key: str,
        model: str,
        timeout: float = 60.0,
    ) -> Optional[RagDecision]:
        if OpenAI is None:
            raise RuntimeError("openai SDK not available")

        # 给 RAG 的输入：固定用摘要，避免把正文喂太多
        reference = format_results(results, abstract_only=True)
        user_input = f"{self.prefix}{query}{self.suffix}{reference}"

        client = OpenAI(api_key=provider_key, base_url=provider_url)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": user_input}],
            temperature=0,
            stream=False,
            timeout=timeout,
        )
        msg = resp.choices[0].message.content or ""
        objs = _extract_json_objects(msg)
        if not objs:
            return None

        obj = objs[0]
        enough = obj.get("enough_intel", False)
        useful = obj.get("useful_result", []) or []
        # 容错：字符串 True/False
        if isinstance(enough, str):
            enough = enough.lower() == "true"
        if isinstance(useful, str):
            useful = [int(x) for x in re.findall(r"\d+", useful)]
        useful = [int(x) for x in useful if str(x).isdigit()]

        return RagDecision(enough_intel=bool(enough), useful_result=useful)