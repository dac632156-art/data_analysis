"""
Whitespace Optimizer —— Dashboard 留白优化器

核心职责：
- 自动控制 Page Margin
- 自动控制 Section Gap
- 自动控制 Widget Gap
- 自动控制 Card Padding
- 保证 Dashboard 呼吸感

设计原则：
- Widget 少时保持留白（不强行填满）
- Widget 多时自动增加行（不拥挤）
- 不出现空洞（unused grid cells）
- 不出现拥挤（widgets too close）
- 间距参数来自 Layout Strategy

生产方：WhitespaceOptimizer
消费方：DashboardLayoutEngine
"""

from __future__ import annotations
from typing import List, Dict, Any

from src.dashboard.grid_system import GridSlot
from src.dashboard.layout_strategy import LayoutStrategy


# ============================================================
# Whitespace Optimizer
# ============================================================

class WhitespaceOptimizer:
    """留白优化器——自动调整间距保证 Dashboard 呼吸感

    使用方式：
        optimizer = WhitespaceOptimizer(strategy)
        optimized_slots = optimizer.optimize(slots)
        report = optimizer.check_whitespace(slots)
    """

    def __init__(self, strategy: LayoutStrategy):
        self._strategy = strategy

    def optimize(self, slots: List[GridSlot]) -> List[GridSlot]:
        """优化间距

        算法：
        1. 根据 Widget 数量调整 section_gap（多→小，少→大）
        2. 根据 Widget 密度调整 widget_gap
        3. 填补空洞（连续空行）
        4. 不破坏 reading_flow 顺序

        Args:
            slots: GridSlot 列表

        Returns:
            优化后的 GridSlot 列表
        """
        if not slots:
            return slots

        # Step 1: 检查是否有空洞（连续空行）
        self._fill_holes(slots)

        # Step 2: 根据 Widget 数量调整间距
        total_widgets = len(slots)
        if total_widgets <= 3:
            # Widget 少 → 增加间距（保持留白）
            self._expand_spacing(slots, factor=1.5)
        elif total_widgets >= 10:
            # Widget 多 → 减少间距（避免拥挤）
            self._compact_spacing(slots, factor=0.8)

        return slots

    def _fill_holes(self, slots: List[GridSlot]) -> None:
        """填补空洞——检测并消除连续空行

        空洞定义：两行 Widget 之间有 ≥ 3 行完全空白。
        处理方式：将下方 Widget 上移。
        """
        if not slots:
            return

        # 按 y 排序
        sorted_slots = sorted(slots, key=lambda s: s.y)

        # 检测连续空行
        current_y = sorted_slots[0].y
        for i, slot in enumerate(sorted_slots):
            expected_y = current_y
            if slot.y > expected_y + 3:
                # 空洞超过 3 行 → 上移
                shift = slot.y - expected_y
                # 从这个 Widget 开始，后续所有 Widget 上移
                for j in range(i, len(sorted_slots)):
                    sorted_slots[j].y -= shift
            # 更新 current_y
            current_y = slot.y + slot.h + self._strategy.widget_gap

    def _expand_spacing(self, slots: List[GridSlot], factor: float = 1.5) -> None:
        """增加间距——Widget 少时保持留白

        不修改 gap 参数（那会影响所有 Widget），而是增加 Section 间间距。
        """
        # 按 section_id 分组
        sections: Dict[str, List[GridSlot]] = {}
        for s in slots:
            if s.section_id not in sections:
                sections[s.section_id] = []
            sections[s.section_id].append(s)

        # 按 y 排序 section
        sorted_sections = sorted(
            sections.keys(),
            key=lambda sid: min(s.y for s in sections[sid]),
        )

        # 增加后续 Section 的间距
        extra_gap = int(self._strategy.section_gap * (factor - 1))
        for i in range(1, len(sorted_sections)):
            sec_id = sorted_sections[i]
            prev_sec_id = sorted_sections[i - 1]
            prev_max_y = max(s.y + s.h for s in sections[prev_sec_id])
            # 将当前 Section 的所有 Widget 下移 extra_gap
            for s in sections[sec_id]:
                s.y += extra_gap

    def _compact_spacing(self, slots: List[GridSlot], factor: float = 0.8) -> None:
        """减少间距——Widget 多时避免拥挤

        不修改 gap 参数，而是减少 Section 间间距。
        """
        sections: Dict[str, List[GridSlot]] = {}
        for s in slots:
            if s.section_id not in sections:
                sections[s.section_id] = []
            sections[s.section_id].append(s)

        sorted_sections = sorted(
            sections.keys(),
            key=lambda sid: min(s.y for s in sections[sid]),
        )

        # 减少间距
        reduced_gap = int(self._strategy.section_gap * (1 - factor))
        for i in range(1, len(sorted_sections)):
            sec_id = sorted_sections[i]
            for s in sections[sec_id]:
                s.y -= reduced_gap

    def check_whitespace(self, slots: List[GridSlot]) -> Dict[str, Any]:
        """检查留白状况（不修改，只报告）

        Returns:
            留白报告 dict
        """
        if not slots:
            return {"status": "empty", "holes": 0, "avg_section_gap": 0}

        # 计算空洞
        sorted_slots = sorted(slots, key=lambda s: s.y)
        holes = 0
        for i in range(1, len(sorted_slots)):
            gap = sorted_slots[i].y - (sorted_slots[i - 1].y + sorted_slots[i - 1].h)
            if gap > 3:
                holes += 1

        # 计算 section 间平均间距
        sections: Dict[str, List[GridSlot]] = {}
        for s in slots:
            if s.section_id not in sections:
                sections[s.section_id] = []
            sections[s.section_id].append(s)

        section_gaps = []
        sorted_sections = sorted(
            sections.keys(),
            key=lambda sid: min(s.y for s in sections[sid]),
        )
        for i in range(1, len(sorted_sections)):
            prev_max_y = max(s.y + s.h for s in sections[sorted_sections[i - 1]])
            curr_min_y = min(s.y for s in sections[sorted_sections[i]])
            section_gaps.append(curr_min_y - prev_max_y)

        avg_gap = sum(section_gaps) / len(section_gaps) if section_gaps else 0

        # 计算拥挤度
        total_widgets = len(slots)
        max_y = max(s.y + s.h for s in slots)
        density = total_widgets / (max_y or 1)

        return {
            "holes": holes,
            "avg_section_gap": round(avg_gap, 2),
            "density": round(density, 2),
            "page_margin": self._strategy.page_margin,
            "section_gap_config": self._strategy.section_gap,
            "widget_gap_config": self._strategy.widget_gap,
            "status": "good" if holes == 0 and density < 3 else "needs_optimization",
        }
