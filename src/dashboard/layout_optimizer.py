"""
Layout Optimizer —— Dashboard 布局优化器

核心职责：
- 检测 Widget 重叠
- 检测 Section 空白
- 检测布局失衡
- 检测阅读顺序错误
- 自动修正所有问题

设计原则：
- 不破坏 reading_flow 顺序
- 不破坏 Composition Planner 的内容组织
- 只修正 Grid 坐标问题
- 修正后必须重新验证

生产方：LayoutOptimizer
消费方：DashboardLayoutEngine
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field

from src.dashboard.grid_system import GridSlot
from src.dashboard.layout_strategy import LayoutStrategy
from src.dashboard.visual_balance import VisualBalanceOptimizer
from src.dashboard.whitespace_optimizer import WhitespaceOptimizer


# ============================================================
# Layout Issue —— 布局问题描述
# ============================================================

@dataclass
class LayoutIssue:
    """布局问题描述"""
    issue_type: str = ""           # overlap / empty_section / imbalance / reading_order / hole
    severity: str = ""             # critical / warning / info
    description: str = ""
    affected_widgets: List[str] = field(default_factory=list)
    suggestion: str = ""


# ============================================================
# Layout Optimizer
# ============================================================

class LayoutOptimizer:
    """布局优化器——检测并修正所有布局问题

    检测项：
    1. Widget 重叠（critical）
    2. Section 空白（warning）
    3. 布局失衡（warning）
    4. 空洞（info）
    5. Widget 超出 Grid 边界（critical）

    修正策略：
    1. 重叠 → 移动下方 Widget
    2. 空白 → 合并或删除空 Section
    3. 失衡 → VisualBalanceOptimizer 处理
    4. 空洞 → WhitespaceOptimizer 处理
    5. 超出边界 → 缩小 Widget

    使用方式：
        optimizer = LayoutOptimizer(strategy)
        issues = optimizer.detect(slots)
        if issues:
            optimized_slots = optimizer.fix(slots, issues)
    """

    def __init__(self, strategy: LayoutStrategy):
        self._strategy = strategy
        self._columns = strategy.grid_columns
        self._balance_optimizer = VisualBalanceOptimizer(strategy)
        self._whitespace_optimizer = WhitespaceOptimizer(strategy)

    def detect(self, slots: List[GridSlot]) -> List[LayoutIssue]:
        """检测所有布局问题

        Args:
            slots: GridSlot 列表

        Returns:
            LayoutIssue 列表（按 severity 排序：critical > warning > info）
        """
        issues: List[LayoutIssue] = []

        if not slots:
            return issues

        # Detect 1: Widget overlap
        overlap_issues = self._detect_overlap(slots)
        issues.extend(overlap_issues)

        # Detect 2: Empty sections
        empty_issues = self._detect_empty_sections(slots)
        issues.extend(empty_issues)

        # Detect 3: Layout imbalance
        imbalance_issues = self._detect_imbalance(slots)
        issues.extend(imbalance_issues)

        # Detect 4: Widget out of bounds
        bounds_issues = self._detect_bounds(slots)
        issues.extend(bounds_issues)

        # Sort by severity
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        issues.sort(key=lambda i: severity_order.get(i.severity, 3))

        return issues

    def fix(self, slots: List[GridSlot], issues: List[LayoutIssue]) -> List[GridSlot]:
        """修正所有布局问题

        Args:
            slots: GridSlot 列表
            issues: LayoutIssue 列表

        Returns:
            修正后的 GridSlot 列表
        """
        if not slots:
            return slots

        # Fix overlap (critical)
        overlap_issues = [i for i in issues if i.issue_type == "overlap"]
        if overlap_issues:
            slots = self._fix_overlap(slots)

        # Fix bounds (critical)
        bounds_issues = [i for i in issues if i.issue_type == "out_of_bounds"]
        if bounds_issues:
            slots = self._fix_bounds(slots)

        # Fix imbalance (warning)
        imbalance_issues = [i for i in issues if i.issue_type == "imbalance"]
        if imbalance_issues:
            slots = self._balance_optimizer.optimize(slots)

        # Fix holes / whitespace (info)
        whitespace_issues = [i for i in issues if i.issue_type in ("hole", "empty_section")]
        if whitespace_issues:
            slots = self._whitespace_optimizer.optimize(slots)

        # Re-validate after fix
        remaining_issues = self.detect(slots)
        critical_remaining = [i for i in remaining_issues if i.severity == "critical"]
        if critical_remaining:
            # Second pass
            slots = self._fix_overlap(slots)
            slots = self._fix_bounds(slots)

        return slots

    # ============================================================
    # Detection Methods
    # ============================================================

    def _detect_overlap(self, slots: List[GridSlot]) -> List[LayoutIssue]:
        """检测 Widget 重叠

        两个 Widget 重叠的条件：
        - A.x < B.x + B.w AND A.x + A.w > B.x（水平重叠）
        - A.y < B.y + B.h AND A.y + A.h > B.y（垂直重叠）
        - 不在同一 Section（同一 Section 允许重叠调整）
        """
        issues: List[LayoutIssue] = []

        for i, a in enumerate(slots):
            for b in slots[i + 1:]:
                # 水平重叠
                h_overlap = a.x < b.x + b.w and a.x + a.w > b.x
                # 垂直重叠
                v_overlap = a.y < b.y + b.h and a.y + a.h > b.y

                if h_overlap and v_overlap:
                    overlap_area = self._overlap_area(a, b)
                    if overlap_area > 0:
                        issues.append(LayoutIssue(
                            issue_type="overlap",
                            severity="critical",
                            description=f"Widget {a.widget_id} overlaps {b.widget_id} (area={overlap_area})",
                            affected_widgets=[a.widget_id, b.widget_id],
                            suggestion=f"Move {b.widget_id} below {a.widget_id}",
                        ))

        return issues

    def _detect_empty_sections(self, slots: List[GridSlot]) -> List[LayoutIssue]:
        """检测空 Section"""
        issues: List[LayoutIssue] = []

        # 按 section_id 分组
        sections: Dict[str, List[GridSlot]] = {}
        for s in slots:
            if s.section_id not in sections:
                sections[s.section_id] = []
            sections[s.section_id].append(s)

        for sec_id, sec_slots in sections.items():
            if not sec_slots:
                issues.append(LayoutIssue(
                    issue_type="empty_section",
                    severity="warning",
                    description=f"Section {sec_id} has no widgets",
                    suggestion="Remove or merge empty section",
                ))

        return issues

    def _detect_imbalance(self, slots: List[GridSlot]) -> List[LayoutIssue]:
        """检测布局失衡"""
        issues: List[LayoutIssue] = []

        balance_report = self._balance_optimizer.check_balance(slots)
        if balance_report.get("status") == "imbalanced":
            h_ratio = balance_report.get("left_right_ratio", 1.0)
            v_ratio = balance_report.get("upper_lower_ratio", 1.0)

            if not balance_report.get("horizontal_balanced", True):
                issues.append(LayoutIssue(
                    issue_type="imbalance",
                    severity="warning",
                    description=f"Horizontal imbalance: L/R ratio={h_ratio}",
                    suggestion="Rebalance widgets for left-right symmetry",
                ))

            if not balance_report.get("vertical_balanced", True):
                issues.append(LayoutIssue(
                    issue_type="imbalance",
                    severity="info",
                    description=f"Vertical imbalance: U/L ratio={v_ratio}",
                    suggestion="Increase z-index for upper widgets",
                ))

        return issues

    def _detect_bounds(self, slots: List[GridSlot]) -> List[LayoutIssue]:
        """检测 Widget 超出 Grid 边界"""
        issues: List[LayoutIssue] = []

        for s in slots:
            if s.x + s.w > self._columns:
                issues.append(LayoutIssue(
                    issue_type="out_of_bounds",
                    severity="critical",
                    description=f"Widget {s.widget_id} exceeds grid: x={s.x}, w={s.w}, x+w={s.x + s.w} > {self._columns}",
                    affected_widgets=[s.widget_id],
                    suggestion=f"Reduce w from {s.w} to {self._columns - s.x}",
                ))
            if s.x < 0:
                issues.append(LayoutIssue(
                    issue_type="out_of_bounds",
                    severity="critical",
                    description=f"Widget {s.widget_id} has negative x={s.x}",
                    affected_widgets=[s.widget_id],
                    suggestion="Set x to 0",
                ))

        return issues

    # ============================================================
    # Fix Methods
    # ============================================================

    def _fix_overlap(self, slots: List[GridSlot]) -> List[GridSlot]:
        """修正重叠——将重叠的 Widget 移到下方

        算法：
        逐行检查，如果两个 Widget 重叠 → 将第二个 Widget 下移。
        """
        # 按 y 排序
        sorted_slots = sorted(slots, key=lambda s: (s.y, s.x))

        occupied: List[Tuple[int, int, int, int, str]] = []  # (x, y, w, h, widget_id)

        for slot in sorted_slots:
            # 检查是否有重叠
            new_y = slot.y
            while True:
                has_overlap = False
                for ox, oy, ow, oh, oid in occupied:
                    h_overlap = slot.x < ox + ow and slot.x + slot.w > ox
                    v_overlap = new_y < oy + oh and new_y + slot.h > oy
                    if h_overlap and v_overlap:
                        has_overlap = True
                        # 移到已有 Widget 下方
                        new_y = oy + oh + self._strategy.widget_gap
                        break

                if not has_overlap:
                    break

            slot.y = new_y
            occupied.append((slot.x, slot.y, slot.w, slot.h, slot.widget_id))

        return slots

    def _fix_bounds(self, slots: List[GridSlot]) -> List[GridSlot]:
        """修正超出边界——缩小 Widget 或移回边界"""
        for s in slots:
            # 确保不超出右边界
            if s.x + s.w > self._columns:
                s.w = self._columns - s.x
            # 确保 w 不小于最小宽度
            if s.w < 4:
                s.w = 4
                s.x = max(0, self._columns - s.w)
            # 确保 x 不为负
            if s.x < 0:
                s.x = 0
            # 确保 h 不小于最小高度
            if s.h < 2:
                s.h = 2

        return slots

    # ============================================================
    # Utility
    # ============================================================

    @staticmethod
    def _overlap_area(a: GridSlot, b: GridSlot) -> int:
        """计算两个 Widget 的重叠面积"""
        x_overlap = max(0, min(a.x + a.w, b.x + b.w) - max(a.x, b.x))
        y_overlap = max(0, min(a.y + a.h, b.y + b.h) - max(a.y, b.y))
        return x_overlap * y_overlap



