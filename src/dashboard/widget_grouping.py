"""
Widget Grouping —— 按 business_topic + visual_role 聚合 Widget

核心职责：
- 将 SemanticWidget 按 business_topic 聚合为 WidgetGroup
- 每个分组包含：同一业务主题的所有 Widget
- 分组信息用于 Composition Planner 决定 Dashboard 的业务领域组成

设计原则：
- 按 business_topic 一级聚合
- 每个 Group 记录其包含的 visual_roles 和 analytical_roles
- Group 的重要性 = 组内 Widget 的平均 importance_score
- Group 的优先级 = 组内最高 priority_level
"""

from __future__ import annotations
from typing import List, Dict, Any
from collections import Counter

from src.dashboard.semantic_models import (
    SemanticWidget, BusinessTopic, PriorityLevel,
)
from src.dashboard.composition_schema import WidgetGroup


# ============================================================
# Business Topic 中文映射
# ============================================================

TOPIC_TITLE_MAP: Dict[str, str] = {
    "sales": "销售分析",
    "customer": "客户分析",
    "product": "产品分析",
    "finance": "财务分析",
    "operation": "运营分析",
    "growth": "增长分析",
    "risk": "风险分析",
    "efficiency": "效率分析",
    "quality": "质量分析",
    "general": "综合分析",
}


# ============================================================
# Widget Grouping Engine
# ============================================================

class WidgetGroupingEngine:
    """Widget 业务主题分组引擎

    使用方式：
        engine = WidgetGroupingEngine()
        groups = engine.group(widgets)
    """

    def group(self, widgets: List[SemanticWidget]) -> List[WidgetGroup]:
        """按 business_topic 对 Widget 分组

        Args:
            widgets: SemanticWidget 列表

        Returns:
            WidgetGroup 列表（按 avg_importance 降序）
        """
        if not widgets:
            return []

        # Step 1: 按 business_topic 分桶
        topic_buckets: Dict[str, List[SemanticWidget]] = {}
        for w in widgets:
            topic = w.business_topic.value
            if topic not in topic_buckets:
                topic_buckets[topic] = []
            topic_buckets[topic].append(w)

        # Step 2: 为每个 topic 创建 WidgetGroup
        groups: List[WidgetGroup] = []
        for topic, topic_widgets in topic_buckets.items():
            group = self._build_group(topic, topic_widgets)
            groups.append(group)

        # Step 3: 按 avg_importance 降序排序
        groups.sort(key=lambda g: g.avg_importance, reverse=True)

        return groups

    def _build_group(self, topic: str, widgets: List[SemanticWidget]) -> WidgetGroup:
        """构建单个 WidgetGroup"""
        # 按 importance 降序排列
        sorted_widgets = sorted(widgets, key=lambda w: w.importance_score, reverse=True)

        # 提取 visual_roles 和 analytical_roles
        visual_roles = list(set(w.visual_role.value for w in sorted_widgets))
        analytical_roles = list(set(w.analytical_role.value for w in sorted_widgets))

        # 计算平均 importance
        avg_importance = sum(w.importance_score for w in sorted_widgets) / len(sorted_widgets)

        # 确定分组优先级（取组内最高）
        priority_order = {PriorityLevel.HERO: 0, PriorityLevel.MAJOR: 1, PriorityLevel.MINOR: 2}
        highest_priority = min(
            sorted_widgets,
            key=lambda w: priority_order.get(w.priority_level, 3)
        )
        group_priority = highest_priority.priority_level.value

        # 分组标题
        title = TOPIC_TITLE_MAP.get(topic, topic)

        return WidgetGroup(
            id=f"group_{topic}",
            topic=topic,
            title=title,
            widget_ids=[w.id for w in sorted_widgets],
            visual_roles=visual_roles,
            analytical_roles=analytical_roles,
            avg_importance=avg_importance,
            priority_level=group_priority,
        )
