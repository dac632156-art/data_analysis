"""
Rule: Cross Analysis: Concentration x Risk

Cross-analysis: when high concentration coexists with negative signals,
flag it as a structural risk.
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


class CrossConcentrationRiskRule(BaseRule):
    """Cross Analysis: Concentration x Risk

    Strategy:
    1. Check for high concentration (HHI > 1800 or CR3 > 50%)
    2. Check for any negative signals (decline, anomaly, risk)
    3. If both present, flag as structural risk
    """
    name = "cross_concentration_risk"
    description = "Cross Analysis: Concentration x Risk - high concentration + negative signal = structural risk"
    category = "cross_analysis"

    def evaluate(self, graph: "BusinessFactGraph",
                 packages: List["AnalysisPackage"]) -> List["InferredConclusion"]:
        conclusions = []

        concentration_nodes = graph.get_nodes_by_category("concentration")
        growth_nodes = graph.get_nodes_by_category("growth")
        risk_nodes = graph.get_nodes_by_category("risk")
        anomaly_nodes = graph.get_nodes_by_category("anomaly")

        # Check for high concentration
        high_concentration = False
        hhi_value = None
        cr3_value = None
        for n in concentration_nodes:
            if n.value is not None:
                if "hhi" in n.finding_title.lower() and n.value > 1800:
                    high_concentration = True
                    hhi_value = n.value
                if n.value > 0.5 and "top3" in n.finding_title.lower():
                    cr3_value = n.value

        if not high_concentration:
            return conclusions

        # Check for negative signals
        has_decline = any(
            g.value is not None and g.value < 0 for g in growth_nodes
        )
        has_risk = len(risk_nodes) > 0
        has_anomaly = len(anomaly_nodes) > 0

        negative_signals = []
        if has_decline:
            negative_signals.extend(growth_nodes)
        if has_risk:
            negative_signals.extend(risk_nodes)
        if has_anomaly:
            negative_signals.extend(anomaly_nodes)

        if negative_signals:
            evidence = [EvidenceItem(
                finding_id=n.id, finding_title=n.finding_title,
                package_index=n.package_index,
            ) for n in concentration_nodes[:2] + negative_signals[:2]]

            risk_desc_parts = [f"HHI={hhi_value:.0f}" if hhi_value else ""]
            if cr3_value:
                risk_desc_parts.append(f"CR3={cr3_value*100:.1f}%")

            conclusions.append(InferredConclusion(
                id=str(uuid.uuid4()),
                category=ConclusionCategory.RISK,
                title=f"结构性风险：高集中度（{', '.join(risk_desc_parts)}）且存在负面信号",
                description=(
                    f"数据集中度较高（{', '.join(risk_desc_parts)}），"
                    f"同时检测到负面信号。"
                    f"高集中度意味着少数实体主导整体表现，"
                    f"任何负面变化都会被放大。建议分散业务风险。"
                ),
                confidence=0.85,
                evidence_strength=EvidenceStrength.MODERATE if len(evidence) >= 2 else EvidenceStrength.WEAK,
                evidence_items=evidence,
                evidence_count=len(evidence),
                source_package_indices=list(set(e.package_index for e in evidence)),
                related_finding_ids=[e.finding_id for e in evidence],
            ))

        return conclusions
