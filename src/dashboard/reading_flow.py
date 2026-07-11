"""
Reading Flow —— Dashboard 阅读顺序规划

核心职责：
- 定义用户浏览 Dashboard 的推荐阅读路径
- 不是 Widget 顺序，而是 Section 顺序
- 根据 CompositionStrategy 的 flow_type 和 Section 组成自动生成

设计原则：
- 阅读流是 Section 级别，不是 Widget 级别
- 不同 Dashboard 类型有不同的阅读流
- Reading Flow 不包含 Grid 位置信息

标准阅读流：
- Executive: Overview → Main → Comparison → Monitoring → Detail
- Analytical: Overview → Main → Comparison → Detail
- Monitoring: Overview → Monitoring → Main → Detail
"""

from __future__ import annotations
from typing import List, Dict, Any

from src.dashboard.composition_schema import (
    BlueprintSection, BlueprintSectionRole, ReadingFlow, FlowStep,
)
from src.dashboard.composition_rules import CompositionStrategy


# ============================================================
# Flow Type → Section Order Mapping
# ============================================================

FLOW_SECTION_ORDER: Dict[str, List[BlueprintSectionRole]] = {
    "executive": [
        BlueprintSectionRole.OVERVIEW,
        BlueprintSectionRole.MAIN_ANALYSIS,
        BlueprintSectionRole.COMPARISON,
        BlueprintSectionRole.MONITORING,
        BlueprintSectionRole.DETAIL,
    ],
    "analytical": [
        BlueprintSectionRole.OVERVIEW,
        BlueprintSectionRole.MAIN_ANALYSIS,
        BlueprintSectionRole.COMPARISON,
        BlueprintSectionRole.RANKING,
        BlueprintSectionRole.DISTRIBUTION,
        BlueprintSectionRole.GEOGRAPHIC,
        BlueprintSectionRole.DETAIL,
    ],
    "monitoring": [
        BlueprintSectionRole.OVERVIEW,
        BlueprintSectionRole.MONITORING,
        BlueprintSectionRole.MAIN_ANALYSIS,
        BlueprintSectionRole.DETAIL,
    ],
}


# ============================================================
# Reading Flow Builder
# ============================================================

class ReadingFlowBuilder:
    """阅读流构建器——根据 Section 和 Strategy 自动生成 ReadingFlow

    使用方式：
        builder = ReadingFlowBuilder()
        flow = builder.build(sections, strategy)
    """

    # Section role → 阅读目的描述
    SECTION_PURPOSE_MAP: Dict[str, str] = {
        "overview": "首先了解全局状态和核心指标",
        "main_analysis": "接着深入了解核心趋势和关键发现",
        "comparison": "然后比较不同维度的差异和排名",
        "ranking": "查看各维度的高低排名与集中度",
        "distribution": "分析数据的分布特征和集中度",
        "geographic": "了解区域维度的地理分布差异",
        "monitoring": "关注异常预警和风险信号",
        "detail": "最后查看辅助分析和细节信息",
    }

    def build(self, sections: List[BlueprintSection],
              strategy: CompositionStrategy) -> ReadingFlow:
        """构建阅读流

        Args:
            sections: BlueprintSection 列表（已规划）
            strategy: 选择的组合策略

        Returns:
            ReadingFlow
        """
        flow_type = strategy.flow_type or "analytical"

        # Step 1: 确定标准阅读顺序
        standard_order = FLOW_SECTION_ORDER.get(flow_type, FLOW_SECTION_ORDER["analytical"])

        # Step 2: 只保留实际存在的 Section
        existing_roles: Dict[BlueprintSectionRole, BlueprintSection] = {}
        for sec in sections:
            existing_roles[sec.role] = sec

        # Step 3: 按标准顺序生成 FlowStep
        steps: List[FlowStep] = []
        order = 1
        for role in standard_order:
            section = existing_roles.get(role)
            if section:
                purpose = self.SECTION_PURPOSE_MAP.get(role.value, section.purpose)
                step = FlowStep(
                    section_id=section.id,
                    role=role.value,
                    title=section.title,
                    purpose=purpose,
                    order=order,
                )
                steps.append(step)
                order += 1

        # Step 4: 处理不在标准顺序中的 Section（按 priority 排序追加）
        covered_roles = {step.role for step in steps}
        remaining = [sec for sec in sections if sec.role.value not in covered_roles]
        remaining.sort(key=lambda s: s.priority)

        for sec in remaining:
            purpose = self.SECTION_PURPOSE_MAP.get(sec.role.value, sec.purpose)
            step = FlowStep(
                section_id=sec.id,
                role=sec.role.value,
                title=sec.title,
                purpose=purpose,
                order=order,
            )
            steps.append(step)
            order += 1

        return ReadingFlow(
            steps=steps,
            flow_type=flow_type,
        )
