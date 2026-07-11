"""
ReasoningResult —— 业务推理结果数据模型

Business Reasoning Pipeline 的最终输出。
Professional Report / Dashboard / API 的统一消费接口。

设计原则：
- 不包含原始 DataFrame
- 不重复 AnalysisPackage 的内容（通过引用关联）
- 所有结论都关联证据
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


# ===== 枚举 =====

class ConclusionCategory(str, Enum):
    ROOT_CAUSE = "root_cause"
    RISK = "risk"
    OPPORTUNITY = "opportunity"
    RECOMMENDATION = "recommendation"
    INSIGHT = "insight"


class EvidenceStrength(str, Enum):
    STRONG = "strong"        # ≥3 个证据
    MODERATE = "moderate"   # 2 个证据
    WEAK = "weak"           # 1 个证据
    NONE = "none"           # 无证据（不应输出）


# ===== 证据项 =====

@dataclass
class EvidenceItem:
    """单条证据——关联到具体 AnalysisPackage 中的 Finding/Chart/Table/KPI"""
    finding_id: str = ""                # BusinessFinding.id
    finding_title: str = ""             # BusinessFinding.title
    chart_slot: Optional[str] = None    # ChartData.slot
    table_title: Optional[str] = None   # TableData.title
    kpi_label: Optional[str] = None     # KPIItem.label
    package_index: int = 0              # 来自第几个 AnalysisPackage


# ===== 推断结论 =====

@dataclass
class InferredConclusion:
    """推理产生的结论——Rule Engine 发现 + Evidence Engine 验证"""
    id: str = ""
    category: ConclusionCategory = ConclusionCategory.INSIGHT
    title: str = ""                     # "华东市场下滑是整体下降的根因"
    description: str = ""               # 2-4 句详细描述
    confidence: float = 0.0             # 综合置信度
    evidence_strength: EvidenceStrength = EvidenceStrength.NONE
    evidence_count: int = 0
    evidence_items: List[EvidenceItem] = field(default_factory=list)
    source_package_indices: List[int] = field(default_factory=list)
    related_finding_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        import dataclasses
        d = dataclasses.asdict(self)
        d["category"] = self.category.value
        d["evidence_strength"] = self.evidence_strength.value
        return d


# ===== ReasoningResult =====

@dataclass
class ReasoningResult:
    """业务推理管道的最终输出——Professional Report 的唯一输入

    不包含原始数据，只包含经过推理和验证的结论。
    """

    # ========== 标识 ==========
    id: str = ""
    title: str = ""                     # 报告标题："H1 2024 华东市场分析报告"
    created_at: str = ""                # ISO 时间戳

    # ========== 执行摘要 ==========
    executive_summary: str = ""         # 3-5 段，LLM 生成的管理层摘要

    # ========== LLM 叙事 ==========
    narrative: str = ""                 # 完整的业务叙事文本（LLM 生成）
    narrative_sections: List[Dict[str, str]] = field(default_factory=list)

    # ========== 关键发现 ==========
    key_findings: List[Dict[str, Any]] = field(default_factory=list)

    # ========== 推断结论 ==========
    root_causes: List[InferredConclusion] = field(default_factory=list)
    risks: List[InferredConclusion] = field(default_factory=list)
    opportunities: List[InferredConclusion] = field(default_factory=list)
    recommendations: List[InferredConclusion] = field(default_factory=list)
    business_impacts: List[InferredConclusion] = field(default_factory=list)

    # ========== 证据映射 ==========
    evidence_mapping: Dict[str, List[EvidenceItem]] = field(default_factory=dict)
    # key: conclusion_id → value: [EvidenceItem, ...]

    # ========== 元数据 ==========
    confidence: float = 0.0             # 整体推理置信度
    packages_consumed: int = 0          # 消费的 AnalysisPackage 数量
    findings_consumed: int = 0          # 处理的 BusinessFinding 总数
    rules_fired: List[str] = field(default_factory=list)
    execution_time: float = 0.0

    # ========== 便捷方法 ==========

    def get_all_conclusions(self) -> List[InferredConclusion]:
        return (self.root_causes + self.risks +
                self.opportunities + self.recommendations +
                self.business_impacts)

    def get_high_confidence(self, threshold: float = 0.7) -> List[InferredConclusion]:
        return [c for c in self.get_all_conclusions() if c.confidence >= threshold]

    def get_by_category(self, cat: ConclusionCategory) -> List[InferredConclusion]:
        return [c for c in self.get_all_conclusions() if c.category == cat]

    def to_dict(self) -> Dict[str, Any]:
        import dataclasses
        d = dataclasses.asdict(self)
        d["root_causes"] = [rc.to_dict() for rc in self.root_causes]
        d["risks"] = [r.to_dict() for r in self.risks]
        d["opportunities"] = [o.to_dict() for o in self.opportunities]
        d["recommendations"] = [r.to_dict() for r in self.recommendations]
        d["business_impacts"] = [bi.to_dict() for bi in self.business_impacts]
        return d