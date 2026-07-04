"""
ConclusionRenderer —— 统一结论汇总渲染层

输入 List[str] → 输出汇总后的结论段落。
支持合并、摘要生成
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class RenderedConclusion:
    summary: str            # 一句话摘要
    details: List[str]      # 详细要点
    confidence: str = "medium"   # "high" | "medium" | "low"


class ConclusionRenderer:
    """统一结论渲染器"""

    def render(self, conclusions: List[str]) -> RenderedConclusion:
        """将多条结论汇总为结构化输出"""
        if not conclusions:
            return RenderedConclusion(
                summary="暂无分析结论",
                details=[],
                confidence="low",
            )

        # 第一条作为摘要
        summary = conclusions[0]
        details = conclusions[1:] if len(conclusions) > 1 else []

        # 推断置信度（基于结论数量）
        confidence = "high" if len(conclusions) >= 3 else "medium"

        return RenderedConclusion(
            summary=summary,
            details=details,
            confidence=confidence,
        )

    def merge(self, rendered_list: List[RenderedConclusion]) -> RenderedConclusion:
        """合并多个分析包的结论"""
        if not rendered_list:
            return RenderedConclusion(summary="", details=[], confidence="low")

        all_summaries = [r.summary for r in rendered_list if r.summary]
        all_details = []
        for r in rendered_list:
            all_details.extend(r.details)

        merged_summary = "；".join(all_summaries[:3])
        confidences = [r.confidence for r in rendered_list]
        confidence = "high" if "high" in confidences else "medium"

        return RenderedConclusion(
            summary=merged_summary or "综合各维度分析，数据整体表现平稳",
            details=all_details,
            confidence=confidence,
        )
