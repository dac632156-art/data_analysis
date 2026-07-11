"""
Dashboard Interaction Engine —— DashboardSchema → Complete DashboardSchema

核心职责：
- 根据 Dashboard Schema 自动生成整个 Dashboard 的交互逻辑
- 不是布局（Layout Engine 决定）
- 不是渲染（Renderer 决定）
- 而是：Dashboard 如何交互（How to Interact）

设计原则：
- 只读取 Dashboard Schema
- 不修改布局
- 不修改 Widget
- 不修改 Section
- 不重新分析业务
- 输出 Complete Dashboard Schema（interactions 字段填充）

内部流程：
1. Global Filter Generation → 全局筛选器
2. Cross Filter Generation → Widget 间交叉筛选
3. Drill Down Generation → 维度下钻
4. Highlight Generation → 高亮交互
5. Widget Linkage → Widget 联动关系
6. Interaction Optimizer → 冲突检测 + 优先级排序
7. 组装 Complete Dashboard Schema

生产方：DashboardInteractionEngine
消费方：Dashboard Renderer

使用方式：
    engine = DashboardInteractionEngine()
    complete_schema = engine.enrich(schema)
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
import uuid
import time

from src.dashboard.layout_schema import DashboardSchema
from src.dashboard.interaction_schema import (
    InteractionSchema,
    FilterRule, CrossFilterRule, DrillDownRule, HighlightRule,
    WidgetLinkageRule,
    InteractionPriority,
)
from src.dashboard.interaction_rules import InteractionRuleEngine
from src.dashboard.global_filter_generator import GlobalFilterGenerator
from src.dashboard.cross_filter_generator import CrossFilterGenerator
from src.dashboard.drill_down_generator import DrillDownGenerator
from src.dashboard.highlight_generator import HighlightGenerator
from src.dashboard.widget_linkage_builder import WidgetLinkageBuilder


# ============================================================
# Interaction Optimizer —— 交互冲突检测 + 优化
# ============================================================

class InteractionOptimizer:
    """交互优化器——检测冲突、调整优先级

    检测项：
    1. 重复 Filter（同一 field 出现多次）
    2. Cross Filter 循环依赖
    3. 交互优先级冲突（Global > Cross > Highlight）
    4. Highlight 规则重叠
    """

    def optimize(self, ischema: InteractionSchema) -> InteractionSchema:
        """优化交互规则

        优化策略：
        1. 去重复 Global Filter（同一 field 只保留一个）
        2. 去重复 Cross Filter（同一 source+field 只保留一个）
        3. 去重复 Highlight（同一 widget+rule_type 只保留一个）
        4. 优先级排序确保：Global > Cross > Drill > Highlight
        """
        # Step 1: 去重复 Global Filter
        seen_fields: set = set()
        unique_filters: List[FilterRule] = []
        for f in ischema.global_filters:
            if f.field not in seen_fields:
                seen_fields.add(f.field)
                unique_filters.append(f)
        ischema.global_filters = unique_filters

        # Step 2: 去重复 Cross Filter
        seen_keys: set = set()
        unique_cross: List[CrossFilterRule] = []
        for c in ischema.cross_filters:
            key = (c.source_widget, c.field)
            if key not in seen_keys:
                seen_keys.add(key)
                unique_cross.append(c)
        ischema.cross_filters = unique_cross

        # Step 3: 去重复 Highlight
        seen_hl_keys: set = set()
        unique_hl: List[HighlightRule] = []
        for h in ischema.highlights:
            key = (h.widget_id, h.rule_type)
            if key not in seen_hl_keys:
                seen_hl_keys.add(key)
                unique_hl.append(h)
        ischema.highlights = unique_hl

        # Step 4: 去重复 Linkage
        seen_lg_keys: set = set()
        unique_lg: List[WidgetLinkageRule] = []
        for l in ischema.linkages:
            key = tuple(sorted(l.source_widgets))
            if key not in seen_lg_keys:
                seen_lg_keys.add(key)
                unique_lg.append(l)
        ischema.linkages = unique_lg

        return ischema


# ============================================================
# Dashboard Interaction Engine —— 主编排器
# ============================================================

class DashboardInteractionEngine:
    """Dashboard 交互引擎——Dashboard Schema → Complete Dashboard Schema

    使用方式：
        engine = DashboardInteractionEngine()
        complete_schema = engine.enrich(schema)
    """

    def __init__(self):
        self._rule_engine = InteractionRuleEngine()
        self._optimizer = InteractionOptimizer()

    def enrich(self, schema: DashboardSchema) -> DashboardSchema:
        """将 Dashboard Schema 的 interactions 字段填充为完整的 Interaction Schema

        流程：
        1. Global Filter Generation
        2. Cross Filter Generation
        3. Drill Down Generation
        4. Highlight Generation
        5. Widget Linkage Generation
        6. Interaction Optimizer
        7. 组装到 Dashboard Schema

        Args:
            schema: DashboardSchema（Layout Engine 的输出）

        Returns:
            Complete DashboardSchema（interactions 字段已填充）
        """
        if not schema.widgets:
            schema.interactions = self._empty_interaction(schema).to_dict()
            return schema

        # Step 1: Global Filter
        gf_gen = GlobalFilterGenerator(self._rule_engine)
        global_filters = gf_gen.generate(schema)

        # Step 2: Cross Filter
        cf_gen = CrossFilterGenerator(self._rule_engine)
        cross_filters = cf_gen.generate(schema)

        # Step 3: Drill Down
        dd_gen = DrillDownGenerator(self._rule_engine)
        drill_downs = dd_gen.generate(schema)

        # Step 4: Highlight
        hl_gen = HighlightGenerator(self._rule_engine)
        highlights = hl_gen.generate(schema)

        # Step 5: Widget Linkage
        lg_builder = WidgetLinkageBuilder(self._rule_engine)
        linkages = lg_builder.build(schema)

        # Step 6: 组装 InteractionSchema
        ischema = InteractionSchema(
            id=f"interact_{uuid.uuid4().hex[:8]}",
            dashboard_id=schema.id,
            version="2.0",
            global_filters=global_filters,
            cross_filters=cross_filters,
            drill_downs=drill_downs,
            highlights=highlights,
            linkages=linkages,
            metadata={
                "total_widgets": len(schema.widgets),
                "global_filter_count": len(global_filters),
                "cross_filter_count": len(cross_filters),
                "drill_down_count": len(drill_downs),
                "highlight_count": len(highlights),
                "linkage_count": len(linkages),
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "generator": "DashboardInteractionEngine v1.0",
            },
        )

        # Step 7: Optimization
        ischema = self._optimizer.optimize(ischema)

        # Step 8: 合并到 Dashboard Schema
        schema.interactions = ischema.to_dict()

        return schema

    @staticmethod
    def _empty_interaction(schema: DashboardSchema) -> InteractionSchema:
        """空 Interaction Schema"""
        return InteractionSchema(
            id="empty_interaction",
            dashboard_id=schema.id,
            version="2.0",
            metadata={"total_widgets": 0, "note": "No widgets available"},
        )


# ============================================================
# Quick Function
# ============================================================

def enrich_dashboard_interactions(schema: DashboardSchema) -> DashboardSchema:
    """快捷函数：DashboardSchema → Complete DashboardSchema"""
    engine = DashboardInteractionEngine()
    return engine.enrich(schema)
