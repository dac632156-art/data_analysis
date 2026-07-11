"""
Rule Engine —— 规则引擎

职责：
1. 加载所有推理规则
2. 从多个 AnalysisPackage 构建 BusinessFactGraph
3. 依次评估每条规则
4. 汇总规则产生的 InferredConclusion

禁止：
- 调用 LLM
- 重新读取 DataFrame
- 重新计算业务指标
- 重新生成图表

Rule Engine 只消费 AnalysisPackage。
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any, TYPE_CHECKING
import time

if TYPE_CHECKING:
    from src.reasoning.business_fact_graph import BusinessFactGraph
    from src.reasoning.reasoning_result import InferredConclusion
    from src.analysis_templates.base import AnalysisPackage
    from src.reasoning.rules.base_rule import BaseRule

from src.reasoning.business_fact_graph import BusinessFactGraph
from src.reasoning.rules import BUILTIN_RULES


class RuleEngine:
    """规则引擎

    使用方式：
        engine = RuleEngine()
        conclusions = engine.run(packages)
        graph = engine.get_graph()
    """

    def __init__(self, rules: Optional[List[BaseRule]] = None):
        """
        Args:
            rules: 自定义规则列表，默认使用 BUILTIN_RULES
        """
        self._rules: List[BaseRule] = list(rules) if rules else list(BUILTIN_RULES)
        self._graph: Optional[BusinessFactGraph] = None
        self._fired_rules: List[str] = []
        self._all_conclusions: List[InferredConclusion] = []

    @property
    def graph(self) -> Optional[BusinessFactGraph]:
        return self._graph

    @property
    def fired_rules(self) -> List[str]:
        return list(self._fired_rules)

    @property
    def conclusions(self) -> List[InferredConclusion]:
        return list(self._all_conclusions)

    def run(self, packages: List[AnalysisPackage]) -> List[InferredConclusion]:
        """执行所有规则

        Args:
            packages: 分析包列表

        Returns:
            所有规则产生的 InferredConclusion 列表
        """
        # 1. 构建 BusinessFactGraph
        self._graph = BusinessFactGraph(name="reasoning_graph")
        for i, pkg in enumerate(packages):
            self._graph.add_nodes_from_package(pkg, package_index=i)

        # 2. 依次评估每条规则
        self._all_conclusions = []
        self._fired_rules = []

        for rule in self._rules:
            try:
                rule_conclusions = rule.evaluate(self._graph, packages)
                if rule_conclusions:
                    self._fired_rules.append(rule.name)
                    self._all_conclusions.extend(rule_conclusions)
            except Exception as e:
                # 单条规则失败不影响其他规则
                self._fired_rules.append(f"{rule.name}:ERROR:{e}")

        return self._all_conclusions

    def get_conclusions_by_category(self, category_str: str) -> List[InferredConclusion]:
        """按类别获取结论"""
        return [c for c in self._all_conclusions if c.category.value == category_str]

    def get_root_causes(self) -> List[InferredConclusion]:
        return self.get_conclusions_by_category("root_cause")

    def get_risks(self) -> List[InferredConclusion]:
        return self.get_conclusions_by_category("risk")

    def get_opportunities(self) -> List[InferredConclusion]:
        return self.get_conclusions_by_category("opportunity")

    def get_insights(self) -> List[InferredConclusion]:
        return self.get_conclusions_by_category("insight")

    def get_recommendations(self) -> List[InferredConclusion]:
        return self.get_conclusions_by_category("recommendation")

    def add_rule(self, rule: BaseRule):
        """动态添加规则"""
        self._rules.append(rule)

    def remove_rule(self, rule_name: str):
        """按名称移除规则"""
        self._rules = [r for r in self._rules if r.name != rule_name]

    def get_graph(self) -> Optional[BusinessFactGraph]:
        return self._graph

    def summarize(self) -> Dict[str, Any]:
        """输出引擎运行摘要"""
        return {
            "total_rules": len(self._rules),
            "fired_rules": self._fired_rules,
            "total_conclusions": len(self._all_conclusions),
            "root_causes": len(self.get_root_causes()),
            "risks": len(self.get_risks()),
            "opportunities": len(self.get_opportunities()),
            "graph": self._graph.to_summary() if self._graph else {},
        }