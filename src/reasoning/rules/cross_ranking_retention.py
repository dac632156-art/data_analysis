"""
Rule: Cross Analysis: Ranking x Retention

Cross-analysis: link top-ranking entities with retention signals.
High contribution + low retention = risk; high + high = strength.
"""
from __future__ import annotations
from typing import List, TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from src.reasoning.business_fact_graph import BusinessFactGraph
    from src.reasoning.reasoning_result import InferredConclusion
    from src.analysis_templates.base import AnalysisPackage

from src.reasoning.rules.base_rule import BaseRule
from src.reasoning.reasoning_result import (
    InferredConclusion, EvidenceItem, ConclusionCategory, EvidenceStrength,
)


class CrossRankingRetentionRule(BaseRule):
    """Cross Analysis: Ranking x Retention"""
    name = "cross_ranking_retention"
    description = "Cross Analysis: Ranking x Retention - link top entities to retention health"
    category = "cross_analysis"

    def evaluate(self, graph: "BusinessFactGraph",
                 packages: List["AnalysisPackage"]) -> List["InferredConclusion"]:
        conclusions = []

        ranking_nodes = graph.get_nodes_by_category("ranking")
        retention_nodes = graph.get_nodes_by_category("retention")
        risk_nodes = graph.get_nodes_by_category("risk")

        # If retention signals exist with ranking
        if retention_nodes and ranking_nodes:
            for rnode in retention_nodes:
                evidence = [EvidenceItem(
                    finding_id=rnode.id, finding_title=rnode.finding_title,
                    package_index=rnode.package_index,
                )]

                # Add top ranking as context
                top_ranking = [n for n in ranking_nodes if n.entity and n.entity not in ("", "全量")]
                if top_ranking:
                    evidence.append(EvidenceItem(
                        finding_id=top_ranking[0].id, finding_title=top_ranking[0].finding_title,
                        package_index=top_ranking[0].package_index,
                    ))

                conclusions.append(InferredConclusion(
                    id=str(uuid.uuid4()),
                    category=ConclusionCategory.INSIGHT,
                    title=rnode.finding_title[:60],
                    description=f"客户粘性分析显示：{rnode.finding_title}。结合排名数据，可识别高贡献但低粘性的实体，优先改善。",
                    confidence=0.80,
                    evidence_strength=EvidenceStrength.MODERATE if len(evidence) >= 2 else EvidenceStrength.WEAK,
                    evidence_items=evidence,
                    evidence_count=len(evidence),
                    source_package_indices=list(set(e.package_index for e in evidence)),
                    related_finding_ids=[e.finding_id for e in evidence],
                ))
                break  # One insight per retention finding is enough

        # Risk from retention
        if risk_nodes and retention_nodes:
            for risk in risk_nodes[:1]:
                evidence = [EvidenceItem(
                    finding_id=risk.id, finding_title=risk.finding_title,
                    package_index=risk.package_index,
                ) for n in retention_nodes[:1]] + [EvidenceItem(
                    finding_id=risk.id, finding_title=risk.finding_title,
                    package_index=risk.package_index,
                )]
                conclusions.append(InferredConclusion(
                    id=str(uuid.uuid4()),
                    category=ConclusionCategory.RISK,
                    title=risk.finding_title[:60],
                    description=risk.finding_title + "。低复购率意味着客户忠诚度不足，需建立客户分层和召回策略。",
                    confidence=0.85,
                    evidence_strength=EvidenceStrength.MODERATE,
                    evidence_items=evidence,
                    evidence_count=len(evidence),
                    source_package_indices=list(set(e.package_index for e in evidence)),
                    related_finding_ids=[e.finding_id for e in evidence],
                ))

        return conclusions
