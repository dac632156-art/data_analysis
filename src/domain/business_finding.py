"""
BusinessFinding —— 业务发现领域模型（Domain Model）

这是整个分析平台唯一的业务发现模型。所有模块统一围绕 BusinessFinding 工作。

设计原则（DDD）：
- 不仅是 dataclass，而是封装业务行为的领域对象
- 字段不可变（frozen=True），通过工厂方法创建
- 提供多种视图方法（to_prompt / to_report / to_dashboard）
- 支持合并、证据链接、置信度评估
"""

from __future__ import annotations
from dataclasses import dataclass, field, replace
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import uuid
import math


# ============================================================
# 枚举类型
# ============================================================

class Direction(str, Enum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    CRITICAL = "critical"    # 需要立即行动
    HIGH = "high"            # 需要关注
    MEDIUM = "medium"        # 一般
    LOW = "low"              # 信息性
    INFO = "info"            # 纯信息


class FindingCategory(str, Enum):
    """业务发现分类——与 AnalysisLibrary 的 intent 对应"""
    GROWTH = "growth"
    RANKING = "ranking"
    COMPARISON = "comparison"
    CONCENTRATION = "concentration"
    DISTRIBUTION = "distribution"
    CORRELATION = "correlation"
    ANOMALY = "anomaly"
    RETENTION = "retention"
    STRUCTURE = "structure"
    PROPORTION = "proportion"
    GEO = "geo"
    RISK = "risk"
    OPPORTUNITY = "opportunity"
    INSIGHT = "insight"
    SUMMARY = "summary"
    UNKNOWN = "unknown"


# ============================================================
# 证据引用（值对象）
# ============================================================

@dataclass(frozen=True)
class EvidenceRef:
    """证据引用——轻量级值对象，不持有图表/表格/KPI对象本身

    只保存引用标识（slot / title / label），由消费方按需查找。
    """
    chart_slots: Tuple[str, ...] = ()     # ChartData.slot
    table_titles: Tuple[str, ...] = ()    # TableData.title
    kpi_labels: Tuple[str, ...] = ()      # KPIItem.label

    def is_empty(self) -> bool:
        return not self.chart_slots and not self.table_titles and not self.kpi_labels

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chart_slots": list(self.chart_slots),
            "table_titles": list(self.table_titles),
            "kpi_labels": list(self.kpi_labels),
        }


# ============================================================
# BusinessFinding 领域模型
# ============================================================

@dataclass(frozen=True)
class BusinessFinding:
    """业务发现领域模型

    不可变（frozen=True）：保证数据一致性，修改通过 replace() 创建新实例。

    字段分为三类：
    - 标识层：id, analysis_type, category
    - 事实层：title, description, metric, dimension, entity, value, unit, direction
    - 解释层：severity, confidence, business_meaning, business_impact, recommendation, evidence
    """

    # ========== 标识层 ==========
    id: str                                    # 唯一标识（UUID）
    analysis_type: str                         # "growth_analysis" / "ranking_analysis" / ...
    category: FindingCategory = FindingCategory.UNKNOWN

    # ========== 事实层 ==========
    title: str = ""                            # 简短标题："华东同比下降12%"
    description: str = ""                      # 详细描述（2-3句业务语言）
    metric: str = ""                           # "销售额" / "复购率" / "HHI"
    dimension: str = ""                        # 维度列名
    entity: str = ""                           # 业务实体："华东" / "产品A" / "全量"
    value: Optional[float] = None              # 核心数值（可能是比率或绝对值）
    unit: str = ""                             # "%" / "元" / "次" / "个"
    direction: Direction = Direction.UNKNOWN   # 方向
    change_pct: Optional[float] = None         # 变化率（相对于基准的变化百分比）

    # ========== 解释层 ==========
    severity: Severity = Severity.INFO
    confidence: float = 1.0                    # 0.0-1.0
    business_meaning: str = ""                 # 业务含义："华东市场正在萎缩，可能是竞争加剧或季节性因素"
    business_impact: str = ""                  # 业务影响："若不干预，全年营收可能下降5-8%"
    recommendation: str = ""                   # 可执行建议
    evidence: EvidenceRef = field(default_factory=EvidenceRef)

    # ========== 元数据 ==========
    tags: Tuple[str, ...] = ()                 # 可搜索标签
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ================================================================
    # 行为方法
    # ================================================================

    # ----- 视图方法 -----

    def to_prompt(self) -> str:
        """输出适合 LLM 理解的业务事实（嵌入 Prompt 用）

        格式：结构化自然语言，包含所有关键信息。
        """
        parts = []
        if self.title:
            parts.append(f"[{self.category.value}] {self.title}")
        if self.entity and self.metric:
            val_str = f"{self.value}{self.unit}" if self.value is not None else "N/A"
            dir_str = f"（{self.direction.value}）" if self.direction != Direction.UNKNOWN else ""
            parts.append(f"  指标：{self.metric} | 实体：{self.entity} | 值：{val_str}{dir_str}")
        if self.description:
            parts.append(f"  描述：{self.description}")
        if self.business_meaning:
            parts.append(f"  业务含义：{self.business_meaning}")
        if self.business_impact:
            parts.append(f"  业务影响：{self.business_impact}")
        if self.recommendation:
            parts.append(f"  建议：{self.recommendation}")
        if self.confidence < 1.0:
            parts.append(f"  置信度：{self.confidence:.0%}")
        return "\n".join(parts)

    def to_report(self) -> Dict[str, Any]:
        """输出适合 Professional Report 引用的结构化数据"""
        return {
            "id": self.id,
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "metric": self.metric,
            "entity": self.entity,
            "value": self.value,
            "unit": self.unit,
            "direction": self.direction.value,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "business_meaning": self.business_meaning,
            "business_impact": self.business_impact,
            "recommendation": self.recommendation,
            "evidence": self.evidence.to_dict(),
            "tags": list(self.tags),
        }

    def to_dashboard(self) -> Dict[str, Any]:
        """输出 Dashboard 摘要（精简版）"""
        return {
            "id": self.id,
            "category": self.category.value,
            "title": self.title,
            "entity": self.entity,
            "value": self.value,
            "unit": self.unit,
            "direction": self.direction.value,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "evidence": self.evidence.to_dict(),
        }

    def to_dict(self) -> Dict[str, Any]:
        """完整序列化（含所有字段）"""
        return {
            "id": self.id,
            "analysis_type": self.analysis_type,
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "metric": self.metric,
            "dimension": self.dimension,
            "entity": self.entity,
            "value": self.value,
            "unit": self.unit,
            "direction": self.direction.value,
            "change_pct": self.change_pct,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "business_meaning": self.business_meaning,
            "business_impact": self.business_impact,
            "recommendation": self.recommendation,
            "evidence": self.evidence.to_dict(),
            "tags": list(self.tags),
            "metadata": self.metadata,
        }

    # ----- 合并方法 -----

    @staticmethod
    def merge(findings: List[BusinessFinding]) -> BusinessFinding:
        """合并多个同类 Finding 为一个摘要 Finding

        策略：
        - 取第一个的 category / analysis_type / metric / dimension
        - 合并 tags
        - entity 设为 "综合"（aggregated）
        - 取最高 severity
        - 平均 confidence
        - business_meaning / impact / recommendation 合并为摘要文本
        """
        if not findings:
            raise ValueError("Cannot merge empty list")
        if len(findings) == 1:
            return findings[0]

        first = findings[0]
        all_tags = set()
        max_severity = Severity.INFO
        avg_confidence = 0.0
        titles = []
        meanings = []
        impacts = []
        recs = []

        for f in findings:
            all_tags.update(f.tags)
            titles.append(f.title)
            if f.business_meaning:
                meanings.append(f.business_meaning)
            if f.business_impact:
                impacts.append(f.business_impact)
            if f.recommendation:
                recs.append(f.recommendation)
            avg_confidence += f.confidence
            # 按严重程度排序：CRITICAL 最严重，INFO 最轻
            sev_order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]
            if sev_order.index(f.severity) < sev_order.index(max_severity):
                max_severity = f.severity

        avg_confidence = round(avg_confidence / len(findings), 2)

        return BusinessFinding(
            id=str(uuid.uuid4()),
            analysis_type=first.analysis_type,
            category=first.category,
            title=f"综合分析：{first.metric}相关发现（{len(findings)}条）",
            description="；".join(titles),
            metric=first.metric,
            dimension=first.dimension,
            entity="综合",
            confidence=avg_confidence,
            severity=max_severity,
            business_meaning="\n".join(meanings) if meanings else "",
            business_impact="\n".join(impacts) if impacts else "",
            recommendation="\n".join(recs) if recs else "",
            tags=tuple(sorted(all_tags)),
        )

    # ----- 证据链接方法 -----

    def link_evidence(
        self,
        chart_slots: Optional[List[str]] = None,
        table_titles: Optional[List[str]] = None,
        kpi_labels: Optional[List[str]] = None,
    ) -> BusinessFinding:
        """建立 Finding → Chart/Table/KPI 的证据引用关系

        返回新的 BusinessFinding（因为 frozen=True）。
        """
        new_evidence = EvidenceRef(
            chart_slots=tuple(chart_slots or []),
            table_titles=tuple(table_titles or []),
            kpi_labels=tuple(kpi_labels or []),
        )
        return replace(self, evidence=new_evidence)

    # ----- 工厂辅助 -----

    def with_evidence(self, evidence: EvidenceRef) -> BusinessFinding:
        """替换证据引用"""
        return replace(self, evidence=evidence)

    def with_severity(self, severity: Severity) -> BusinessFinding:
        return replace(self, severity=severity)

    def with_confidence(self, confidence: float) -> BusinessFinding:
        return replace(self, confidence=confidence)