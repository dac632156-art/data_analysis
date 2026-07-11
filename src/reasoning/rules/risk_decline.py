"""
Rule: Risk: 持续下滑风险

从 growth 中识别持续下滑的趋势节点，
评估其对整体业务的潜在风险。
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


class RiskDeclineRule(BaseRule):
    name = "risk_decline"
    description = "Risk: 持续下滑风险 —— 多实体同时下滑"
    category = "risk"

    def evaluate(self, graph: BusinessFactGraph,
                 packages: List[AnalysisPackage]) -> List[InferredConclusion]:
        conclusions = []
        growth_nodes = graph.get_nodes_by_category("growth")

        # 收集所有下滑的实体
        declining = [n for n in growth_nodes
                     if n.value is not None and n.value < -10
                     and (n.entity or "").lower() != "全量"]

        if len(declining) >= 2:
            entity_names = [n.entity for n in declining[:5]]
            evidence = [
                EvidenceItem(finding_id=n.id, finding_title=n.finding_title, package_index=n.package_index)
                for n in declining[:5]
            ]

            total_decline = sum(abs(n.value) for n in declining if n.value) / len(declining)

            conclusions.append(InferredConclusion(
                id=str(uuid.uuid4()),
                category=ConclusionCategory.RISK,
                title=f"多实体同时下滑，平均降幅 {total_decline:.0f}%，系统性风险",
                description=(
                    f"以下 {len(declining)} 个实体同时出现显著下滑（降幅 > 10%）："
                    f"{', '.join(entity_names[:5])}。"
                    f"这不是个别现象，可能存在系统性原因（市场变化、竞争加剧、政策调整等）。"
                    f"平均降幅 {total_decline:.0f}%，需紧急调查。"
                ),
                confidence=0.70,
                evidence_items=evidence,
                evidence_count=len(evidence),
                source_package_indices=list({n.package_index for n in declining[:5]}),
                related_finding_ids=[n.id for n in declining[:5]],
            ))

        return conclusions