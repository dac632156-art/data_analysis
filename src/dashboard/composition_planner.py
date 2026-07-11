"""
Dashboard Composition Planner —— SemanticWidget[] → Dashboard Blueprint

核心职责：
- 根据 SemanticWidget 的业务语义、视觉角色、业务主题、重要程度
- 自动设计整个 Dashboard 的组成结构（Composition）
- 输出 Dashboard Blueprint（不含 Grid 信息）

它决定：
- Dashboard 应该由哪些区域组成
- 每个区域放哪些 Widget
- Widget 与 Widget 如何组合
- 整个 Dashboard 的信息组织方式

不负责：
- Grid 排版（x/y/w/h）→ Layout Engine
- React 页面 → Renderer
- 重新分析数据 → Analysis Library
- 生成新的 Finding → Business Calculator

生产方：DashboardCompositionPlanner
消费方：Layout Engine（后续升级为读取 Blueprint）

使用方式：
    planner = DashboardCompositionPlanner()
    blueprint = planner.plan(widgets, title="销售看板")
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from collections import Counter

from src.dashboard.semantic_models import (
    SemanticWidget, BusinessTopic, VisualRole, PriorityLevel,
)
from src.dashboard.composition_schema import (
    DashboardBlueprint, BlueprintMetadata, BlueprintSection,
    BlueprintSectionRole, WidgetGroup, CompositionGraph,
    ReadingFlow, VisualHierarchy,
)
from src.dashboard.section_planner import SectionPlanner
from src.dashboard.widget_grouping import WidgetGroupingEngine
from src.dashboard.composition_rules import (
    CompositionStrategy, CompositionStrategySelector, COMPOSITION_STRATEGIES,
)
from src.dashboard.composition_graph_builder import CompositionGraphBuilder
from src.dashboard.reading_flow import ReadingFlowBuilder
from src.dashboard.visual_hierarchy import VisualHierarchyBuilder


# ============================================================
# Dashboard Composition Planner
# ============================================================

class DashboardCompositionPlanner:
    """Dashboard 组合规划器——SemanticWidget[] → Dashboard Blueprint

    内部流程：
    1. Widget Grouping → WidgetGroup[]
    2. Strategy Selection → CompositionStrategy
    3. Section Planning → BlueprintSection[]
    4. Widget Assignment → 将 Widget 分配到 Section
    5. Visual Hierarchy → Hero/Major/Minor 分层
    6. Composition Graph → Widget 组合关系图
    7. Reading Flow → Section 阅读顺序
    8. 组装 Blueprint → 最终输出

    使用方式：
        planner = DashboardCompositionPlanner()
        blueprint = planner.plan(widgets, title="销售看板")
    """

    def __init__(self):
        self._grouping_engine = WidgetGroupingEngine()
        self._strategy_selector = CompositionStrategySelector()
        self._section_planner = SectionPlanner()
        self._graph_builder = CompositionGraphBuilder()
        self._flow_builder = ReadingFlowBuilder()
        self._hierarchy_builder = VisualHierarchyBuilder()

    # ============================================================
    # 主入口
    # ============================================================

    def plan(
        self,
        widgets: List[SemanticWidget],
        title: str = "数据分析驾驶舱",
    ) -> DashboardBlueprint:
        """将 SemanticWidget 列表规划为 Dashboard Blueprint

        Args:
            widgets: SemanticWidget 列表（已含 related_widgets）
            title: Dashboard 标题

        Returns:
            DashboardBlueprint（不含 Grid 信息）
        """
        if not widgets:
            return self._empty_blueprint(title)

        # Step 1: Widget Grouping（按 business_topic 分组）
        groups = self._grouping_engine.group(widgets)

        # Step 2: Strategy Selection（选择组合策略）
        strategy = self._strategy_selector.select(widgets)

        # Step 3: Section Planning（自动规划 Section）
        sections = self._section_planner.plan(widgets)

        # Step 4: 调整 Section 顺序（按 Strategy 的 section_order 排序）
        sections = self._apply_strategy_order(sections, strategy)

        # Step 5: Visual Hierarchy（信息层级）
        visual_hierarchy = self._hierarchy_builder.build(widgets)

        # Step 6: Composition Graph（Widget 组合关系）
        composition_graph = self._graph_builder.build(widgets)

        # Step 7: Reading Flow（阅读顺序）
        reading_flow = self._flow_builder.build(sections, strategy)

        # Step 8: 组装 Blueprint
        metadata = self._build_metadata(widgets, sections, groups, strategy, title)

        blueprint = DashboardBlueprint(
            metadata=metadata,
            sections=sections,
            groups=groups,
            composition_graph=composition_graph,
            reading_flow=reading_flow,
            visual_hierarchy=visual_hierarchy,
            theme={"mode": "light", "primary_color": "#38BDF8"},
            responsive={"breakpoints": {"lg": 1200, "md": 768, "sm": 480}},
            animation={"transition": "fade", "duration": 300},
            dark_mode={"supported": True, "default": False},
            mobile={"enabled": False, "layout": "stacked"},
        )

        return blueprint

    # ============================================================
    # Strategy Order Adjustment
    # ============================================================

    def _apply_strategy_order(
        self,
        sections: List[BlueprintSection],
        strategy: CompositionStrategy,
    ) -> List[BlueprintSection]:
        """按 Strategy 的 section_order 调整 Section 顺序

        算法：
        1. Strategy 定义了理想的 Section 顺序
        2. 实际存在的 Section 按 Strategy 顺序排列
        3. 不在 Strategy 中的 Section 按 priority 排在末尾
        """
        # 按 Strategy section_order 排序
        strategy_order = strategy.section_order
        section_role_map: Dict[BlueprintSectionRole, BlueprintSection] = {}
        for sec in sections:
            section_role_map[sec.role] = sec

        ordered: List[BlueprintSection] = []

        # Step 1: 按 Strategy 顺序添加存在的 Section
        for role in strategy_order:
            section = section_role_map.get(role)
            if section:
                ordered.append(section)

        # Step 2: 添加不在 Strategy 顺序中的 Section
        covered_roles = {sec.role for sec in ordered}
        remaining = [sec for sec in sections if sec.role not in covered_roles]
        remaining.sort(key=lambda s: s.priority)
        ordered.extend(remaining)

        # Step 3: 重新编号 priority
        for i, sec in enumerate(ordered):
            sec.priority = i + 1

        return ordered

    # ============================================================
    # Metadata Builder
    # ============================================================

    def _build_metadata(
        self,
        widgets: List[SemanticWidget],
        sections: List[BlueprintSection],
        groups: List[WidgetGroup],
        strategy: CompositionStrategy,
        title: str,
    ) -> BlueprintMetadata:
        """构建 Blueprint 元数据"""
        import uuid
        import time

        # Topic distribution
        topic_counts = Counter(w.business_topic.value for w in widgets)
        dominant_topic = topic_counts.most_common(1)[0][0] if topic_counts else "general"

        return BlueprintMetadata(
            id=f"blueprint_{uuid.uuid4().hex[:8]}",
            title=title,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            version="2.0",
            widget_count=len(widgets),
            section_count=len(sections),
            group_count=len(groups),
            topic_distribution=dict(topic_counts),
            dominant_topic=dominant_topic,
            composition_strategy=strategy.name,
            source_type="semantic_widgets",
            generator="DashboardCompositionPlanner v1.0",
        )

    # ============================================================
    # Empty Blueprint
    # ============================================================

    @staticmethod
    def _empty_blueprint(title: str) -> DashboardBlueprint:
        """生成空 Blueprint"""
        import uuid
        import time

        return DashboardBlueprint(
            metadata=BlueprintMetadata(
                id=f"blueprint_{uuid.uuid4().hex[:8]}",
                title=title,
                created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                widget_count=0,
                section_count=0,
                group_count=0,
                note="No widgets available",
            ),
        )
