"""
Rule: Root Cause: Anomaly Root Cause

Derive root cause insights from anomaly detection findings,
enriched with growth and ranking context.
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


class RootCauseAnomalyRule(BaseRule):
    """Root Cause: Anomaly"""
    name = "root_cause_anomaly"
    description = "Root Cause: Anomaly - derive insights from anomaly findings"
    category = "root_cause"

    def evaluate(self, graph: "BusinessFactGraph",
                 packages: List["AnalysisPackage"]) -> List["InferredConclusion"]:
        conclusions = []

        anomaly_nodes = graph.get_nodes_by_category("anomaly")
        growth_nodes = graph.get_nodes_by_category("growth")

        for node in anomaly_nodes:
            evidence = [EvidenceItem(
                finding_id=node.id, finding_title=node.finding_title,
                package_index=node.package_index,
            )]

            # Add growth context
            growth_context = ""
            for g in growth_nodes[:1]:
                evidence.append(EvidenceItem(
                    finding_id=g.id, finding_title=g.finding_title,
                    package_index=g.package_index,
                ))
                if g.value is not None:
                    growth_context = f"同时整体增长率为{g.value:+.1f}%。"

            conclusions.append(InferredConclusion(
                id=str(uuid.uuid4()),
                category=ConclusionCategory.ROOT_CAUSE,
                title=f"异常检测：{node.finding_title[:50]}",
                description=f"数据中检测到异常波动。{growth_context}建议深入调查异常点的业务背景，判断是否为系统性问题。",
                confidence=0.75,
                evidence_strength=EvidenceStrength.WEAK if len(evidence) < 2 else EvidenceStrength.MODERATE,
                evidence_items=evidence,
                evidence_count=len(evidence),
                source_package_indices=list(set(e.package_index for e in evidence)),
                related_finding_ids=[node.id],
            ))

        return conclusions
