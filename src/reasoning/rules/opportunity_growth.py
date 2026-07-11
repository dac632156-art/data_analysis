"""
Rule: Opportunity: 增长机会

从 growth + ranking 中自动发现正增长的实体，
识别具有高增长潜力的机会领域。
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


class OpportunityGrowthRule(BaseRule):
    name = "opportunity_growth"
    description = "Opportunity: 增长机会 —— 高增长实体识别"
    category = "opportunity"

    def evaluate(self, graph: BusinessFactGraph,
                 packages: List[AnalysisPackage]) -> List[InferredConclusion]:
        conclusions = []
        growth_nodes = graph.get_nodes_by_category("growth")
        ranking_nodes = graph.get_nodes_by_category("ranking")
        retention_nodes = graph.get_nodes_by_category("retention")

        # 找高增长实体（>10%）
        growing = [n for n in growth_nodes
                   if n.value is not None and n.value > 10
                   and (n.entity or "").lower() != "全量"]
        growing.sort(key=lambda n: n.value or 0, reverse=True)

        for gnode in growing[:3]:
            gentity = gnode.entity.lower() if gnode.entity else ""

            # 找贡献度
            contribution = None
            for rnode in ranking_nodes:
                if rnode.entity.lower() == gentity and rnode.value is not None:
                    contribution = rnode.value
                    break

            # 找复购情况
            retention_info = ""
            for tnode in retention_nodes:
                if tnode.entity.lower() == gentity and tnode.value is not None:
                    if tnode.value > 0.5:
                        retention_info = f"复购率也较高（{tnode.value*100:.0f}%），增长可持续性强。"
                    break

            evidence = [EvidenceItem(
                finding_id=gnode.id, finding_title=gnode.finding_title,
                package_index=gnode.package_index,
            )]

            desc = f"「{gnode.entity}」增长率 {gnode.value:.1f}%，是当前增长最快的领域。"
            if contribution is not None:
                desc += f" 当前贡献度 {contribution*100:.0f}%。"
            desc += f" {retention_info}"

            conclusions.append(InferredConclusion(
                id=str(uuid.uuid4()),
                category=ConclusionCategory.OPPORTUNITY,
                title=f"「{gnode.entity}」增长 {gnode.value:.1f}%，为重点增长机会",
                description=desc.strip(),
                confidence=0.70,
                evidence_items=evidence,
                evidence_count=len(evidence),
                source_package_indices=[gnode.package_index],
                related_finding_ids=[gnode.id],
            ))

        return conclusions