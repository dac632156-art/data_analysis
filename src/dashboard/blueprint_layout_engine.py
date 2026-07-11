"""
Dashboard Layout Engine —— Dashboard Blueprint → Dashboard Schema

核心职责：
- 把 Dashboard Blueprint 自动转换成专业 Dashboard Layout
- 决定 Dashboard 应该如何摆放（Placement）
- 不是展示什么（Composition Planner 决定）
- 不是组织什么（Composition Planner 决定）
- 而是：放在哪里（Layout Engine 决定）

设计原则：
- 只读取 Dashboard Blueprint
- 不重新生成 Section（Composition Planner 决定）
- 不重新分组 Widget（Composition Planner 决定）
- 不重新计算 Business Topic（Composition Planner 决定）
- 输出 Dashboard Schema（Renderer 唯一输入）

内部流程：
1. Layout Strategy Selection → 选择布局策略
2. Grid System → 24 列栅格，计算 w/h
3. Section Placement → 按 reading_flow 排列 Section
4. Widget Placement → Hero/Major/Minor 分级放置
5. Visual Balance → 左右/上下平衡优化
6. Whitespace Optimization → 间距调整
7. Layout Optimization → 重叠检测 + 修正
8. 组装 Dashboard Schema → 最终输出

生产方：DashboardLayoutEngine
消费方：Interaction Engine / Renderer

使用方式：
    engine = DashboardLayoutEngine()
    schema = engine.build(blueprint, widgets, title="销售看板")
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
import uuid
import time

from src.dashboard.semantic_models import SemanticWidget
from src.dashboard.composition_schema import DashboardBlueprint, BlueprintSectionRole
from src.dashboard.layout_schema import (
    DashboardSchema, LayoutConfig, WidgetSlot, DashboardSection,
    BusinessGroup, SectionRole,
)
from src.dashboard.layout_strategy import (
    LayoutStrategy, LayoutStrategySelector, LAYOUT_STRATEGIES,
)
from src.dashboard.grid_system import GridSystem, GridSlot
from src.dashboard.section_placement import SectionPlacementEngine
from src.dashboard.widget_placement import WidgetPlacementEngine
from src.dashboard.visual_balance import VisualBalanceOptimizer
from src.dashboard.whitespace_optimizer import WhitespaceOptimizer
from src.dashboard.layout_optimizer import LayoutOptimizer


# ============================================================
# Dashboard Layout Engine —— 主编排器
# ============================================================

class DashboardLayoutEngine:
    """Dashboard Layout Engine——Dashboard Blueprint → Dashboard Schema

    使用方式：
        engine = DashboardLayoutEngine()
        schema = engine.build(blueprint, widgets, title="销售看板")
    """

    def __init__(self):
        self._strategy_selector = LayoutStrategySelector()

    def build(
        self,
        blueprint: DashboardBlueprint,
        widgets: List[SemanticWidget],
        title: str = "数据分析驾驶舱",
        strategy_name: Optional[str] = None,
    ) -> DashboardSchema:
        """将 Dashboard Blueprint 转换为 Dashboard Schema

        Args:
            blueprint: DashboardBlueprint（Composition Planner 的输出）
            widgets: SemanticWidget 列表（提供 chart_config 等数据）
            title: Dashboard 标题
            strategy_name: 指定布局策略（None = 自动选择）

        Returns:
            DashboardSchema（Renderer 唯一输入）
        """
        if not widgets or not blueprint.sections:
            return self._empty_schema(title, blueprint)

        # Step 1: Layout Strategy Selection
        strategy = self._select_strategy(blueprint, strategy_name)

        # Step 2: 按 reading_flow 排列 Section
        ordered_sections = self._order_sections(blueprint)

        # Step 3: Grid System → 计算 x/y/w/h
        grid_system = GridSystem(strategy)
        grid_slots = grid_system.allocate(ordered_sections, widgets, blueprint)

        # Step 4: Convert GridSlot → WidgetSlot
        widget_slots = self._convert_slots(grid_slots, widgets, blueprint)

        # Step 5: Section Placement → 计算 y_start/y_end
        section_engine = SectionPlacementEngine(strategy)
        # 将 grid_slots 转为 dict 格式给 section_engine
        slot_dicts = [s.to_dict() for s in grid_slots]
        schema_sections = section_engine.place(blueprint, slot_dicts)

        # Step 6: Visual Balance Optimization
        balance_optimizer = VisualBalanceOptimizer(strategy)
        grid_slots = balance_optimizer.optimize(grid_slots)
        # 重新更新 widget_slots 的位置
        widget_slots = self._update_slots_from_grid(widget_slots, grid_slots)

        # Step 7: Whitespace Optimization
        whitespace_optimizer = WhitespaceOptimizer(strategy)
        grid_slots = whitespace_optimizer.optimize(grid_slots)
        widget_slots = self._update_slots_from_grid(widget_slots, grid_slots)

        # Step 8: Layout Optimization（检测 + 修正）
        layout_optimizer = LayoutOptimizer(strategy)
        issues = layout_optimizer.detect(grid_slots)
        if issues:
            grid_slots = layout_optimizer.fix(grid_slots, issues)
            widget_slots = self._update_slots_from_grid(widget_slots, grid_slots)
            # Re-run section placement after optimization
            slot_dicts = [s.to_dict() for s in grid_slots]
            schema_sections = section_engine.place(blueprint, slot_dicts)

        # Step 9: Build Business Groups
        schema_groups = self._build_groups(blueprint, widgets)

        # Step 10: Assemble Dashboard Schema
        config = LayoutConfig(
            name=strategy.name,
            columns=strategy.grid_columns,
            section_order=[sec.role.value for sec in ordered_sections],
            hero_cols=int(strategy.hero_width_percent * strategy.grid_columns),
            size_grid={
                "hero":    (int(strategy.hero_width_percent * strategy.grid_columns), strategy.hero_height),
                "large":   (int(strategy.major_width_percent * strategy.grid_columns), strategy.major_height),
                "medium":  (int(strategy.minor_width_percent * strategy.grid_columns), strategy.minor_height),
                "small":   (8, 2),
            },
            section_gap=strategy.section_gap,
            widget_gap=strategy.widget_gap,
            page_margin=strategy.page_margin,
            rebalance_enabled=strategy.rebalance_enabled,
        )

        schema = DashboardSchema(
            id=f"dashboard_{uuid.uuid4().hex[:8]}",
            title=title,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            version="2.0",
            metadata={
                "widget_count": len(widgets),
                "section_count": len(blueprint.sections),
                "layout_strategy": strategy.name,
                "composition_strategy": blueprint.metadata.composition_strategy,
                "generator": "DashboardLayoutEngine v1.0",
                "layout_issues_fixed": len(issues),
            },
            blueprint_id=blueprint.metadata.id,
            layout=config,
            layout_strategy=strategy.name,
            widgets=widget_slots,
            sections=schema_sections,
            groups=schema_groups,
            interactions={},  # Interaction Engine 后续填充
            theme={"mode": "light", "primary_color": "#38BDF8"},
            responsive={
                "desktop": {"columns": 24, "mode": "grid"},
                "tablet": {"columns": 12, "mode": "grid"},
                "mobile": {"columns": 1, "mode": "stacked"},
            },
            dark_mode=False,
            mobile={"enabled": False, "layout": "stacked"},
        )

        return schema

    # ============================================================
    # Strategy Selection
    # ============================================================

    def _select_strategy(
        self,
        blueprint: DashboardBlueprint,
        strategy_name: Optional[str],
    ) -> LayoutStrategy:
        """选择 Layout Strategy"""
        if strategy_name:
            return LAYOUT_STRATEGIES.get(strategy_name, LAYOUT_STRATEGIES["general"])
        return self._strategy_selector.select(blueprint)

    # ============================================================
    # Section Ordering
    # ============================================================

    def _order_sections(
        self,
        blueprint: DashboardBlueprint,
    ) -> List:
        """按 reading_flow 排列 Section"""
        from src.dashboard.composition_schema import BlueprintSection

        section_map: Dict[str, BlueprintSection] = {
            sec.id: sec for sec in blueprint.sections
        }

        ordered: List[BlueprintSection] = []

        # 按 reading_flow 步骤排序
        for step in blueprint.reading_flow.steps:
            sec = section_map.get(step.section_id)
            if sec:
                ordered.append(sec)

        # 添加不在 reading_flow 中的 Section
        covered_ids = {sec.id for sec in ordered}
        remaining = [sec for sec in blueprint.sections if sec.id not in covered_ids]
        remaining.sort(key=lambda s: s.priority)
        ordered.extend(remaining)

        return ordered

    # ============================================================
    # Slot Conversion
    # ============================================================

    def _convert_slots(
        self,
        grid_slots: List[GridSlot],
        widgets: List[SemanticWidget],
        blueprint: DashboardBlueprint,
    ) -> List[WidgetSlot]:
        """将 GridSlot 转换为 WidgetSlot（添加 chart_config 等数据）"""
        widget_map: Dict[str, SemanticWidget] = {w.id: w for w in widgets}
        hierarchy = blueprint.visual_hierarchy

        # priority → importance_score (0-1 → 0-100)
        priority_score_map: Dict[str, int] = {}
        for wid in hierarchy.hero_widgets:
            w = widget_map.get(wid)
            priority_score_map[wid] = int((w.importance_score if w else 0.9) * 100)
        for wid in hierarchy.major_widgets:
            w = widget_map.get(wid)
            priority_score_map[wid] = int((w.importance_score if w else 0.7) * 100)
        for wid in hierarchy.minor_widgets:
            w = widget_map.get(wid)
            priority_score_map[wid] = int((w.importance_score if w else 0.3) * 100)

        slots: List[WidgetSlot] = []
        for gs in grid_slots:
            w = widget_map.get(gs.widget_id)
            if not w:
                continue

            # 找到 Widget 所在 Group
            group_id = ""
            for grp in blueprint.groups:
                if gs.widget_id in grp.widget_ids:
                    group_id = grp.id
                    break

            slot = WidgetSlot(
                widget_id=w.id,
                title=w.title,
                description=getattr(w, "description", "") or "",
                widget_type=self._infer_widget_type(w),
                x=gs.x,
                y=gs.y,
                w=gs.w,
                h=gs.h,
                size_class=gs.priority_level if gs.priority_level in ("hero", "large", "medium", "small") else "medium",
                importance_score=priority_score_map.get(gs.widget_id, int(w.importance_score * 100)),
                visual_weight=gs.visual_weight,
                z_index=gs.z_index,
                section_id=gs.section_id,
                group_id=group_id,
                chart_type=w.chart_type,
                chart_config=w.chart_config,
                supported_filters=[
                    {"field": f.field, "label": f.label, "filter_type": f.filter_type}
                    for f in w.supported_filters
                ],
                metadata={
                    "analysis_type": w.analysis_type,
                    "business_topic": w.business_topic.value,
                    "visual_role": w.visual_role.value,
                    "priority_level": gs.priority_level,
                },
            )
            slots.append(slot)

        return slots

    @staticmethod
    def _infer_widget_type(widget: SemanticWidget) -> str:
        """推断 widget_type"""
        from src.dashboard.semantic_models import VisualRole
        role_type_map = {
            VisualRole.OVERVIEW_METRIC: "kpi",
            VisualRole.SUMMARY_CARD: "summary",
            VisualRole.DETAIL: "table",
            VisualRole.GEOGRAPHIC: "map",
        }
        return role_type_map.get(widget.visual_role, "chart")

    # ============================================================
    # Update Slots from Grid
    # ============================================================

    @staticmethod
    def _update_slots_from_grid(
        widget_slots: List[WidgetSlot],
        grid_slots: List[GridSlot],
    ) -> List[WidgetSlot]:
        """从 GridSlot 更新 WidgetSlot 的位置信息"""
        grid_map: Dict[str, GridSlot] = {gs.widget_id: gs for gs in grid_slots}

        for ws in widget_slots:
            gs = grid_map.get(ws.widget_id)
            if gs:
                ws.x = gs.x
                ws.y = gs.y
                ws.w = gs.w
                ws.h = gs.h
                ws.z_index = gs.z_index
                ws.visual_weight = gs.visual_weight

        return widget_slots

    # ============================================================
    # Build Groups
    # ============================================================

    def _build_groups(
        self,
        blueprint: DashboardBlueprint,
        widgets: List[SemanticWidget],
    ) -> List[BusinessGroup]:
        """从 Blueprint Groups 构建 DashboardSchema BusinessGroup"""
        widget_map: Dict[str, SemanticWidget] = {w.id: w for w in widgets}
        schema_groups: List[BusinessGroup] = []

        for grp in blueprint.groups:
            # 计算组内 importance 均值
            group_widgets = [widget_map.get(wid) for wid in grp.widget_ids]
            valid_widgets = [w for w in group_widgets if w]
            avg_importance = (
                sum(w.importance_score for w in valid_widgets) / len(valid_widgets)
                if valid_widgets else 0
            )

            bg = BusinessGroup(
                id=grp.id,
                topic=grp.title or grp.topic,
                widget_ids=grp.widget_ids,
                importance=round(int(avg_importance * 100)),
            )
            schema_groups.append(bg)

        # 按 importance 降序排列
        schema_groups.sort(key=lambda g: g.importance, reverse=True)

        return schema_groups

    # ============================================================
    # Empty Schema
    # ============================================================

    @staticmethod
    def _empty_schema(title: str, blueprint: DashboardBlueprint) -> DashboardSchema:
        """生成空 Dashboard Schema"""
        return DashboardSchema(
            id="empty_dashboard",
            title=title,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            metadata={"widget_count": 0, "note": "No widgets or sections available"},
            blueprint_id=blueprint.metadata.id if blueprint else "",
        )
