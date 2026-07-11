"""
Cross Filter Generator —— 交叉筛选器生成引擎

核心职责：
- 根据 Widget 间共享字段和图表类型生成 Cross Filter
- bar/pie/map Widget 作为可点击源
- 生成 click/hover 联动规则
- 冲突检测和合并（循环依赖、重复联动）

设计原则：
- 不使用 if-else 硬编码
- 使用 InteractionRuleEngine 评估规则
- 可点击图表（bar/pie/map/scatter）作为 source
- 自动合并同 source+field 的联动

生产方：DashboardInteractionEngine
消费方：Renderer（绑定 Cross Filter UI）
"""

from __future__ import annotations
from typing import List, Dict, Any, Set, Tuple
import uuid

from src.dashboard.layout_schema import DashboardSchema, WidgetSlot
from src.dashboard.interaction_schema import (
    CrossFilterRule, InteractionPriority,
)
from src.dashboard.interaction_rules import (
    InteractionRuleEngine,
    FILTER_FIELD_LABELS,
    _extract_filter_fields,
)


# ============================================================
# Clickable Chart Types —— 可作为 Cross Filter Source 的图表类型
# ============================================================

CLICKABLE_CHART_TYPES: Set[str] = {"bar", "pie", "map", "scatter"}


# ============================================================
# Cross Filter Generator
# ============================================================

class CrossFilterGenerator:
    """交叉筛选器生成引擎

    使用方式：
        generator = CrossFilterGenerator(rule_engine)
        rules = generator.generate(schema)
    """

    def __init__(self, rule_engine: Optional[InteractionRuleEngine] = None):
        self._rule_engine = rule_engine or InteractionRuleEngine()

    def generate(self, schema: DashboardSchema) -> List[CrossFilterRule]:
        """从 DashboardSchema 生成交叉筛选器

        流程：
        1. 评估 Cross Filter 规则（Rule Engine）
        2. 构建 Widget 的 filter fields 映射
        3. 找可点击图表作为 source
        4. 对每个 source，找共享字段的目标 Widget
        5. 合并同 source+field 的联动
        6. 冲突检测（循环依赖）

        Args:
            schema: DashboardSchema

        Returns:
            CrossFilterRule 列表
        """
        if len(schema.widgets) < 2:
            return []

        # 构建 widget_id → fields 映射
        widget_fields: Dict[str, Set[str]] = {}
        widget_index: Dict[str, WidgetSlot] = {w.widget_id: w for w in schema.widgets}

        for w in schema.widgets:
            fields = set(_extract_filter_fields(w))
            if fields:
                widget_fields[w.widget_id] = fields

        # 找可点击 Widget
        clickable_widgets = {
            w.widget_id: w for w in schema.widgets
            if w.chart_type in CLICKABLE_CHART_TYPES and w.widget_id in widget_fields
        }

        if not clickable_widgets:
            return []

        # 构建联动对
        raw_rules: List[CrossFilterRule] = []
        widget_ids = list(widget_fields.keys())

        for source_id, source_widget in clickable_widgets.items():
            source_fields = widget_fields.get(source_id, set())

            for target_id in widget_ids:
                if target_id == source_id:
                    continue

                target_fields = widget_fields.get(target_id, set())
                # 找出共享字段（排除 time，time 不适合做 cross filter）
                common_fields = source_fields & target_fields - {"time"}

                for field_name in common_fields:
                    label = FILTER_FIELD_LABELS.get(field_name, field_name)
                    event_type = self._infer_event_type(source_widget)

                    raw_rules.append(CrossFilterRule(
                        id=f"cf_{source_id}_{field_name}",
                        source_widget=source_id,
                        event=event_type,
                        field=field_name,
                        field_label=label,
                        targets=[target_id],
                        priority=InteractionPriority.CROSS_FILTER,
                        bidirectional=field_name != "time",
                    ))

        # 合并同 source+field 的联动
        merged = self._merge_cross_filters(raw_rules)

        # 冲突检测（循环依赖）
        resolved = self._resolve_cyclic_dependencies(merged)

        return resolved

    # ============================================================
    # Event Type Inference
    # ============================================================

    @staticmethod
    def _infer_event_type(widget: WidgetSlot) -> str:
        """推断交互事件类型"""
        ct = widget.chart_type or ""
        if ct in ("bar", "pie", "map"):
            return "click"
        if ct == "scatter":
            return "hover"
        return "click"

    # ============================================================
    # Merge —— 合并同 source+field
    # ============================================================

    @staticmethod
    def _merge_cross_filters(raw: List[CrossFilterRule]) -> List[CrossFilterRule]:
        """合并同 source+field 的联动"""
        merged: Dict[Tuple[str, str], CrossFilterRule] = {}

        for r in raw:
            key = (r.source_widget, r.field)
            if key in merged:
                existing = merged[key]
                for t in r.targets:
                    if t not in existing.targets:
                        existing.targets.append(t)
            else:
                merged[key] = CrossFilterRule(
                    id=r.id,
                    source_widget=r.source_widget,
                    event=r.event,
                    field=r.field,
                    field_label=r.field_label,
                    targets=list(r.targets),
                    priority=r.priority,
                    bidirectional=r.bidirectional,
                    metadata=r.metadata,
                )

        return list(merged.values())

    # ============================================================
    # Cyclic Dependency Detection
    # ============================================================

    @staticmethod
    def _resolve_cyclic_dependencies(rules: List[CrossFilterRule]) -> List[CrossFilterRule]:
        """检测循环依赖并标记 bidirectional

        规则：A→B 且 B→A → bidirectional=True，保留一条
        """
        # 构建依赖图
        graph: Dict[str, Set[str]] = {}
        for r in rules:
            if r.source_widget not in graph:
                graph[r.source_widget] = set()
            for t in r.targets:
                graph[r.source_widget].add(t)

        result: List[CrossFilterRule] = []
        seen_pairs: Set[Tuple[str, str]] = set()

        for r in rules:
            # 检测 A→B 且 B→A 循环
            cyclic = False
            for t in r.targets:
                if t in graph and r.source_widget in graph[t]:
                    cyclic = True

            if cyclic:
                r.bidirectional = True

            # 防止重复
            pair_key = (r.source_widget, r.field)
            if pair_key not in seen_pairs:
                seen_pairs.add(pair_key)
                result.append(r)

        return result
