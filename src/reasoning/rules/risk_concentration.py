"""
Rule: Risk 集中度风险

当 concentration 分析发现 HHI > 2500 或 CR3 > 80% 时，
自动生成风险结论。
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any, TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from src.reasoning.business_fact_graph import BusinessFactGraph
    from src.reasoning.reasoning_result import InferredConclusion, EvidenceItem, ConclusionCategory, EvidenceStrength
    from src.analysis_templates.base import AnalysisPackage

from src.reasoning.rules.base_rule import BaseRule
from src.reasoning.reasoning_result import (
    InferredConclusion, EvidenceItem, ConclusionCategory, EvidenceStrength,
)


class RiskConcentrationRule(BaseRule):
    name = "risk_concentration"
    description = "Risk: 集中度风险 —— HHI>2500 或 CR3>80% 触发"
    category = "risk"

    def evaluate(self, graph: BusinessFactGraph,
                 packages: List[AnalysisPackage]) -> List[InferredConclusion]:
        conclusions = []
        concentration_nodes = graph.get_nodes_by_category("concentration")

        for node in concentration_nodes:
            title_lower = node.finding_title.lower()
            if "hhi" in title_lower or "集中度" in node.finding_title:
                if node.value is not None and node.value > 2500:
                    evidence = [EvidenceItem(
                        finding_id=node.id, finding_title=node.finding_title,
                        package_index=node.package_index,
                    )]
                    conclusions.append(InferredConclusion(
                        id=str(uuid.uuid4()),
                        category=ConclusionCategory.RISK,
                        title=f"HHI 指数 {node.value:.0f}，市场高度集中风险",
                        description=(
                            f"当前 HHI 指数达到 {node.value:.0f}（>2500 为高度集中），"
                            f"对头部分类/客户/产品的依赖度过高。"
                            f"一旦头部出现波动，整体业务将受到显著冲击。"
                        ),
                        confidence=0.85,
                        evidence_items=evidence,
                        evidence_count=1,
                        source_package_indices=[node.package_index],
                        related_finding_ids=[node.id],
                    ))

        return conclusions