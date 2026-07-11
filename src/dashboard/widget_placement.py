"""
Widget Placement —— 根据 priority_level + preferred_size 放置 Widget

核心职责：
- 将 SemanticWidget 放置到 Grid 中
- Hero Widget → 占满一行（最显著位置）
- Major Widget → 左右布局（清晰展示）
- Minor Widget → 自动填充（补充信息）
- 禁止所有 Widget 等宽等高

设计原则：
- Hero 占满整行，w = grid_columns
- Major 左右对称，w = grid_columns / major_per_row
- Minor 自动填充剩余空间
- 视觉重心优先
- 不写死坐标（全部由 Grid System 计算）

注意：实际的 x/y/w/h 计算在 Grid System 中完成。
Widget Placement 的职责是确定 Widget 的放置策略（按什么顺序、什么分组），
Grid System 根据这些策略计算具体坐标。

生产方：WidgetPlacementEngine
消费方：DashboardLayoutEngine（协调 Grid System + Widget Placement）
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field

from src.dashboard.semantic_models import (
    SemanticWidget, PriorityLevel, PreferredSize,
    VisualRole, BusinessTopic,
)
from src.dashboard.composition_schema import (
    DashboardBlueprint, BlueprintSection, BlueprintSectionRole,
)
from src.dashboard.layout_strategy import LayoutStrategy


# ============================================================
# Placement Strategy —— Widget 放置策略
# ============================================================

@dataclass
class WidgetPlacementPlan:
    """Widget 放置计划——描述每个 Widget 的放置策略

    不包含具体坐标（x/y），只描述放置策略。
    Grid System 读取此计划来计算坐标。
    """
    widget_id: str = ""
    section_id: str = ""
    priority_level: str = "major"              # hero / major / minor
    placement_mode: str = "auto"               # full_row / side_by_side / auto_fill / stacked
    width_hint: float = 0.5                    # 期望宽度占比（0-1）
    height_hint: int = 3                       # 期望高度（行数）
    preferred_size: str = "medium"              # 原始 preferred_size
    visual_weight: int = 50                     # 视觉重量（0-100）
    row_group: int = 0                          # 同行分组号（同一个 row_group 的 Widget 尝试放在同一行）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "section_id": self.section_id,
            "priority_level": self.priority_level,
            "placement_mode": self.placement_mode,
            "width_hint": self.width_hint,
            "height_hint": self.height_hint,
            "preferred_size": self.preferred_size,
            "visual_weight": self.visual_weight,
            "row_group": self.row_group,
        }


# ============================================================
# Widget Placement Engine
# ============================================================

class WidgetPlacementEngine:
    """Widget 放置策略引擎——根据 priority_level + visual_role 生成放置计划

    核心算法：
    1. Hero Widget → placement_mode = "full_row", width_hint = 1.0
    2. Major Widget → placement_mode = "side_by_side", width_hint = 0.5
    3. Minor Widget → placement_mode = "auto_fill", width_hint = 0.33
    4. 根据 composition_graph 的 cluster → 同簇 Widget 尝试同行
    5. 根据 visual_role 确定是否需要全宽（trend / map → full_row）

    使用方式：
        engine = WidgetPlacementEngine(strategy)
        plans = engine.plan(blueprint, widgets)
    """

    def __init__(self, strategy: LayoutStrategy):
        self._strategy = strategy

    def plan(
        self,
        blueprint: DashboardBlueprint,
        widgets: List[SemanticWidget],
    ) -> List[WidgetPlacementPlan]:
        """为所有 Widget 生成放置计划

        Args:
            blueprint: DashboardBlueprint
            widgets: SemanticWidget 列表

        Returns:
            WidgetPlacementPlan 列表
        """
        widget_map: Dict[str, SemanticWidget] = {w.id: w for w in widgets}
        hierarchy = blueprint.visual_hierarchy

        # 构建 widget_id → priority_level 映射
        priority_map: Dict[str, str] = {}
        for wid in hierarchy.hero_widgets:
            priority_map[wid] = "hero"
        for wid in hierarchy.major_widgets:
            priority_map[wid] = "major"
        for wid in hierarchy.minor_widgets:
            priority_map[wid] = "minor"

        # Hero 超过 max_count → 降级为 Major
        hero_widgets = hierarchy.hero_widgets[:self._strategy.hero_max_count]
        overflow_hero = hierarchy.hero_widgets[self._strategy.hero_max_count:]
        for wid in overflow_hero:
            priority_map[wid] = "major"

        # 构建 cluster → row_group 映射（同簇 Widget 放同一行）
        cluster_groups = self._build_cluster_groups(blueprint)

        plans: List[WidgetPlacementPlan] = []

        for sec in blueprint.sections:
            for wid in sec.widget_ids:
                widget = widget_map.get(wid)
                if not widget:
                    continue

                priority = priority_map.get(wid, widget.priority_level.value)
                plan = self._build_plan(
                    widget=widget,
                    section_id=sec.id,
                    priority=priority,
                    cluster_group=cluster_groups.get(wid, 0),
                )
                plans.append(plan)

        return plans

    def _build_plan(
        self,
        widget: SemanticWidget,
        section_id: str,
        priority: str,
        cluster_group: int,
    ) -> WidgetPlacementPlan:
        """为单个 Widget 构建放置计划"""
        visual_weight = int(widget.importance_score * 100)

        # placement_mode
        if priority == "hero":
            placement_mode = "full_row"
            width_hint = self._strategy.hero_width_percent
            height_hint = self._strategy.hero_height
        elif priority == "major":
            # 如果 visual_role 是 primary_trend 或 geographic → 需要 wider
            if widget.visual_role in (VisualRole.PRIMARY_TREND, VisualRole.GEOGRAPHIC):
                placement_mode = "full_row"
                width_hint = 0.667  # 2/3 宽
            else:
                placement_mode = "side_by_side"
                width_hint = self._strategy.major_width_percent
            height_hint = self._strategy.major_height
        else:
            placement_mode = "auto_fill"
            width_hint = self._strategy.minor_width_percent
            height_hint = self._strategy.minor_height
            if widget.preferred_size == PreferredSize.SMALL:
                height_hint = max(2, height_hint - 1)

        return WidgetPlacementPlan(
            widget_id=widget.id,
            section_id=section_id,
            priority_level=priority,
            placement_mode=placement_mode,
            width_hint=width_hint,
            height_hint=height_hint,
            preferred_size=widget.preferred_size.value,
            visual_weight=visual_weight,
            row_group=cluster_group,
        )

    @staticmethod
    def _build_cluster_groups(blueprint: DashboardBlueprint) -> Dict[str, int]:
        """从 Composition Graph 的 Cluster 构建 row_group 映射

        同簇 Widget 尝试放在同一行（row_group 相同）。
        """
        groups: Dict[str, int] = {}
        for i, cluster in enumerate(blueprint.composition_graph.clusters):
            for mid in cluster.member_ids:
                groups[mid] = i + 1
            # 核心 Widget 也属于这个组
            groups[cluster.core_widget_id] = i + 1
        return groups
