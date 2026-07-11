"""
Visual Balance —— Dashboard 视觉平衡优化器

核心职责：
- 检测左右视觉重量是否失衡
- 检测上下视觉重量是否失衡
- 自动调整 Widget 位置以实现视觉平衡
- 避免：所有 Hero 在左边、所有图大小一致

设计原则：
- 左侧重量 ≈ 右侧重量
- 上部重量 ≥ 下部重量（重要信息在上）
- 同行 Widget 高度对齐
- 不破坏 reading_flow 顺序

算法：
- 检查每行左右两侧的 visual_weight 之和
- 如果左侧 > 右侧 * 1.3 → 交换最重的 Widget 到右侧
- 如果上下失衡 → 适当提升低权重 Widget 的 z_index

生产方：VisualBalanceOptimizer
消费方：DashboardLayoutEngine
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple

from src.dashboard.grid_system import GridSlot
from src.dashboard.layout_strategy import LayoutStrategy


# ============================================================
# Visual Balance Optimizer
# ============================================================

class VisualBalanceOptimizer:
    """视觉平衡优化器——自动调整 Widget 位置实现左右平衡

    使用方式：
        optimizer = VisualBalanceOptimizer(strategy)
        optimized_slots = optimizer.optimize(slots)
    """

    def __init__(self, strategy: LayoutStrategy):
        self._strategy = strategy
        self._columns = strategy.grid_columns

    def optimize(self, slots: List[GridSlot]) -> List[GridSlot]:
        """优化 Widget 位置实现视觉平衡

        Args:
            slots: GridSlot 列表（已含 x/y/w/h）

        Returns:
            优化后的 GridSlot 列表（可能调整了 x 位置）
        """
        if not slots or not self._strategy.rebalance_enabled:
            return slots

        # Step 1: 按 y 分组（按行）
        rows: Dict[int, List[GridSlot]] = {}
        for s in slots:
            if s.y not in rows:
                rows[s.y] = []
            rows[s.y].append(s)

        # Step 2: 逐行检查左右平衡
        for y, row_slots in rows.items():
            if len(row_slots) < 2:
                continue

            self._balance_row(row_slots)

        # Step 3: 检查上下平衡（重要信息在上）
        self._balance_vertical(slots)

        return slots

    def _balance_row(self, row_slots: List[GridSlot]) -> None:
        """平衡单行左右视觉重量

        算法：
        1. 计算左半 (x < columns/2) 和右半 (x >= columns/2) 的 visual_weight 之和
           全宽 Widget（跨越中线）的重量等分左右
        2. 如果左侧 > 右侧 * 1.3 → 交换最重的 Widget 到右侧
        3. 如果右侧 > 左侧 * 1.3 → 交换最重的 Widget 到左侧
        """
        mid = self._columns // 2

        left_weight = 0
        right_weight = 0
        left_slots = []
        right_slots = []
        full_width_slots = []

        for s in row_slots:
            if s.x + s.w > mid and s.x < mid:
                # 跨越中线
                left_weight += s.visual_weight / 2
                right_weight += s.visual_weight / 2
                full_width_slots.append(s)
            elif s.x >= mid:
                right_weight += s.visual_weight
                right_slots.append(s)
            else:
                left_weight += s.visual_weight
                left_slots.append(s)

        # 只调整非全宽 Widget（全宽 Widget 无法移动）
        # 左侧过重 → 将左侧最重的非全宽 Widget 移到右侧
        if left_weight > right_weight * 1.3 and left_slots and right_slots:
            left_slots_sorted = sorted(left_slots, key=lambda s: s.visual_weight, reverse=True)
            if left_slots_sorted:
                heaviest = left_slots_sorted[0]
                right_slots_sorted = sorted(right_slots, key=lambda s: s.visual_weight)
                lightest_right = right_slots_sorted[0]
                # 交换 x 位置
                heaviest.x, lightest_right.x = lightest_right.x, heaviest.x

        # 右侧过重 → 将右侧最重的非全宽 Widget 移到左侧
        elif right_weight > left_weight * 1.3 and right_slots and left_slots:
            right_slots_sorted = sorted(right_slots, key=lambda s: s.visual_weight, reverse=True)
            if right_slots_sorted:
                heaviest = right_slots_sorted[0]
                left_slots_sorted = sorted(left_slots, key=lambda s: s.visual_weight)
                lightest_left = left_slots_sorted[0]
                heaviest.x, lightest_left.x = lightest_left.x, heaviest.x

    def _balance_vertical(self, slots: List[GridSlot]) -> None:
        """检查上下平衡——重要信息应在上方

        算法：
        1. 计算上半部分和下半部分的 visual_weight 之和（跨越中线等分）
        2. 如果上半 < 下半 * 0.7 → 提升 z_index 使上方更突出
        3. 不调整 y 位置（会破坏 reading_flow）
        """
        if not slots:
            return

        max_y = max(s.y + s.h for s in slots)
        mid_y = max_y // 2

        upper_weight = 0
        lower_weight = 0
        for s in slots:
            if s.y <= mid_y and s.y + s.h > mid_y:
                upper_weight += s.visual_weight / 2
                lower_weight += s.visual_weight / 2
            elif s.y > mid_y:
                lower_weight += s.visual_weight
            else:
                upper_weight += s.visual_weight

        # 如果下半部分视觉重量过大 → 提升上半 Widget 的 z_index
        if lower_weight > upper_weight * 1.3:
            for s in slots:
                if s.y <= mid_y:
                    s.z_index += 10

    def check_balance(self, slots: List[GridSlot]) -> Dict[str, Any]:
        """检查当前布局的平衡状况（不修改，只报告）

        Returns:
            平衡报告 dict
        """
        if not slots:
            return {"status": "empty", "left_weight": 0, "right_weight": 0}

        mid = self._columns // 2

        # 计算左右视觉重量——全宽 Widget 的重量等分左右
        left_weight = 0
        right_weight = 0
        for s in slots:
            if s.x + s.w > mid and s.x < mid:
                # Widget 跨越中线 → 重量等分
                left_weight += s.visual_weight / 2
                right_weight += s.visual_weight / 2
            elif s.x >= mid:
                right_weight += s.visual_weight
            else:
                left_weight += s.visual_weight

        max_y = max(s.y for s in slots)
        mid_y = max_y // 2 if max_y > 0 else 0
        upper_weight = 0
        lower_weight = 0
        for s in slots:
            # Widget 跨越中线 → 重量等分
            if s.y <= mid_y and s.y + s.h > mid_y:
                upper_weight += s.visual_weight / 2
                lower_weight += s.visual_weight / 2
            elif s.y > mid_y:
                lower_weight += s.visual_weight
            else:
                upper_weight += s.visual_weight

        left_right_ratio = left_weight / (right_weight or 1)
        upper_lower_ratio = upper_weight / (lower_weight or 1)

        return {
            "left_weight": round(left_weight),
            "right_weight": round(right_weight),
            "upper_weight": round(upper_weight),
            "lower_weight": round(lower_weight),
            "left_right_ratio": round(left_right_ratio, 2),
            "upper_lower_ratio": round(upper_lower_ratio, 2),
            "horizontal_balanced": 0.5 <= left_right_ratio <= 2.0,
            "vertical_balanced": upper_lower_ratio >= 0.5,
            "status": "balanced" if (0.5 <= left_right_ratio <= 2.0 and upper_lower_ratio >= 0.5) else "imbalanced",
        }
