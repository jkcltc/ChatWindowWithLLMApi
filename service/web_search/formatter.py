# websearch/core/formatter.py
from __future__ import annotations
from typing import Iterable, Optional, Sequence, Set
from .models import WebResult

def format_results(
    results: Sequence[WebResult],
    *,
    abstract_only: bool = True,
    allowed_ranks: Optional[Iterable[int]] = None,
    max_total_chars: int = 15000,
    max_item_chars: int = 10000,
) -> str:
    allowed: Optional[Set[int]] = set(allowed_ranks) if allowed_ranks is not None else None

    chunks = []
    total = 0

    for r in results:
        rank = r.hit.rank
        if allowed is not None and rank not in allowed:
            continue

        content = r.hit.snippet if abstract_only else r.content
        if not content:
            content = r.hit.snippet

        if not abstract_only and len(content) > max_item_chars:
            content = content[:max_item_chars]

        block = []
        block.append(f"\n Result {rank}")
        block.append(f"\n Title: {r.hit.title}")
        block.append(f"\n Link: {r.hit.url}")
        if abstract_only:
            block.append(f"\n Abstract: {r.hit.snippet}")
        else:
            block.append(f"\n Content: {content}")
        block.append("\n" + "-" * 10)

        piece = "".join(block)
        if total + len(piece) > max_total_chars:
            break
        chunks.append(piece)
        total += len(piece)

    return "".join(chunks)