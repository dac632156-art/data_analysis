"""
Widget Linkage Builder —— Widget 联动关系图构建引擎

核心职责：
- 根据 business_topic + related_widgets 建立 Widget Link Graph
- 生成 WidgetLinkageRule（联动关系描述）
- 支持 One-to-One / One-to-Many / Many-to-Many 联动类型
- 联动关系是抽象描述，不是具体数据联动

设计原则：
- 不使用 if-else 硬编码
- 使用 InteractionRuleEngine 评估规则
- 同一 business_topic 的 Widget 自动建立联动
- related_widgets 中的关系也纳入联动

生产方：DashboardInteractionEngine
消费方：Renderer（理解 Widget 间联动关系）
"""

from __future__ import annotations
from typing import List, Dict, Any, Set
import uuid

from src.dashboard.layout_schema import DashboardSchema, WidgetSlot
from src.dashboard.interaction_schema import (
    WidgetLinkageRule, LinkageType,
)
from src.dashboard.interaction_rules import (
    InteractionRuleEngine,
    _extract_filter_fields,
)


# ============================================================
# Widget Linkage Builder
# ============================================================

class WidgetLinkageBuilder:
    """Widget 联动关系图构建引擎

    使用方式：
        builder = WidgetLinkageBuilder(rule_engine)
        linkages = builder.build(schema)
    """

    def __init__(self, rule_engine: Optional[InteractionRuleEngine] = None):
        self._rule_engine = rule_engine or InteractionRuleEngine()

    def build(self, schema: DashboardSchema) -> List[WidgetLinkageRule]:
        """从 DashboardSchema 构建 Widget 联动关系图

        流程：
        1. 按 business_topic 分组 Widget
        2. 同一 topic 内的 Widget 建立联动
        3. 按 shared filter field 建立跨 topic 联动
        4. 判断联动类型（One-to-One / One-to-Many / Many-to-Many）
        5. 生成 WidgetLinkageRule

        Args:
            schema: DashboardSchema

        Returns:
            WidgetLinkageRule 列表
        """
        rules: List[WidgetLinkageRule] = []

        # Phase 1: 按 business_topic 分组
        topic_groups: Dict[str, List[WidgetSlot]] = {}
        for w in schema.widgets:
            metadata = w.metadata or {}
            topic = metadata.get("business_topic", "")
            if topic:
                if topic not in topic_groups:
                    topic_groups[topic] = []
                topic_groups[topic].append(w)

        # 同一 topic 内的 Widget 建立联动
        for topic, group_widgets in topic_groups.items():
            if len(group_widgets) < 2:
                continue

            # 找 topic 内 importance 最高的 Widget 作为 core
            core_widget = max(group_widgets, key=lambda w: w.importance_score)
            other_widgets = [w for w in group_widgets if w.widget_id != core_widget.widget_id]

            # 判断联动类型
            linkage_type = self._determine_linkage_type(core_widget, other_widgets)

            rules.append(WidgetLinkageRule(
                id=f"lg_{topic}",
                source_widgets=[core_widget.widget_id],
                target_widgets=[w.widget_id for w in other_widgets],
                linkage_type=linkage_type,
                business_topic=topic,
                description=f"{topic} 领域：{core_widget.title} → {', '.join(w.title for w in other_widgets)}",
            ))

        # Phase 2: 按 shared filter field 建立跨 topic 联动
        field_groups: Dict[str, List[WidgetSlot]] = {}
        for w in schema.widgets:
            fields = _extract_filter_fields(w)
            for f in fields:
                if f == "time":
                    continue  # time 是 global，不适合做 linkage
                if f not in field_groups:
                    field_groups[f] = []
                field_groups[f].append(w)

        for field, field_widgets in field_groups.items():
            if len(field_widgets) < 2:
                continue

            # 检查是否跨 topic
            topics = set()
            for w in field_widgets:
                metadata = w.metadata or {}
                topic = metadata.get("business_topic", "")
                if topic:
                    topics.add(topic)

            # 只生成跨 topic 联动（同 topic 的已在 Phase 1 处理）
            if len(topics) < 2:
                continue

            # 重要性最高的 Widget 作为 source
            core_widget = max(field_widgets, key=lambda w: w.importance_score)
            others = [w for w in field_widgets if w.widget_id != core_widget.widget_id]

            linkage_type = self._determine_linkage_type(core_widget, others)

            rules.append(WidgetLinkageRule(
                id=f"lg_field_{field}",
                source_widgets=[core_widget.widget_id],
                target_widgets=[w.widget_id for w in others],
                linkage_type=linkage_type,
                business_topic="",
                description=f"共享 {field} 字段：{core_widget.title} → {', '.join(w.title for w in others)}",
            ))

        return rules

    # ============================================================
    # Linkage Type Determination
    # ============================================================

    @staticmethod
    def _determine_linkage_type(
        core: WidgetSlot,
        others: List[WidgetSlot],
    ) -> LinkageType:
        """判断联动类型

        规则：
        - 1 source → 1 target → ONE_TO_ONE
        - 1 source → 多个 target → ONE_TO_MANY
        - 多个 source → 多个 target → MANY_TO_MANY
        """
        if len(others) == 1:
            return LinkageType.ONE_TO_ONE
        elif len(others) <= 4:
            return LinkageType.ONE_TO_MANY
        else:
            return LinkageType.MANY_TO_MANY
