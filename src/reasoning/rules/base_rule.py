"""
BaseRule —— 规则基类

所有推理规则继承此基类。
规则不包含业务常量，通过 AnalysisPackage 中的 BusinessFinding 推断。
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.reasoning.business_fact_graph import BusinessFactGraph
    from src.reasoning.reasoning_result import InferredConclusion
    from src.analysis_templates.base import AnalysisPackage


class BaseRule(ABC):
    """推理规则基类"""

    name: str = "base_rule"
    description: str = ""
    category: str = "general"      # "cross_analysis" | "root_cause" | "risk" | "opportunity"

    @abstractmethod
    def evaluate(self, graph: BusinessFactGraph,
                 packages: List[AnalysisPackage]) -> List[InferredConclusion]:
        """评估规则——返回推理结论列表"""
        ...

    def __repr__(self):
        return f"<Rule {self.name}>"