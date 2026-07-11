"""
Reasoning Pipeline —— 业务推理管道

完整的推理流程编排器。

流程：
    List[AnalysisPackage]
        ↓
    Rule Engine → BusinessFactGraph + InferredConclusion[]
        ↓
    Evidence Engine → verified InferredConclusion[]
        ↓
    LLM Reasoner → executive_summary + narrative + recommendations
        ↓
    ReasoningResult

三个引擎独立运作，Pipeline 只负责调度。
"""
from __future__ import annotations
from typing import List, Optional, Callable, Dict, Any, TYPE_CHECKING
import time

if TYPE_CHECKING:
    from src.reasoning.reasoning_result import ReasoningResult
    from src.analysis_templates.base import AnalysisPackage

from src.reasoning.rule_engine import RuleEngine
from src.reasoning.evidence_engine import EvidenceEngine
from src.reasoning.llm_reasoner import LLMReasoner
from src.reasoning.reasoning_result import ReasoningResult


class ReasoningPipeline:
    """业务推理管道

    使用方式：
        # 无 LLM
        pipeline = ReasoningPipeline()
        result = pipeline.run(packages)

        # 有 LLM
        pipeline = ReasoningPipeline(llm_callable=my_llm_func)
        result = pipeline.run(packages)

        # 自定义规则
        pipeline = ReasoningPipeline(rules=[MyRule()])
        result = pipeline.run(packages)
    """

    def __init__(self,
                 rules: Optional[List] = None,
                 llm_callable: Optional[Callable[[str], str]] = None):
        """
        Args:
            rules: 自定义规则列表（不提供则使用 BUILTIN_RULES）
            llm_callable: 可选的 LLM 调用函数
        """
        self._rule_engine = RuleEngine(rules=rules)
        self._evidence_engine = EvidenceEngine()
        self._llm_reasoner = LLMReasoner(llm_callable=llm_callable)
        self._last_result: Optional[ReasoningResult] = None

    @property
    def last_result(self) -> Optional[ReasoningResult]:
        return self._last_result

    def run(self,
            packages: List[AnalysisPackage],
            title: str = "") -> ReasoningResult:
        """执行完整的推理流程

        Args:
            packages: AnalysisPackage 列表
            title: 报告标题

        Returns:
            ReasoningResult: 完整的推理结果
        """
        start_time = time.time()

        # Phase 1: Rule Engine —— 构建事实图谱 + 推理结论
        raw_conclusions = self._rule_engine.run(packages)
        graph = self._rule_engine.get_graph()

        # Phase 2: Evidence Engine —— 验证结论
        verified_conclusions = self._evidence_engine.verify(raw_conclusions, graph)

        # Phase 3: LLM Reasoner —— 生成叙事
        result = self._llm_reasoner.reason(verified_conclusions, graph, title=title)

        # 补充元数据
        result.rules_fired = self._rule_engine.fired_rules
        result.packages_consumed = len(packages)
        result.execution_time = round(time.time() - start_time, 3)

        self._last_result = result
        return result

    def run_sync(self,
                 packages: List[AnalysisPackage],
                 title: str = "") -> ReasoningResult:
        """同步运行（与 run 相同，但明确标识同步模式）"""
        return self.run(packages, title)

    # ===== 便捷访问 =====

    def get_graph(self):
        """获取当前的事实图谱"""
        return self._rule_engine.get_graph()

    def get_rule_engine(self) -> RuleEngine:
        return self._rule_engine

    def get_evidence_engine(self) -> EvidenceEngine:
        return self._evidence_engine

    def get_llm_reasoner(self) -> LLMReasoner:
        return self._llm_reasoner

    # ===== 摘要 =====

    def summarize(self) -> Dict[str, Any]:
        """输出完整管线摘要"""
        return {
            "rule_engine": self._rule_engine.summarize(),
            "evidence_engine": self._evidence_engine.summarize(),
            "result": self._last_result.to_dict() if self._last_result else None,
        }