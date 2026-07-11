"""
Global Filter Generator —— 全局筛选器生成引擎

核心职责：
- 从 DashboardSchema 的 WidgetSlot 中识别公共筛选字段
- 根据 Rule Engine 规则决定哪些字段成为 Global Filter
- 自动计算 Filter Scope（global/section/widget）
- 不重复生成相同 Filter

设计原则：
- 不使用 if-else
- 使用 InteractionRuleEngine 评估规则
- 全局筛选器只覆盖 ≥2 Widget 共享的字段
- time 字段始终为 global scope
- region/product 按 widget 覆盖数量决定 scope

生产方：DashboardInteractionEngine
消费方：Renderer（绑定 Global Filter UI）
"""

from __future__ import annotations
from typing import List, Dict, Any, Set
import uuid

from src.dashboard.layout_schema import DashboardSchema, WidgetSlot
from src.dashboard.interaction_schema import (
    FilterRule, FilterType, FilterScope, InteractionPriority,
)
from src.dashboard.interaction_rules import (
    InteractionRuleEngine, InteractionRule,
    FILTER_FIELD_LABELS, FILTER_FIELD_WIDGET_TYPES,
    _extract_filter_fields,
)


# ============================================================
# Scope Resolution —— 筛选器作用范围决策
# ============================================================

# 字段覆盖比例 → scope 映射
# >= 50% Widget 覆盖 → global
# >= 20% Widget 覆盖 → section（如果同一 Section）
# < 20% → widget（仅自身）

SCOPE_THRESHOLDS = {
    "global": 0.50,     # 覆盖 ≥50% Widget → 全局
    "section": 0.20,    # 覆盖 ≥20% Widget → Section 级
    "widget": 0.00,     # 覆盖 <20% Widget → Widget 级
}


def resolve_filter_scope(
    field_name: str,
    covering_widgets: List[WidgetSlot],
    all_widget_count: int,
    schema: DashboardSchema,
) -> FilterScope:
    """根据字段覆盖度决定筛选器作用范围

    特殊规则：
    - time → 强制 global
    - 其他字段 → 按覆盖比例决定

    Args:
        field_name: 筛选字段名
        covering_widgets: 支持该字段的 Widget 列表
        all_widget_count: Dashboard 总 Widget 数
        schema: DashboardSchema（用于检查 section 分布）

    Returns:
        FilterScope
    """
    # time 字段强制 global
    if field_name == "time":
        return FilterScope.GLOBAL

    coverage_ratio = len(covering_widgets) / all_widget_count if all_widget_count > 0 else 0

    # >= 50% → global
    if coverage_ratio >= SCOPE_THRESHOLDS["global"]:
        return FilterScope.GLOBAL

    # >= 20% → section（检查是否集中在同一 Section）
    if coverage_ratio >= SCOPE_THRESHOLDS["section"]:
        section_ids = set(w.section_id for w in covering_widgets)
        # 如果所有支持 Widget 都在同一 Section → section scope
        if len(section_ids) == 1:
            return FilterScope.SECTION
        # 跨多个 Section → 仍然 global
        return FilterScope.GLOBAL

    # < 20% → widget
    return FilterScope.WIDGET


# ============================================================
# Global Filter Generator
# ============================================================

class GlobalFilterGenerator:
    """全局筛选器生成引擎

    使用方式：
        generator = GlobalFilterGenerator(rule_engine)
        filters = generator.generate(schema)
    """

    def __init__(self, rule_engine: Optional[InteractionRuleEngine] = None):
        self._rule_engine = rule_engine or InteractionRuleEngine()

    def generate(self, schema: DashboardSchema) -> List[FilterRule]:
        """从 DashboardSchema 生成全局筛选器

        流程：
        1. 评估 Global Filter 规则（Rule Engine）
        2. 收集每个 Widget 的 supported_filters 字段
        3. 统计共享字段（≥2 Widget 共有）
        4. 计算 Filter Scope
        5. 生成 FilterRule

        Args:
            schema: DashboardSchema

        Returns:
            FilterRule 列表
        """
        if not schema.widgets:
            return []

        # 评估规则（哪些全局筛选器类型应该生成）
        matched_rules = self._rule_engine.evaluate_rules(schema, rule_type="global_filter")

        # 收集字段 → Widget 映射
        field_widgets: Dict[str, List[WidgetSlot]] = {}
        for w in schema.widgets:
            fields = _extract_filter_fields(w)
            for f in fields:
                if f not in field_widgets:
                    field_widgets[f] = []
                field_widgets[f].append(w)

        # 生成筛选器
        rules: List[FilterRule] = []
        seen_fields: Set[str] = set()

        # 从命中的规则中提取目标字段
        rule_fields = set()
        for rule in matched_rules:
            if rule.rule_id.startswith("gf_"):
                # 从 rule_id 提取字段名：gf_time_global → time
                field_name = rule.rule_id.replace("gf_", "").replace("_global", "")
                rule_fields.add(field_name)

        # 遍历共享字段（≥2 Widget）
        all_widget_count = len(schema.widgets)
        for field_name, widgets in field_widgets.items():
            if len(widgets) < 2:
                continue
            if field_name in seen_fields:
                continue

            # 检查是否在规则命中列表中
            # 如果没有命中任何 gf_ 规则但字段覆盖 ≥2 Widget → 也生成（兜底）
            should_generate = (
                field_name in rule_fields or
                len(widgets) >= 2
            )

            if not should_generate:
                continue

            seen_fields.add(field_name)

            # 计算 Scope
            scope = resolve_filter_scope(field_name, widgets, all_widget_count, schema)

            # 标签和控件类型
            label = FILTER_FIELD_LABELS.get(field_name, field_name)
            widget_type = FILTER_FIELD_WIDGET_TYPES.get(field_name, "dropdown")

            # target_widgets 和 target_sections
            target_widgets = sorted([w.widget_id for w in widgets])
            target_sections = []
            if scope == FilterScope.SECTION:
                section_ids = set(w.section_id for w in widgets)
                target_sections = sorted(section_ids)

            rules.append(FilterRule(
                id=f"gf_{field_name}",
                name=label,
                field=field_name,
                filter_type=FilterType.GLOBAL,
                scope=scope,
                widget_type=widget_type,
                target_widgets=target_widgets,
                target_sections=target_sections,
                priority=InteractionPriority.GLOBAL_FILTER,
            ))

        # 按覆盖 widget 数量降序
        rules.sort(key=lambda r: len(r.target_widgets), reverse=True)
        return rules
