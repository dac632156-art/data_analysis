"""
Domain Model Layer —— 业务发现领域模型

统一的分析结果数据模型，所有模块围绕 BusinessFinding 工作。

模块结构：
- business_finding.py    核心领域模型（BusinessFinding + EvidenceRef + 枚举）
- finding_factory.py     工厂（统一创建入口）

使用方式：
    from src.domain import BusinessFinding, FindingFactory, FindingCategory, Direction, Severity

    factory = FindingFactory("growth_analysis")
    finding = factory.growth(entity="华东", metric="销售额", value=-12.0, direction=Direction.DOWN)
    finding = finding.link_evidence(chart_slots=["trend"], kpi_labels=["同比增长率"])
"""

from src.domain.business_finding import (
    BusinessFinding,
    EvidenceRef,
    FindingCategory,
    Direction,
    Severity,
)
from src.domain.finding_factory import FindingFactory

__all__ = [
    "BusinessFinding",
    "EvidenceRef",
    "FindingCategory",
    "Direction",
    "Severity",
    "FindingFactory",
]