"""
LLM Reasoner —— 自然语言叙事引擎

职责：
1. 基于已验证的业务结论生成 Executive Summary
2. 生成完整的业务叙事（Narrative）
3. 生成结构化的 Recommendations
4. 输出 ReasoningResult 中的自然语言部分

限制（必须遵守）：
- 不能推翻 Rule Engine 的结论
- 不能新增没有证据支持的因果推断
- 不能编造数据、指标
- 所有结论必须引用 VerifiedBusinessGraph 中的内容
- LLM 只负责语言组织和商业表达

设计：
- 接受可选的 llm_callable 函数
- 如果没有 LLM，使用基于规则的方式生成结构化摘要
"""
from __future__ import annotations
from typing import List, Dict, Optional, Any, Callable, TYPE_CHECKING
import time

if TYPE_CHECKING:
    from src.reasoning.business_fact_graph import BusinessFactGraph
    from src.reasoning.reasoning_result import (
        InferredConclusion, ReasoningResult, ConclusionCategory,
    )

from src.reasoning.reasoning_result import (
    ReasoningResult, ConclusionCategory, EvidenceStrength,
)


class LLMReasoner:
    """自然语言叙事引擎

    使用方式：
        # 无 LLM（基于规则生成摘要）
        reasoner = LLMReasoner()
        result = reasoner.reason(verified_conclusions, graph)

        # 有 LLM
        reasoner = LLMReasoner(llm_callable=my_llm_function)
        result = reasoner.reason(verified_conclusions, graph)
    """

    def __init__(self, llm_callable: Optional[Callable[[str], str]] = None):
        """
        Args:
            llm_callable: 可选的 LLM 调用函数，接受 prompt 字符串，返回 response 字符串。
                         如果不提供，使用规则生成摘要。
        """
        self._llm = llm_callable

    def reason(self,
               verified_conclusions: List[InferredConclusion],
               graph: BusinessFactGraph,
               title: str = "") -> ReasoningResult:
        """从已验证的结论生成 ReasoningResult

        Args:
            verified_conclusions: Evidence Engine 验证通过的结论
            graph: 业务事实图谱
            title: 报告标题

        Returns:
            ReasoningResult: 包含 executive_summary、narrative、recommendations
        """
        result = ReasoningResult(
            id=f"reasoning_{int(time.time())}",
            title=title or "业务分析推理结果",
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )

        # 分类整理结论
        root_causes = [c for c in verified_conclusions
                       if c.category == ConclusionCategory.ROOT_CAUSE]
        risks = [c for c in verified_conclusions
                 if c.category == ConclusionCategory.RISK]
        opportunities = [c for c in verified_conclusions
                         if c.category == ConclusionCategory.OPPORTUNITY]
        recommendations = [c for c in verified_conclusions
                           if c.category == ConclusionCategory.RECOMMENDATION]
        insights = [c for c in verified_conclusions
                    if c.category == ConclusionCategory.INSIGHT]
        business_impacts = [c for c in verified_conclusions
                            if c.category not in (
                                ConclusionCategory.ROOT_CAUSE,
                                ConclusionCategory.RISK,
                                ConclusionCategory.OPPORTUNITY,
                                ConclusionCategory.RECOMMENDATION,
                                ConclusionCategory.INSIGHT,
                            )]

        result.root_causes = root_causes
        result.risks = risks
        result.opportunities = opportunities
        result.recommendations = recommendations
        result.business_impacts = business_impacts

        # 构建关键发现
        result.key_findings = self._build_key_findings(verified_conclusions)

        # 构建 Evidence Mapping
        result.evidence_mapping = self._build_evidence_mapping(verified_conclusions)

        # 如果有 LLM，使用 LLM 生成叙事
        if self._llm:
            prompt = self._build_prompt(verified_conclusions, graph, title)
            try:
                response = self._llm(prompt)
                result = self._parse_llm_response(result, response)
            except Exception:
                # LLM 失败时回退到规则生成
                result = self._build_rule_based(result, verified_conclusions, graph)
        else:
            result = self._build_rule_based(result, verified_conclusions, graph)

        # 计算整体置信度
        result.confidence = self._calc_overall_confidence(verified_conclusions)
        result.packages_consumed = len({
            p_idx for c in verified_conclusions
            for p_idx in c.source_package_indices
        })
        result.findings_consumed = len(set(
            fid for c in verified_conclusions
            for fid in c.related_finding_ids
        ))

        return result

    # ===== Prompt 构建 =====

    def _build_prompt(self,
                      conclusions: List[InferredConclusion],
                      graph: BusinessFactGraph,
                      title: str) -> str:
        """构建 LLM prompt——结构化输入，限制 LLM 行为"""
        parts = []
        parts.append("你是一位资深商业分析师。请基于以下**已验证的业务事实**生成分析报告叙事。")
        parts.append("")
        parts.append("## 严格规则")
        parts.append("1. 只能基于以下「已验证结论」中的内容得出结论")
        parts.append("2. 不能编造任何不在结论中的数据、指标或数字")
        parts.append("3. 不能推翻或修改任何已给出的结论")
        parts.append("4. 如果某个结论的证据强度为 WEAK，请在提及它时注明不确定性")
        parts.append("")
        parts.append("## 已验证结论")
        parts.append("")

        for i, c in enumerate(conclusions, 1):
            parts.append(f"### 结论 {i}")
            parts.append(f"- 类别: {c.category.value}")
            parts.append(f"- 标题: {c.title}")
            parts.append(f"- 描述: {c.description}")
            parts.append(f"- 置信度: {c.confidence:.0%}")
            parts.append(f"- 证据强度: {c.evidence_strength.value} ({c.evidence_count}条证据)")
            parts.append("")

        parts.append("## 图谱摘要")
        parts.append(str(graph.to_summary()))
        parts.append("")

        parts.append("## 输出要求")
        parts.append("请严格按以下格式输出（不要输出其他文字）：")
        parts.append("")
        parts.append("### EXECUTIVE_SUMMARY")
        parts.append("(3-4 段管理层摘要，总结核心发现、主要风险和机会)")
        parts.append("")
        parts.append("### NARRATIVE")
        parts.append("(完整的业务叙事，5-8 段，逻辑递进地讲述数据背后的商业故事)")
        parts.append("")
        parts.append("### RECOMMENDATIONS")
        parts.append("(3-5 条具体可执行的建议，每条以 - 开头)")
        parts.append("")
        parts.append("### NARRATIVE_SECTIONS")
        parts.append("(每个 section 为一行 JSON，格式：{\"heading\": \"...\", \"body\": \"...\"})")

        return "\n".join(parts)

    def _parse_llm_response(self, result: ReasoningResult, response: str) -> ReasoningResult:
        """解析 LLM 响应"""
        import re

        # 解析 EXECUTIVE_SUMMARY
        es_match = re.search(r'###\s*EXECUTIVE_SUMMARY\s*\n(.*?)(?=###|\Z)', response, re.DOTALL)
        if es_match:
            result.executive_summary = es_match.group(1).strip()

        # 解析 NARRATIVE
        na_match = re.search(r'###\s*NARRATIVE\s*\n(.*?)(?=###|\Z)', response, re.DOTALL)
        if na_match:
            result.narrative = na_match.group(1).strip()

        # 解析 RECOMMENDATIONS
        rec_match = re.search(r'###\s*RECOMMENDATIONS\s*\n(.*?)(?=###|\Z)', response, re.DOTALL)
        if rec_match:
            rec_text = rec_match.group(1).strip()
            recs = []
            for line in rec_text.split('\n'):
                line = line.strip()
                if line.startswith('-') or line.startswith('*'):
                    recs.append({"heading": "", "body": line.lstrip('- *').strip()})
            result.narrative_sections = recs

        # 解析 NARRATIVE_SECTIONS
        ns_match = re.search(r'###\s*NARRATIVE_SECTIONS\s*\n(.*?)(?=\Z)', response, re.DOTALL)
        if ns_match:
            import json
            sections_text = ns_match.group(1).strip()
            sections = []
            for line in sections_text.split('\n'):
                line = line.strip()
                if line.startswith('{'):
                    try:
                        sections.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            if sections:
                result.narrative_sections = sections

        return result

    # ===== 基于规则的生成（无 LLM 模式） =====

    def _build_rule_based(self,
                          result: ReasoningResult,
                          conclusions: List[InferredConclusion],
                          graph: BusinessFactGraph) -> ReasoningResult:
        """基于规则生成摘要和叙事（无 LLM 回退方案）"""
        root_causes = result.root_causes
        risks = result.risks
        opportunities = result.opportunities

        # Executive Summary
        summary_parts = []

        # 总体概述
        summary_parts.append(
            f"基于 {len(conclusions)} 条已验证业务发现的分析，"
            f"系统识别出 {len(root_causes)} 个根因、{len(risks)} 个风险和 {len(opportunities)} 个机会。"
        )

        # 关键根因
        if root_causes:
            summary_parts.append(f"\n**核心发现**")
            for rc in root_causes[:3]:
                summary_parts.append(f"- {rc.title}（置信度 {rc.confidence:.0%}）")

        # 主要风险
        if risks:
            summary_parts.append(f"\n**主要风险**")
            for r in risks[:3]:
                summary_parts.append(f"- {r.title}（置信度 {r.confidence:.0%}）")

        # 机会
        if opportunities:
            summary_parts.append(f"\n**增长机会**")
            for o in opportunities[:3]:
                summary_parts.append(f"- {o.title}（置信度 {o.confidence:.0%}）")

        result.executive_summary = "\n".join(summary_parts)

        # Narrative
        narrative_parts = []
        narrative_parts.append("## 业务分析叙事\n")

        for i, c in enumerate(conclusions, 1):
            strength_label = {
                EvidenceStrength.STRONG: "确凿证据",
                EvidenceStrength.MODERATE: "较充分证据",
                EvidenceStrength.WEAK: "初步证据",
            }.get(c.evidence_strength, "证据")

            narrative_parts.append(
                f"### 发现 {i}: {c.title}\n"
                f"\n{c.description}\n"
                f"\n*{strength_label}支持 | 置信度 {c.confidence:.0%}*\n"
            )

        result.narrative = "\n".join(narrative_parts)

        # Recommendations
        recs = self._generate_recommendations(root_causes, risks, opportunities)
        result.narrative_sections = recs

        return result

    def _generate_recommendations(self,
                                   root_causes: List[InferredConclusion],
                                   risks: List[InferredConclusion],
                                   opportunities: List[InferredConclusion]) -> List[Dict[str, str]]:
        """基于 Rule Engine 结论自动生成建议"""
        recs = []

        # 基于根因生成建议
        for rc in root_causes[:2]:
            recs.append({
                "heading": f"应对: {rc.title[:30]}",
                "body": f"针对「{rc.title}」，建议深入调查具体原因并制定针对性改进计划。"
            })

        # 基于风险生成建议
        for risk in risks[:2]:
            recs.append({
                "heading": f"防范: {risk.title[:30]}",
                "body": f"为应对「{risk.title}」，建议建立监控预警机制，设置风险应急预案。"
            })

        # 基于机会生成建议
        for opp in opportunities[:2]:
            recs.append({
                "heading": f"把握: {opp.title[:30]}",
                "body": f"抓住「{opp.title}」的机会窗口，建议加大资源投入并加速推进。"
            })

        return recs

    # ===== 辅助方法 =====

    def _build_key_findings(self,
                            conclusions: List[InferredConclusion]) -> List[Dict[str, Any]]:
        """构建关键发现列表"""
        findings = []
        for c in conclusions:
            findings.append({
                "id": c.id,
                "category": c.category.value,
                "title": c.title,
                "description": c.description,
                "confidence": c.confidence,
                "evidence_strength": c.evidence_strength.value,
            })
        return findings

    def _build_evidence_mapping(self,
                                conclusions: List[InferredConclusion]) -> Dict[str, List]:
        """构建证据映射：conclusion_id → evidence_items"""
        mapping = {}
        for c in conclusions:
            mapping[c.id] = c.evidence_items
        return mapping

    def _calc_overall_confidence(self,
                                 conclusions: List[InferredConclusion]) -> float:
        """计算整体置信度"""
        if not conclusions:
            return 0.0
        weights = {
            EvidenceStrength.STRONG: 1.0,
            EvidenceStrength.MODERATE: 0.8,
            EvidenceStrength.WEAK: 0.5,
        }
        total = sum(
            c.confidence * weights.get(c.evidence_strength, 0.5)
            for c in conclusions
        )
        return round(total / len(conclusions), 2)