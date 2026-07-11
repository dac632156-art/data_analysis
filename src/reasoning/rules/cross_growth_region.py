"""
Rule: Cross Analysis: Growth x Region/Ranking

Cross-analysis: correlate growth signals with ranking/contribution data
to identify entity-level root causes for overall trends.
"""
from __future__ import annotations
from typing import List, TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from src.reasoning.business_fact_graph import BusinessFactGraph
    from src.reasoning.reasoning_result import InferredConclusion
    from src.analysis_templates.base import AnalysisPackage

from src.reasoning.rules.base_rule import BaseRule
from src.reasoning.business_fact_graph import RelationType
from src.reasoning.reasoning_result import (
    InferredConclusion, EvidenceItem, ConclusionCategory, EvidenceStrength,
)


class CrossGrowthRegionRule(BaseRule):
    """Cross Analysis: Growth x Region/Ranking

    Strategy:
    1. Find growth nodes indicating decline
    2. Find ranking/structure nodes for same entities
    3. Link declining entities to their contribution share
    4. Identify root causes where declining entity has high contribution
    """
    name = "cross_growth_region"
    description = "Cross Analysis: Growth x Region - link entity decline to contribution"
    category = "cross_analysis"

    def evaluate(self, graph: "BusinessFactGraph",
                 packages: List["AnalysisPackage"]) -> List["InferredConclusion"]:
        conclusions = []

        growth_nodes = graph.get_nodes_by_category("growth")
        ranking_nodes = graph.get_nodes_by_category("ranking")
        structure_nodes = graph.get_nodes_by_category("structure")
        comparison_nodes = graph.get_nodes_by_category("comparison")

        # Strategy A: Overall growth decline + high-contribution entities
        for gnode in growth_nodes:
            if gnode.value is None:
                continue
            entity = gnode.entity.lower()
            if not entity or entity == "全量":
                # For "all" growth: find which entities drive it
                decline_signaled = gnode.value < 0
                direction = "down" if decline_signaled else "up"

                # Find highest contributors from ranking/structure
                high_contributors = []
                for rnode in ranking_nodes:
                    if rnode.entity and rnode.entity.lower() not in ("全量", ""):
                        if rnode.value and rnode.value > 0:
                            high_contributors.append(rnode)

                # Find entities below average from comparison
                below_avg = []
                for cnode in comparison_nodes:
                    if cnode.entity and "vs" not in cnode.finding_title.lower():
                        below_avg.append(cnode)

                if decline_signaled and high_contributors:
                    evidence = [EvidenceItem(
                        finding_id=gnode.id, finding_title=gnode.finding_title,
                        package_index=gnode.package_index,
                    )]
                    top_entity = high_contributors[0]
                    evidence.append(EvidenceItem(
                        finding_id=top_entity.id, finding_title=top_entity.finding_title,
                        package_index=top_entity.package_index,
                    ))

                    conclusions.append(InferredConclusion(
                        id=str(uuid.uuid4()),
                        category=ConclusionCategory.ROOT_CAUSE,
                        title=f"整体下滑中，「{top_entity.entity}」贡献最高，是关键影响因子",
                        description=f"整体增长率{gnode.value:+.1f}%，「{top_entity.entity}」作为贡献最高的实体，其表现直接影响整体趋势。建议重点关注该实体的经营状况。",
                        confidence=0.85,
                        evidence_strength=EvidenceStrength.MODERATE,
                        evidence_items=evidence,
                        evidence_count=len(evidence),
                        source_package_indices=list(set(e.package_index for e in evidence)),
                        related_finding_ids=[gnode.id, top_entity.id],
                    ))

        # Strategy B: Cross-entity comparison - best vs worst
        best_entities = [n for n in comparison_nodes if "最优" in n.finding_title]
        worst_entities = [n for n in comparison_nodes if "最弱" in n.finding_title]
        if best_entities and worst_entities:
            for best in best_entities[:1]:
                for worst in worst_entities[:1]:
                    gap_node = next((n for n in comparison_nodes if "差距" in n.finding_title), None)
                    gap_pct = gap_node.value if gap_node else None
                    gap_str = f"{gap_pct:.0f}%" if gap_pct else "显著"

                    evidence = [
                        EvidenceItem(finding_id=best.id, finding_title=best.finding_title,
                                     package_index=best.package_index),
                        EvidenceItem(finding_id=worst.id, finding_title=worst.finding_title,
                                     package_index=worst.package_index),
                    ]
                    conclusions.append(InferredConclusion(
                        id=str(uuid.uuid4()),
                        category=ConclusionCategory.INSIGHT,
                        title=f"实体间差异{gap_str}，「{best.entity}」表现最优，「{worst.entity}」最弱",
                        description=f"数据显示实体间在显著差异。「{best.entity}」作为标杆，其经验可推广至其他实体。",
                        confidence=0.80,
                        evidence_count=len(evidence),
                        evidence_items=evidence,
                        source_package_indices=list(set(e.package_index for e in evidence)),
                        related_finding_ids=[best.id, worst.id],
                    ))

        return conclusions
