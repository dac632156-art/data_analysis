"""
Visual Hierarchy Builder —— Dashboard 信息层级构建

核心职责：
- 根据 Widget 的 priority_level 建立 Dashboard 信息层级
- Hero → Major → Minor 三级分层
- 只定义层级，不定义位置（x/y）

设计原则：
- 层级是概念性的（重要性排序），不是视觉性的（位置排列）
- Layout Engine 后续会根据层级决定 Grid 位置
"""

from __future__ import annotations
from typing import List

from src.dashboard.semantic_models import SemanticWidget, PriorityLevel
from src.dashboard.composition_schema import VisualHierarchy


class VisualHierarchyBuilder:
    """信息层级构建器——根据 priority_level 建立 VisualHierarchy

    使用方式：
        builder = VisualHierarchyBuilder()
        hierarchy = builder.build(widgets)
    """

    def build(self, widgets: List[SemanticWidget]) -> VisualHierarchy:
        """构建信息层级

        Args:
            widgets: SemanticWidget 列表

        Returns:
            VisualHierarchy
        """
        hero_widgets: List[str] = []
        major_widgets: List[str] = []
        minor_widgets: List[str] = []

        for w in widgets:
            if w.priority_level == PriorityLevel.HERO:
                hero_widgets.append(w.id)
            elif w.priority_level == PriorityLevel.MAJOR:
                major_widgets.append(w.id)
            else:
                minor_widgets.append(w.id)

        # Hero Widget 按 importance_score 降序
        hero_widgets_sorted = self._sort_by_importance(widgets, hero_widgets)
        major_widgets_sorted = self._sort_by_importance(widgets, major_widgets)
        minor_widgets_sorted = self._sort_by_importance(widgets, minor_widgets)

        return VisualHierarchy(
            hero_widgets=hero_widgets_sorted,
            major_widgets=major_widgets_sorted,
            minor_widgets=minor_widgets_sorted,
            hero_count=len(hero_widgets_sorted),
            major_count=len(major_widgets_sorted),
            minor_count=len(minor_widgets_sorted),
        )

    @staticmethod
    def _sort_by_importance(widgets: List[SemanticWidget], ids: List[str]) -> List[str]:
        """按 importance_score 降序排列给定 ID 列表"""
        widget_map = {w.id: w for w in widgets}
        sorted_ids = sorted(
            ids,
            key=lambda id_: widget_map.get(id_, SemanticWidget()).importance_score,
            reverse=True,
        )
        return sorted_ids
