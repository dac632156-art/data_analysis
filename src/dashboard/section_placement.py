"""
Section Placement —— 根据 Blueprint 和 reading_flow 放置 Section

核心职责：
- 根据 Blueprint 的 reading_flow 决定 Section 的垂直位置（y_start / y_end）
- Section 顺序严格遵循 reading_flow
- 不重新生成 Section（Section 由 Composition Planner 决定）
- 不重新分组 Widget（Widget 由 Composition Planner 分配）

设计原则：
- Section 顺序 = reading_flow 步骤顺序
- Overview → 顶部
- Main Analysis → 中央
- Comparison → 左右
- Detail → 底部
- Section Gap 由 Layout Strategy 控制

生产方：SectionPlacementEngine
消费方：DashboardLayoutEngine
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

from src.dashboard.composition_schema import (
    DashboardBlueprint, BlueprintSection, BlueprintSectionRole,
)
from src.dashboard.layout_strategy import LayoutStrategy
from src.dashboard.layout_schema import DashboardSection, SectionRole


# ============================================================
# BlueprintSectionRole → SectionRole 映射
# ============================================================

BLUEPRINT_TO_SCHEMA_ROLE: Dict[str, SectionRole] = {
    "overview":        SectionRole.HERO,         # Overview 区 → Hero Section（顶部 KPI 行）
    "main_analysis":   SectionRole.MAIN,         # 主分析 → Main Section
    "comparison":      SectionRole.MAIN,         # 比较 → Main Section
    "distribution":    SectionRole.MAIN,         # 分布 → Main Section
    "ranking":         SectionRole.MAIN,         # 排名 → Main Section
    "geographic":      SectionRole.MAIN,         # 地理 → Main Section
    "monitoring":      SectionRole.SECONDARY,    # 监控 → Secondary Section
    "detail":          SectionRole.SECONDARY,    # 详情 → Secondary Section
}

# Section Role 中文标题
SECTION_DISPLAY_NAMES: Dict[str, str] = {
    "header":     "标题栏",
    "hero":       "核心指标",
    "main":       "主要分析",
    "secondary":  "辅助分析",
    "sidebar":    "侧边栏",
    "footer":     "补充信息",
}


# ============================================================
# Section Placement Engine
# ============================================================

class SectionPlacementEngine:
    """Section 垂直位置计算引擎

    根据 Blueprint 的 reading_flow 和 Section 的 widget 数量，
    计算每个 Section 的 y_start 和 y_end。

    使用方式：
        engine = SectionPlacementEngine(strategy)
        schema_sections = engine.place(blueprint, grid_slots)
    """

    def __init__(self, strategy: LayoutStrategy):
        self._strategy = strategy

    def place(
        self,
        blueprint: DashboardBlueprint,
        grid_slots: List[Dict[str, Any]],
    ) -> List[DashboardSection]:
        """将 Blueprint Section 转换为 DashboardSchema Section

        Args:
            blueprint: DashboardBlueprint（含 sections + reading_flow）
            grid_slots: GridSlot 列表（含 widget_id, section_id, x, y, w, h）

        Returns:
            DashboardSection 列表（含 y_start, y_end, widget_ids）
        """
        schema_sections: List[DashboardSection] = []

        # Step 1: 按 reading_flow 顺序排列 Blueprint Section
        ordered_sections = self._order_by_reading_flow(blueprint)

        # Step 2: 为每个 Section 创建 DashboardSection
        for bp_sec in ordered_sections:
            schema_role = BLUEPRINT_TO_SCHEMA_ROLE.get(
                bp_sec.role.value, SectionRole.MAIN,
            )

            # 找到 Section 内所有 Widget 的 Grid Slot
            sec_slots = [s for s in grid_slots if s.get("section_id") == bp_sec.id]

            # 计算 y_start / y_end
            if sec_slots:
                y_start = min(s.get("y", 0) for s in sec_slots)
                y_end = max(s.get("y", 0) + s.get("h", 3) for s in sec_slots)
            else:
                y_start = 0
                y_end = 0

            schema_sec = DashboardSection(
                id=bp_sec.id,
                role=schema_role,
                title=bp_sec.title,
                y_start=y_start,
                y_end=y_end,
                widget_ids=bp_sec.widget_ids,
            )
            schema_sections.append(schema_sec)

        return schema_sections

    def _order_by_reading_flow(
        self,
        blueprint: DashboardBlueprint,
    ) -> List[BlueprintSection]:
        """按 reading_flow 步骤顺序排列 Section

        reading_flow 定义了用户从上到下浏览的推荐路径。
        Layout Engine 严格遵循这个顺序。
        """
        # 构建 section_id → BlueprintSection 映射
        section_map: Dict[str, BlueprintSection] = {
            sec.id: sec for sec in blueprint.sections
        }

        # 按 reading_flow 步骤排序
        flow = blueprint.reading_flow
        ordered: List[BlueprintSection] = []

        for step in flow.steps:
            sec = section_map.get(step.section_id)
            if sec:
                ordered.append(sec)

        # 添加不在 reading_flow 中的 Section（按 priority 排末尾）
        covered_ids = {sec.id for sec in ordered}
        remaining = [sec for sec in blueprint.sections if sec.id not in covered_ids]
        remaining.sort(key=lambda s: s.priority)
        ordered.extend(remaining)

        return ordered
