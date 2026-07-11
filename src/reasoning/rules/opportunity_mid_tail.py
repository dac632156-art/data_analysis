"""
Rule: Opportunity: 中腰部机会

从 ranking + concentration 中识别中腰部（非头部但有一定份额）的实体，
这些实体往往是被忽视的增长机会。
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


class OpportunityMidTailRule(BaseRule):
    name = "opportunity_mid_tail"
    description = "Opportunity: 中腰部机会 —— 非头部但有一定份额的潜力实体"
    category = "opportunity"

    def evaluate(self, graph: BusinessFactGraph,
                 packages: List[AnalysisPackage]) -> List[InferredConclusion]:
        conclusions = []
        ranking_nodes = graph.get_nodes_by_category("ranking")
        concentration_nodes = graph.get_nodes_by_category("concentration")
        growth_nodes = graph.get_nodes_by_category("growth")

        # 检查集中度是否过高（头部过重 = 中尾部有机会）
        has_concentration = any(
            n.value is not None and n.value > 2000
            for n in concentration_nodes
            if "hhi" in n.finding_title.lower()
        )

        if not has_concentration and len(ranking_nodes) < 5:
            return conclusions

        # 找中腰部：排名 3-5，贡献 5%-15%
        mid_tail = []
        for rnode in ranking_nodes:
            rval = rnode.value
            if rval is not None and 0.05 < rval < 0.15:
                mid_tail.append(rnode)

        if len(mid_tail) >= 2:
            mid_names = [n.entity for n in mid_tail[:3]]
            evidence = [
                EvidenceItem(finding_id=n.id, finding_title=n.finding_title, package_index=n.package_index)
                for n in mid_tail[:3]
            ]

            # 检查中腰部是否有正增长
            growth_context = ""
            for gnode in growth_nodes:
                if any(gnode.entity.lower() == mt.entity.lower() for mt in mid_tail):
                    if gnode.value is not None and gnode.value > 5:
                        growth_context = f"其中部分实体已出现正增长，建议加大投入。"
                        break

            conclusions.append(InferredConclusion(
                id=str(uuid.uuid4()),
                category=ConclusionCategory.OPPORTUNITY,
                title=f"中腰部 {len(mid_tail)} 个实体存在增长空间，降低头部依赖",
                description=(
                    f"当前头部集中度较高，而中腰部实体如 {', '.join(mid_names)} "
                    f"贡献合计可观，具备提升空间。{growth_context}"
                    f"建议对中腰部实体进行重点培育，分散风险的同时开拓新增长极。"
                ),
                confidence=0.65,
                evidence_items=evidence,
                evidence_count=len(evidence),
                source_package_indices=list({n.package_index for n in mid_tail[:3]}),
                related_finding_ids=[n.id for n in mid_tail[:3]],
            ))

        return conclusions