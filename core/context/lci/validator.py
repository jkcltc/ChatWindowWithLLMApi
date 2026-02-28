from __future__ import annotations
from typing import List, Dict, Optional, Tuple, Set
from .model import LCIValidationReport


class LCIValidator:
    MIN_SUMMARY_RATIO: float = 0.15
    MAX_SUMMARY_RATIO: float = 0.95

    def validate(
        self,
        generated_items: List[Dict],
        anchor_id: str,
        context_data: Optional[Dict],
    ) -> LCIValidationReport:
        contents = self._extract_contents(generated_items)
        if not contents:
            return LCIValidationReport(
                is_empty=True,
                anchor_id=anchor_id,
                error_msg="生成的摘要内容为空",
            )

        # 避免在各种早退场景下无谓 join 大字符串
        summary_len = self._joined_len(contents, sep_len=1)

        if context_data is None:
            return LCIValidationReport(
                is_empty=False,
                anchor_id=anchor_id,
                error_msg="锚点消息不存在或不是主对话序列消息（CWLA_req/user）",
            )

        related_ids = context_data["related_ids"]

        if context_data.get("missing_id"):
            return LCIValidationReport(
                is_empty=False,
                anchor_found=True,
                anchor_id=anchor_id,
                related_ids=tuple(related_ids),
                missing_id=context_data["missing_id"],
                error_msg=f"相关消息ID {context_data['missing_id']} 在历史中不存在，可能已被删除",
            )

        if not context_data["is_continuous"]:
            return LCIValidationReport(
                is_empty=False,
                anchor_found=True,
                ids_valid=False,
                anchor_id=anchor_id,
                related_ids=tuple(related_ids),
                error_msg="被总结的消息存在缺失，上下文不完整",
            )

        original_text = context_data["original_text"]
        original_len = len(original_text)

        if original_len == 0:
            return LCIValidationReport(
                is_empty=False,
                anchor_found=True,
                ids_valid=True,
                anchor_id=anchor_id,
                related_ids=tuple(related_ids),
                error_msg="原始消息内容为空",
            )

        ratio = summary_len / original_len

        if ratio < self.MIN_SUMMARY_RATIO:
            return LCIValidationReport(
                is_empty=False,
                anchor_found=True,
                ids_valid=True,
                anchor_id=anchor_id,
                related_ids=tuple(related_ids),
                summary_ratio=ratio,
                error_msg=f"过度压缩：摘要仅占原文的 {ratio:.1%}（低于 {self.MIN_SUMMARY_RATIO:.0%}）",
            )

        if ratio > self.MAX_SUMMARY_RATIO:
            return LCIValidationReport(
                is_empty=False,
                is_copy=True,  # 比例过高视为未有效压缩
                anchor_found=True,
                ids_valid=True,
                anchor_id=anchor_id,
                related_ids=tuple(related_ids),
                summary_ratio=ratio,
                error_msg=f"未有效压缩：摘要占原文的 {ratio:.1%}（超过 {self.MAX_SUMMARY_RATIO:.0%}）",
            )

        return LCIValidationReport(
            is_empty=False,
            anchor_found=True,
            ids_valid=True,
            anchor_id=anchor_id,
            related_ids=tuple(related_ids),
            summary_ratio=ratio,
            error_msg="",
        )

    def _extract_contents(self, items: List[Dict]) -> List[str]:
        valid: List[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            content = item.get("content", "")
            if isinstance(content, str) and content.strip():
                valid.append(content.strip())
            elif isinstance(content, list):
                texts = [
                    str(part.get("text", "")).strip()
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text" and part.get("text")
                ]
                if texts:
                    valid.append(" ".join(t for t in texts if t))
        return valid

    @staticmethod
    def _joined_len(parts: List[str], sep_len: int = 1) -> int:
        if not parts:
            return 0
        return sum(len(p) for p in parts) + (len(parts) - 1) * sep_len