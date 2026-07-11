"""
Section Planner —— 自动规划 Dashboard Section

核心职责：
- 根据 SemanticWidget 的 recommended_section、visual_role、business_topic
- 自动规划 Dashboard 应该由哪些区域组成
- Section 不固定——根据实际 Widget 内容动态生成

设计原则：
- 有地图才生成 Geographic Section
- 有异常才生成 Monitoring Section
- Widget 全是 KPI 就只生成 Overview Section
- 不要"填满"——没有对应 Widget 就不生成 Section
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter

from src.dashboard.semantic_models import (
    SemanticWidget, BusinessTopic, VisualRole, AnalyticalRole,
    PriorityLevel, RecommendedSection, WidgetRelation, RelationType,
)
from src.dashboard.composition_schema import (
    BlueprintSection, BlueprintSectionRole,
)


# ============================================================
# Section Template —— Section 角色定义
# ============================================================

SECTION_TEMPLATES: Dict[BlueprintSectionRole, Dict[str, Any]] = {
    BlueprintSectionRole.OVERVIEW: {
        "title": "核心指标概览",
        "purpose": "展示核心经营指标和全局状态",
        "priority": 1,
        "visual_roles": [VisualRole.OVERVIEW_METRIC, VisualRole.SUMMARY_CARD],
        "recommended_sections": [RecommendedSection.OVERVIEW],
    },
    BlueprintSectionRole.MAIN_ANALYSIS: {
        "title": "主要分析",
        "purpose": "展示核心趋势和关键发现",
        "priority": 2,
        "visual_roles": [VisualRole.PRIMARY_TREND, VisualRole.GEOGRAPHIC],
        "recommended_sections": [RecommendedSection.MAIN_ANALYSIS],
    },
    BlueprintSectionRole.COMPARISON: {
        "title": "比较分析",
        "purpose": "展示不同维度比较与排名",
        "priority": 3,
        "visual_roles": [VisualRole.COMPARISON, VisualRole.RANKING, VisualRole.COMPOSITION],
        "recommended_sections": [RecommendedSection.COMPARISON],
    },
    BlueprintSectionRole.DISTRIBUTION: {
        "title": "分布分析",
        "purpose": "展示数据分布特征与集中度",
        "priority": 4,
        "visual_roles": [VisualRole.DISTRIBUTION, VisualRole.CONCENTRATION],
        "recommended_sections": [RecommendedSection.DETAIL],
    },
    BlueprintSectionRole.RANKING: {
        "title": "排名分析",
        "purpose": "展示 TOP 排名与集中度",
        "priority": 4,
        "visual_roles": [VisualRole.RANKING],
        "recommended_sections": [RecommendedSection.COMPARISON],
    },
    BlueprintSectionRole.GEOGRAPHIC: {
        "title": "区域分析",
        "purpose": "展示地理分布差异与区域热点",
        "priority": 3,
        "visual_roles": [VisualRole.GEOGRAPHIC],
        "recommended_sections": [RecommendedSection.MAIN_ANALYSIS],
    },
    BlueprintSectionRole.MONITORING: {
        "title": "异常监控",
        "purpose": "监测异常离群点和风险预警",
        "priority": 4,
        "visual_roles": [VisualRole.WARNING],
        "recommended_sections": [RecommendedSection.MONITORING],
    },
    BlueprintSectionRole.DETAIL: {
        "title": "详细信息",
        "purpose": "展示辅助分析和细节信息",
        "priority": 5,
        "visual_roles": [VisualRole.DETAIL, VisualRole.CORRELATION],
        "recommended_sections": [RecommendedSection.DETAIL],
    },
}


# ============================================================
# Section Planner —— 自动规划 Dashboard Section
# ============================================================

class SectionPlanner:
    """自动根据 SemanticWidget 规划 Dashboard Section

    算法：
    1. 收集所有 Widget 的 recommended_section 值
    2. 根据推荐区域映射到 BlueprintSectionRole
    3. 只为有 Widget 的区域创建 Section
    4. 合并过小的 Section（可选）
    5. 按优先级排序

    使用方式：
        planner = SectionPlanner()
        sections = planner.plan(widgets)
    """

    # recommended_section → BlueprintSectionRole 映射
    RECOMMENDED_TO_BLUEPRINT: Dict[str, BlueprintSectionRole] = {
        "overview": BlueprintSectionRole.OVERVIEW,
        "main_analysis": BlueprintSectionRole.MAIN_ANALYSIS,
        "comparison": BlueprintSectionRole.COMPARISON,
        "detail": BlueprintSectionRole.DETAIL,
        "monitoring": BlueprintSectionRole.MONITORING,
    }

    # visual_role → BlueprintSectionRole 额外映射（用于没有 recommended_section 的 Widget）
    VISUAL_ROLE_TO_BLUEPRINT: Dict[str, BlueprintSectionRole] = {
        "overview_metric": BlueprintSectionRole.OVERVIEW,
        "summary_card": BlueprintSectionRole.OVERVIEW,
        "primary_trend": BlueprintSectionRole.MAIN_ANALYSIS,
        "geographic": BlueprintSectionRole.GEOGRAPHIC,
        "comparison": BlueprintSectionRole.COMPARISON,
        "ranking": BlueprintSectionRole.RANKING,
        "composition": BlueprintSectionRole.COMPARISON,
        "concentration": BlueprintSectionRole.DISTRIBUTION,
        "distribution": BlueprintSectionRole.DISTRIBUTION,
        "correlation": BlueprintSectionRole.DETAIL,
        "warning": BlueprintSectionRole.MONITORING,
        "detail": BlueprintSectionRole.DETAIL,
    }

    def plan(self, widgets: List[SemanticWidget]) -> List[BlueprintSection]:
        """根据 SemanticWidget 列表自动规划 Section

        Args:
            widgets: SemanticWidget 列表（已按 importance_score 降序）

        Returns:
            BlueprintSection 列表（按 priority 升序 = 越重要越靠前）
        """
        if not widgets:
            return []

        # Step 1: 将每个 Widget 映射到 BlueprintSectionRole
        widget_section_map: Dict[str, BlueprintSectionRole] = {}
        for w in widgets:
            role = self._map_widget_to_section(w)
            widget_section_map[w.id] = role

        # Step 2: 按 SectionRole 聚合 Widget
        section_widgets: Dict[BlueprintSectionRole, List[SemanticWidget]] = {}
        for w in widgets:
            role = widget_section_map[w.id]
            if role not in section_widgets:
                section_widgets[role] = []
            section_widgets[role].append(w)

        # Step 3: 合并小 Section（只有1个 Minor Widget 的独立 Section 合入 Detail）
        section_widgets = self._merge_small_sections(section_widgets)

        # Step 4: 为每个 SectionRole 创建 BlueprintSection
        sections = self._build_sections(section_widgets)

        # Step 5: 按 priority 排序
        sections.sort(key=lambda s: s.priority)

        return sections

    def _map_widget_to_section(self, widget: SemanticWidget) -> BlueprintSectionRole:
        """将单个 Widget 映射到最合适的 BlueprintSectionRole

        策略优先级：
        1. Widget 的 recommended_section（Semantic Widget Generator 已指定）
        2. Widget 的 visual_role（降级映射）
        3. 默认 Detail
        """
        # Strategy 1: recommended_section 精确映射
        rec_sec = widget.recommended_section.value
        mapped = self.RECOMMENDED_TO_BLUEPRINT.get(rec_sec)
        if mapped:
            return mapped

        # Strategy 2: visual_role 降级映射
        vis_role = widget.visual_role.value
        mapped = self.VISUAL_ROLE_TO_BLUEPRINT.get(vis_role)
        if mapped:
            return mapped

        # Fallback: Detail
        return BlueprintSectionRole.DETAIL

    def _merge_small_sections(
        self,
        section_widgets: Dict[BlueprintSectionRole, List[SemanticWidget]]
    ) -> Dict[BlueprintSectionRole, List[SemanticWidget]]:
        """合并只有 1 个 Minor Widget 的独立 Section

        例如：只有 1 个 Minor 的 Distribution Section → 合入 Detail
        但 Overview / Main / Comparison 不合并（即使只有 1 个 Hero）
        """
        merge_candidates = [
            BlueprintSectionRole.DISTRIBUTION,
            BlueprintSectionRole.RANKING,
            BlueprintSectionRole.GEOGRAPHIC,
            BlueprintSectionRole.MONITORING,
        ]

        for role in merge_candidates:
            widgets = section_widgets.get(role, [])
            if len(widgets) == 1 and widgets[0].priority_level == PriorityLevel.MINOR:
                # 移入 Detail
                section_widgets.setdefault(BlueprintSectionRole.DETAIL, []).extend(widgets)
                section_widgets.pop(role, None)

        return section_widgets

    def _build_sections(
        self,
        section_widgets: Dict[BlueprintSectionRole, List[SemanticWidget]]
    ) -> List[BlueprintSection]:
        """为每个 SectionRole 创建 BlueprintSection"""
        sections: List[BlueprintSection] = []

        for role, widgets in section_widgets.items():
            template = SECTION_TEMPLATES.get(role, {
                "title": "分析区域",
                "purpose": "展示分析结果",
                "priority": 5,
            })

            # Widget 按重要性排序
            sorted_widgets = sorted(widgets, key=lambda w: w.importance_score, reverse=True)
            widget_ids = [w.id for w in sorted_widgets]

            # 计算摘要统计
            visual_role_counts = Counter(w.visual_role.value for w in sorted_widgets)
            topic_counts = Counter(w.business_topic.value for w in sorted_widgets)
            avg_importance = sum(w.importance_score for w in sorted_widgets) / len(sorted_widgets)

            dominant_visual_role = visual_role_counts.most_common(1)[0][0] if visual_role_counts else ""
            dominant_topic = topic_counts.most_common(1)[0][0] if topic_counts else ""

            section = BlueprintSection(
                id=f"sec_{role.value}",
                role=role,
                title=template["title"],
                purpose=template["purpose"],
                priority=template["priority"],
                widget_ids=widget_ids,
                dominant_visual_role=dominant_visual_role,
                dominant_business_topic=dominant_topic,
                avg_importance=avg_importance,
            )
            sections.append(section)

        return sections
