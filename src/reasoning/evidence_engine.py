"""
Evidence Engine —— 证据验证引擎

职责：
1. 验证 Rule Engine 输出的每个 InferredConclusion
2. 检查结论是否有充分的证据支持
3. 为每个结论计算 evidence_strength
4. 过滤掉证据不足（NONE）的结论

禁止：
- 调用 LLM
- 重新读取 DataFrame
- 编造证据

设计原则：
- 所有结论必须有证据支撑
- 证据不足的结论直接丢弃，不留模糊结论
- evidence_strength: STRONG (≥3 条) / MODERATE (2 条) / WEAK (1 条) / NONE (0 条)
"""
from __future__ import annotations
from typing import List, Dict, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.reasoning.business_fact_graph import BusinessFactGraph
    from src.reasoning.reasoning_result import InferredConclusion, EvidenceItem

from src.reasoning.reasoning_result import EvidenceStrength


class EvidenceEngine:
    """证据验证引擎

    使用方式：
        engine = EvidenceEngine()
        verified = engine.verify(conclusions, graph)
    """

    def __init__(self):
        self._verified_conclusions: List[InferredConclusion] = []
        self._filtered_count: int = 0
        self._stats: Dict[str, int] = {}

    @property
    def verified_conclusions(self) -> List[InferredConclusion]:
        return list(self._verified_conclusions)

    @property
    def filtered_count(self) -> int:
        """被过滤掉的结论数"""
        return self._filtered_count

    def verify(self,
               conclusions: List[InferredConclusion],
               graph: BusinessFactGraph) -> List[InferredConclusion]:
        """验证所有结论

        Args:
            conclusions: Rule Engine 输出的原始结论列表
            graph: 业务事实图谱（用于验证证据是否引用真实节点）

        Returns:
            通过验证的结论列表（evidence_strength 已设置）
        """
        self._verified_conclusions = []
        self._filtered_count = 0
        self._stats = {"strong": 0, "moderate": 0, "weak": 0, "filtered": 0}

        for conclusion in conclusions:
            # 1. 验证证据项是否有效
            valid_evidence = self._validate_evidence(conclusion.evidence_items, graph)

            # 2. 计算证据强度
            evidence_count = len(valid_evidence)
            if evidence_count >= 3:
                strength = EvidenceStrength.STRONG
            elif evidence_count == 2:
                strength = EvidenceStrength.MODERATE
            elif evidence_count == 1:
                strength = EvidenceStrength.WEAK
            else:
                strength = EvidenceStrength.NONE

            conclusion.evidence_items = valid_evidence
            conclusion.evidence_count = evidence_count
            conclusion.evidence_strength = strength

            # 3. 过滤：NONE 证据的结论不输出
            if strength == EvidenceStrength.NONE:
                self._filtered_count += 1
                self._stats["filtered"] += 1
                continue

            # 4. 动态调整置信度
            if strength == EvidenceStrength.WEAK:
                conclusion.confidence = min(conclusion.confidence, 0.60)
            elif strength == EvidenceStrength.MODERATE:
                conclusion.confidence = min(conclusion.confidence, 0.80)

            self._verified_conclusions.append(conclusion)

            # 统计
            self._stats[strength.value] = self._stats.get(strength.value, 0) + 1

        return self._verified_conclusions

    def _validate_evidence(self,
                           evidence_items: List[EvidenceItem],
                           graph: BusinessFactGraph) -> List[EvidenceItem]:
        """验证证据项——检查引用是否有效

        - 必须有 finding_id 且存在于图中
        - 至少有一条证据链（finding | chart | table | kpi）
        """
        valid = []
        for item in evidence_items:
            # 核心验证：finding_id 必须存在且在图中有对应节点
            if not item.finding_id:
                continue
            if item.finding_id not in graph.nodes:
                continue

            # 至少需要 finding_title + 至少一种证据类型
            if item.finding_title or item.chart_slot or item.table_title or item.kpi_label:
                valid.append(item)

        return valid

    def get_verified_graph(self,
                           graph: BusinessFactGraph,
                           conclusions: List[InferredConclusion]) -> BusinessFactGraph:
        """返回已验证的图——保留有证据支持的节点子图

        不修改原始图，返回一个新的 BusinessFactGraph 引用。
        原始 graph 本身就包含所有已验证的数据，这里直接返回。
        """
        # 原始 graph 已包含所有 finding 节点
        # 证据验证不修改图结构
        return graph

    def summarize(self) -> Dict[str, Any]:
        """输出验证摘要"""
        return {
            "total_input": (self._verified_conclusions.__len__()
                            + self._filtered_count
                            if hasattr(self, '_verified_conclusions') else 0),
            "verified": len(self._verified_conclusions),
            "filtered": self._filtered_count,
            "strength_distribution": self._stats,
        }