"""
Rule: Root Cause: Decline Root Cause

Identify entities driving overall decline by cross-referencing
growth signals with ranking and comparison data.
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


class RootCauseDeclineRule(BaseRule):
    """Root Cause: Decline"""
    name = "root_cause_decline"
    description = "Root Cause: Decline - identify entities driving overall decline"
    category = "root_cause"

    def evaluate(self, graph: "BusinessFactGraph",
                 packages: List["AnalysisPackage"]) -> List["InferredConclusion"]:
        conclusions = []

        growth_nodes = graph.get_nodes_by_category("growth")
        ranking_nodes = graph.get_nodes_by_category("ranking")
        comparison_nodes = graph.get_nodes_by_category("comparison")
        structure_nodes = graph.get_nodes_by_category("structure")

        # Check overall growth direction
        for gnode in growth_nodes:
            if gnode.value is None:
                continue

            if gnode.value < 0:
                # Declining: find worst entity from comparison
                worst = [n for n in comparison_nodes if "最弱" in n.finding_title or "低于" in n.finding_title]

                for w in worst[:2]:
                    evidence = [
                        EvidenceItem(
                            finding_id=gnode.id, finding_title=gnode.finding_title,
                            package_index=gnode.package_index,
                        ),
                        EvidenceItem(
                            finding_id=w.id, finding_title=w.finding_title,
                            package_index=w.package_index,
                        ),
                    ]
                    conclusions.append(InferredConclusion(
                        id=str(uuid.uuid4()),
                        category=ConclusionCategory.ROOT_CAUSE,
                        title=f"整体下滑{abs(gnode.value):.1f}%，「{w.entity}」是主要拖累因素",
                        description=f"整体增长率{gnode.value:+.1f}%。「{w.entity}」表现最弱，是下滑的主要贡献者。建议深入分析该实体的业务数据，找出下滑原因。",
                        confidence=0.85,
                        evidence_strength=EvidenceStrength.MODERATE,
                        evidence_items=evidence,
                        evidence_count=len(evidence),
                        source_package_indices=list(set(e.package_index for e in evidence)),
                        related_finding_ids=[gnode.id, w.id],
                    ))

            elif gnode.value > 0:
                # Growing: still provide insight about best/worst spread
                best = [n for n in comparison_nodes if "最优" in n.finding_title]
                worst = [n for n in comparison_nodes if "最弱" in n.finding_title]
                if best and worst:
                    evidence = [
                        EvidenceItem(finding_id=best[0].id, finding_title=best[0].finding_title, package_index=best[0].package_index),
                        EvidenceItem(finding_id=worst[0].id, finding_title=worst[0].finding_title, package_index=worst[0].package_index),
                    ]
                    conclusions.append(InferredConclusion(
                        id=str(uuid.uuid4()),
                        category=ConclusionCategory.INSIGHT,
                        title=f"整体增长{gnode.value:+.1f}%，但「{worst[0].entity}」表现偏弱，拖累整体",
                        description=f"虽然整体增长，但「{worst[0].entity}」表现不佳，存在提升空间。改善该实体可进一步提升整体表现。",
                        confidence=0.75,
                        evidence_count=len(evidence),
                        evidence_items=evidence,
                        source_package_indices=list(set(e.package_index for e in evidence)),
                        related_finding_ids=[best[0].id, worst[0].id],
                    ))

        return conclusions
