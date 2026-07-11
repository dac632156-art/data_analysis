"""
Highlight Generator —— 高亮交互生成引擎

核心职责：
- 根据 Widget 的 visual_role + chart_type 自动生成高亮规则
- ranking/bar → TOP 3 高亮
- anomaly/scatter → 异常标记
- trend/line → 高增长点 + 趋势拐点
- KPI → 阈值监控

设计原则：
- 不使用 if-else 硬编码
- 使用 InteractionRuleEngine 评估规则
- 高亮不是过滤——只标记，不改变数据
- Hover Highlight：鼠标放到某个数据点，其它图自动高亮同名数据点

生产方：DashboardInteractionEngine
消费方：Renderer（绑定 Highlight UI）
"""

from __future__ import annotations
from typing import List, Dict, Any, Set
import uuid

from src.dashboard.layout_schema import DashboardSchema, WidgetSlot
from src.dashboard.interaction_schema import (
    HighlightRule, HighlightType, InteractionPriority,
)
from src.dashboard.interaction_rules import (
    InteractionRuleEngine,
    _extract_filter_fields,
)


# ============================================================
# Highlight Rule Definitions —— 高亮规则类型定义
# ============================================================

# chart_type / visual_role → highlight rules 映射
HIGHLIGHT_RULE_MAP: Dict[str, List[Dict[str, Any]]] = {
    # ranking/bar → TOP 3
    "ranking": [
        {"rule_type": HighlightType.TOP_N, "params": {"n": 3}, "label": "高亮 TOP 3"},
    ],
    "bar": [
        {"rule_type": HighlightType.TOP_N, "params": {"n": 3}, "label": "高亮 TOP 3"},
    ],
    # anomaly/scatter → 异常标记
    "anomaly": [
        {"rule_type": HighlightType.ANOMALY, "params": {"threshold": 3.0, "method": "zscore"}, "label": "标记异常点"},
    ],
    "scatter": [
        {"rule_type": HighlightType.ANOMALY, "params": {"threshold": 3.0, "method": "zscore"}, "label": "标记异常点"},
    ],
    # trend/line → 高增长 + 趋势拐点
    "trend": [
        {"rule_type": HighlightType.HIGH_GROWTH, "params": {"threshold_pct": 10}, "label": "标记高增长点"},
        {"rule_type": HighlightType.TREND_CHANGE, "params": {}, "label": "标记趋势拐点"},
    ],
    "line": [
        {"rule_type": HighlightType.HIGH_GROWTH, "params": {"threshold_pct": 10}, "label": "标记高增长点"},
        {"rule_type": HighlightType.TREND_CHANGE, "params": {}, "label": "标记趋势拐点"},
    ],
}

# visual_role → highlight rules 映射（补充 chart_type 无法覆盖的情况）
VISUAL_ROLE_HIGHLIGHT_MAP: Dict[str, List[Dict[str, Any]]] = {
    "ranking": [
        {"rule_type": HighlightType.TOP_N, "params": {"n": 3}, "label": "高亮 TOP 3"},
    ],
    "warning": [
        {"rule_type": HighlightType.ANOMALY, "params": {"threshold": 3.0, "method": "zscore"}, "label": "标记异常点"},
    ],
    "primary_trend": [
        {"rule_type": HighlightType.HIGH_GROWTH, "params": {"threshold_pct": 10}, "label": "标记高增长点"},
    ],
    "overview_metric": [
        {"rule_type": HighlightType.THRESHOLD, "params": {"good_above": None, "warn_below": None}, "label": "阈值监控"},
    ],
}


# ============================================================
# Hover Highlight Generator —— 跨图 Hover 高亮
# ============================================================

def generate_hover_highlights(schema: DashboardSchema) -> List[HighlightRule]:
    """生成跨图 Hover 高亮规则

    规则：如果多个 Widget 共享同一非 time 字段，
    当鼠标 hover 到某个数据点时，其它图自动高亮同名数据点。

    不是过滤。只是 Highlight。
    """
    rules: List[HighlightRule] = []

    # 找共享字段的 Widget 组
    field_widgets: Dict[str, List[WidgetSlot]] = {}
    for w in schema.widgets:
        fields = _extract_filter_fields(w)
        for f in fields:
            if f == "time":
                continue  # time 不适合做 hover highlight
            if f not in field_widgets:
                field_widgets[f] = []
            field_widgets[f].append(w)

    # 对每个共享字段组生成 hover highlight
    for field, widgets in field_widgets.items():
        if len(widgets) < 2:
            continue

        # 只为可交互的图表生成
        for source in widgets:
            source_id = source.widget_id
            targets = [w.widget_id for w in widgets if w.widget_id != source_id]
            if not targets:
                continue

            rules.append(HighlightRule(
                id=f"hl_hover_{source_id}_{field}",
                widget_id=source_id,
                rule_type=HighlightType.THRESHOLD,
                params={
                    "hover_field": field,
                    "target_widgets": targets,
                    "interaction": "hover_highlight",
                },
                label=f"Hover 高亮 {field}",
                priority=InteractionPriority.HIGHLIGHT,
            ))

    return rules


# ============================================================
# Highlight Generator
# ============================================================

class HighlightGenerator:
    """高亮交互生成引擎

    使用方式：
        generator = HighlightGenerator(rule_engine)
        rules = generator.generate(schema)
    """

    def __init__(self, rule_engine: Optional[InteractionRuleEngine] = None):
        self._rule_engine = rule_engine or InteractionRuleEngine()

    def generate(self, schema: DashboardSchema) -> List[HighlightRule]:
        """从 DashboardSchema 生成高亮规则

        流程：
        1. 评估 Highlight 规则（Rule Engine）
        2. 对每个 Widget 根据 chart_type/visual_role 生成内置高亮
        3. 生成跨图 Hover Highlight

        Args:
            schema: DashboardSchema

        Returns:
            HighlightRule 列表
        """
        rules: List[HighlightRule] = []

        # Phase 1: 每个 Widget 的内置高亮
        for w in schema.widgets:
            widget_rules = self._generate_widget_highlights(w)
            rules.extend(widget_rules)

        # Phase 2: 跨图 Hover Highlight
        hover_rules = generate_hover_highlights(schema)
        rules.extend(hover_rules)

        return rules

    def _generate_widget_highlights(self, widget: WidgetSlot) -> List[HighlightRule]:
        """为单个 Widget 生成高亮规则"""
        rules: List[HighlightRule] = []
        wid = widget.widget_id

        # 根据 chart_type 匹配
        chart_type = widget.chart_type or ""
        if chart_type in HIGHLIGHT_RULE_MAP:
            for hl_def in HIGHLIGHT_RULE_MAP[chart_type]:
                # importance_score 影响优先级
                priority = InteractionPriority.HIGHLIGHT
                if widget.importance_score >= 70:
                    priority += 10

                rules.append(HighlightRule(
                    id=f"hl_{wid}_{hl_def['rule_type'].value}",
                    widget_id=wid,
                    rule_type=hl_def["rule_type"],
                    params=hl_def.get("params", {}),
                    label=hl_def.get("label", ""),
                    priority=priority,
                ))

        # 根据 visual_role 匹配（补充）
        metadata = widget.metadata or {}
        visual_role = metadata.get("visual_role", "")
        if visual_role in VISUAL_ROLE_HIGHLIGHT_MAP:
            # 防止重复（如果 chart_type 已覆盖）
            existing_types = {r.rule_type for r in rules}
            for hl_def in VISUAL_ROLE_HIGHLIGHT_MAP[visual_role]:
                if hl_def["rule_type"] not in existing_types:
                    rules.append(HighlightRule(
                        id=f"hl_{wid}_{visual_role}_{hl_def['rule_type'].value}",
                        widget_id=wid,
                        rule_type=hl_def["rule_type"],
                        params=hl_def.get("params", {}),
                        label=hl_def.get("label", ""),
                        priority=InteractionPriority.HIGHLIGHT,
                    ))

        # KPI → 阈值监控
        if widget.widget_type == "kpi":
            has_threshold = any(r.rule_type == HighlightType.THRESHOLD for r in rules)
            if not has_threshold:
                rules.append(HighlightRule(
                    id=f"hl_{wid}_threshold",
                    widget_id=wid,
                    rule_type=HighlightType.THRESHOLD,
                    params={"good_above": None, "warn_below": None},
                    label="阈值监控",
                    priority=InteractionPriority.HIGHLIGHT,
                ))

        return rules
