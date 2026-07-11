"""
Grid System —— 24 列栅格系统 + preferred_size → w/h 映射

核心职责：
- 定义 24 列栅格系统
- 将 SemanticWidget 的 preferred_size 映射为 Grid 的 w（列宽）和 h（行高）
- 根据 Layout Strategy 的参数计算具体尺寸
- 自动计算 x 坐标（逐行填充）
- 自动计算 y 坐标（按 Section 排列）

设计原则：
- 24 列提供更精细的布局控制（12 列 → 24 列）
- extra_large → 24 列（全宽）
- large → 16 列（2/3 宽）
- medium → 12 列（半宽）
- small → 8 列（1/3 宽）
- x, y, w, h 全部由 Grid System 自动计算，不写死坐标
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field

from src.dashboard.semantic_models import (
    SemanticWidget, PreferredSize, PriorityLevel,
)
from src.dashboard.composition_schema import DashboardBlueprint, BlueprintSection
from src.dashboard.layout_strategy import LayoutStrategy


# ============================================================
# Grid Size Mapping —— preferred_size → (w, h) 映射
# ============================================================

# 24 列栅格系统下的尺寸映射（base mapping，strategy 可覆盖）
GRID_SIZE_MAP_24: Dict[str, Tuple[int, int]] = {
    "extra_large": (24, 5),   # 全宽 × 5 行
    "large":       (16, 4),   # 2/3 × 4 行
    "medium":      (12, 3),   # 半宽 × 3 行
    "small":       (8, 2),    # 1/3 × 2 行
}

# 旧版 12 列栅格兼容映射
GRID_SIZE_MAP_12: Dict[str, Tuple[int, int]] = {
    "hero":    (12, 4),
    "large":   (6, 3),
    "medium":  (4, 3),
    "small":   (3, 2),
}


# ============================================================
# Priority → Width Percent Mapping —— 优先级 → 列宽比例
# ============================================================

# priority_level → 列宽占比（基于 Layout Strategy 参数）
PRIORITY_WIDTH_MAP: Dict[str, float] = {
    "hero":  1.0,     # 全宽
    "major": 0.5,     # 半宽
    "minor": 0.333,   # 1/3 宽
}


# ============================================================
# Grid Slot —— Grid 坐标计算结果
# ============================================================

@dataclass
class GridSlot:
    """Widget 在 Grid 中的坐标——x, y, w, h 全部由 Grid System 计算"""
    widget_id: str = ""
    section_id: str = ""
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    z_index: int = 0
    priority_level: str = "major"
    preferred_size: str = "medium"
    visual_weight: int = 50

    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "section_id": self.section_id,
            "position": {"x": self.x, "y": self.y, "w": self.w, "h": self.h},
            "z_index": self.z_index,
            "priority_level": self.priority_level,
            "preferred_size": self.preferred_size,
            "visual_weight": self.visual_weight,
        }


# ============================================================
# Grid System —— 24 列栅格系统
# ============================================================

class GridSystem:
    """24 列栅格系统——自动计算 Widget 的 x/y/w/h

    核心算法：
    1. 根据 priority_level 确定 w 的占比
    2. 根据 preferred_size 确定 h
    3. 根据 Layout Strategy 参数微调 w/h
    4. 逐行填充 x 坐标（贪心算法）
    5. 按 Section 顺序计算 y 坐标

    使用方式：
        grid = GridSystem(strategy)
        slots = grid.allocate(section_widgets_map)
    """

    def __init__(self, strategy: LayoutStrategy):
        self._strategy = strategy
        self._columns = strategy.grid_columns

    def allocate(
        self,
        sections: List[BlueprintSection],
        widgets: List[SemanticWidget],
        blueprint: DashboardBlueprint,
    ) -> List[GridSlot]:
        """为所有 Widget 分配 Grid 坐标

        Args:
            sections: Blueprint Section 列表（按 reading_flow 排序）
            widgets: SemanticWidget 列表
            blueprint: DashboardBlueprint（含 visual_hierarchy）

        Returns:
            GridSlot 列表（带 x/y/w/h/z_index）
        """
        # 构建 widget_id → SemanticWidget 映射
        widget_map: Dict[str, SemanticWidget] = {w.id: w for w in widgets}

        # 构建 widget_id → priority_level 映射（从 visual_hierarchy）
        hierarchy = blueprint.visual_hierarchy
        priority_map: Dict[str, str] = {}
        for wid in hierarchy.hero_widgets:
            priority_map[wid] = "hero"
        for wid in hierarchy.major_widgets:
            priority_map[wid] = "major"
        for wid in hierarchy.minor_widgets:
            priority_map[wid] = "minor"

        all_slots: List[GridSlot] = []
        current_y = self._strategy.page_margin

        # 按 Section 顺序处理（遵循 reading_flow）
        for sec in sections:
            sec_slots = self._layout_section(
                sec, widget_map, priority_map, current_y,
            )
            all_slots.extend(sec_slots)

            # 更新 y：取 section 内最大 y + h
            if sec_slots:
                max_y_h = max(s.y + s.h for s in sec_slots)
                current_y = max_y_h + self._strategy.section_gap
            else:
                current_y += self._strategy.section_gap

        return all_slots

    def _layout_section(
        self,
        section: BlueprintSection,
        widget_map: Dict[str, SemanticWidget],
        priority_map: Dict[str, str],
        start_y: int,
    ) -> List[GridSlot]:
        """为单个 Section 分配 Grid

        算法：
        1. 按 priority_level 分三组：hero, major, minor
        2. Hero Widget → 占满一行
        3. Major Widget → 每行放 N 个（strategy.major_per_row）
        4. Minor Widget → 自动填充
        5. 贪心逐行填充 x 坐标
        """
        slots: List[GridSlot] = []

        # 按 widget_ids 顺序（已按 importance 降序）获取 Widget
        sec_widgets: List[SemanticWidget] = []
        for wid in section.widget_ids:
            w = widget_map.get(wid)
            if w:
                sec_widgets.append(w)

        if not sec_widgets:
            return slots

        # 分组：hero / major / minor
        hero_w, major_w, minor_w = self._group_by_priority(sec_widgets, priority_map)

        # Hero 超过 max_count 的降级为 Major
        overflow_hero = hero_w[self._strategy.hero_max_count:]
        hero_w = hero_w[:self._strategy.hero_max_count]
        major_w = overflow_hero + major_w

        # 按 hero → major → minor 顺序排列
        ordered = hero_w + major_w + minor_w

        # 逐行填充
        x = 0
        y = start_y
        row_height = 0

        for widget in ordered:
            w, h = self._compute_wh(widget, priority_map)

            # 换行判断
            if x + w > self._columns and x > 0:
                x = 0
                y += row_height + self._strategy.widget_gap
                row_height = 0

            # 确保不超列数
            if w > self._columns:
                w = self._columns

            # 计算 z_index（Hero 最高，Major 中等，Minor 最低）
            priority = priority_map.get(widget.id, "major")
            z_index = self._compute_z_index(priority, len(slots))

            # 计算 visual_weight
            visual_weight = int(widget.importance_score * 100)

            slot = GridSlot(
                widget_id=widget.id,
                section_id=section.id,
                x=x,
                y=y,
                w=w,
                h=h,
                z_index=z_index,
                priority_level=priority,
                preferred_size=widget.preferred_size.value,
                visual_weight=visual_weight,
            )
            slots.append(slot)

            x += w + self._strategy.widget_gap
            if h > row_height:
                row_height = h

        return slots

    def _group_by_priority(
        self,
        widgets: List[SemanticWidget],
        priority_map: Dict[str, str],
    ) -> Tuple[List[SemanticWidget], List[SemanticWidget], List[SemanticWidget]]:
        """按 priority_level 分三组"""
        hero, major, minor = [], [], []
        for w in widgets:
            priority = priority_map.get(w.id, w.priority_level.value)
            if priority == "hero":
                hero.append(w)
            elif priority == "major":
                major.append(w)
            else:
                minor.append(w)
        return hero, major, minor

    def _compute_wh(
        self,
        widget: SemanticWidget,
        priority_map: Dict[str, str],
    ) -> Tuple[int, int]:
        """根据 priority_level + preferred_size + strategy 计算 w, h

        优先级映射：
        - hero → strategy.hero_width_percent × grid_columns
        - major → strategy.major_width_percent × grid_columns
        - minor → strategy.minor_width_percent × grid_columns

        preferred_size 作为 h 的参考：
        - extra_large → strategy.hero_height
        - large → strategy.major_height
        - medium → strategy.minor_height（默认）
        - small → strategy.minor_height - 1
        """
        priority = priority_map.get(widget.id, widget.priority_level.value)
        size = widget.preferred_size.value

        # w: 根据 priority_level × strategy 参数 × grid_columns
        if priority == "hero":
            w = int(self._strategy.hero_width_percent * self._columns)
        elif priority == "major":
            w = int(self._strategy.major_width_percent * self._columns)
        else:
            w = int(self._strategy.minor_width_percent * self._columns)

        # h: 根据 priority_level + preferred_size
        if priority == "hero":
            h = self._strategy.hero_height
        elif priority == "major":
            h = self._strategy.major_height
        else:
            h = self._strategy.minor_height
            if size == "small":
                h = max(2, h - 1)

        # preferred_size 的 extra_large / large 可以覆盖 h
        if size == "extra_large" and priority != "minor":
            h = max(h, self._strategy.hero_height)

        # 确保 w 在合理范围内
        w = max(4, min(w, self._columns))
        h = max(2, min(h, 8))

        return w, h

    @staticmethod
    def _compute_z_index(priority: str, index: int) -> int:
        """计算 z_index：Hero 最高，Major 中等，Minor 最低"""
        if priority == "hero":
            return 100 - index   # Hero: 100, 99, 98...
        elif priority == "major":
            return 50 - index    # Major: 50, 49, 48...
        else:
            return 10 - index    # Minor: 10, 9, 8...
