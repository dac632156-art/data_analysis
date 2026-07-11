"""
Dashboard Generator —— AnalysisPackage → Dashboard Schema 全流程

模块：
- models.py                  Widget 领域模型（旧版）
- widget_mapping.py          analysis_type → Widget 类型映射配置
- widget_generator.py        AnalysisPackage → List[Widget]（旧版）
- semantic_models.py         SemanticWidget 领域模型（新版）
- semantic_rules.py          语义分类引擎（Rule Engine + Strategy Pattern）
- importance_engine.py       重要性评分引擎（5维度加权）
- relationship_engine.py     Widget 关系识别引擎
- semantic_widget_generator.py  AnalysisPackage → List[SemanticWidget]（新版）
- widget_converter.py        Widget ↔ SemanticWidget 双向转换层
- composition_schema.py      Dashboard Blueprint 数据模型
- section_planner.py         Section 自动规划引擎
- widget_grouping.py         Widget 业务主题分组引擎
- composition_rules.py       Composition Rule Library（Strategy Pattern）
- composition_graph_builder.py  Composition Graph 构建器
- reading_flow.py            Reading Flow 构建器
- visual_hierarchy.py        Visual Hierarchy 构建器
- composition_planner.py     SemanticWidget[] → DashboardBlueprint（Composition Planner）
- layout_strategy.py         Layout Strategy Library（Strategy Pattern）
- grid_system.py             24列栅格系统 + preferred_size → w/h 映射
- section_placement.py       Section Placement 引擎
- widget_placement.py        Widget Placement 引擎（Hero/Major/Minor）
- visual_balance.py          Visual Balance 优化器
- whitespace_optimizer.py    Whitespace 优化器
- layout_optimizer.py        Layout Optimizer（重叠检测、空白检测、失衡修正）
- blueprint_layout_engine.py DashboardBlueprint → DashboardSchema（Layout Engine 新版）
- layout_schema.py           DashboardSchema / WidgetSlot / BusinessGroup 数据模型
- layout_engine.py           Widget[] → DashboardSchema（Layout Engine 旧版）
- interaction_schema.py      InteractionSchema / FilterRule / CrossFilterRule 等（v2.0 含 FilterScope + WidgetLinkageRule）
- interaction_engine.py      Widget + DashboardSchema → InteractionSchema（旧版）
- interaction_rules.py       Interaction Rule Engine（Strategy Pattern + Rule Engine）
- global_filter_generator.py Global Filter Generator（基于 Rule Engine）
- cross_filter_generator.py  Cross Filter Generator（基于 Rule Engine）
- drill_down_generator.py    Drill Down Generator（基于 Rule Engine）
- highlight_generator.py     Highlight Generator（基于 Rule Engine）
- widget_linkage_builder.py  Widget Linkage Builder（business_topic + shared fields）
- dashboard_interaction_engine.py DashboardSchema → Complete DashboardSchema（新版）
"""

from src.dashboard.models import Widget, WidgetType, WidgetSize, DisplayRole
from src.dashboard.widget_mapping import ANALYSIS_TO_WIDGET_MAPPING
from src.dashboard.widget_generator import WidgetGenerator
from src.dashboard.semantic_models import (
    SemanticWidget, BusinessTopic, VisualRole, AnalyticalRole,
    PriorityLevel, PreferredSize, RecommendedSection,
    InteractionCapability, ImportanceDetail,
    SemanticFilter, SemanticDataSource,
    DependencyGraph, WidgetRelation, RelationType,
)
from src.dashboard.semantic_rules import SemanticClassifier, ClassificationRule
from src.dashboard.importance_engine import ImportanceScoreEngine
from src.dashboard.relationship_engine import RelationshipEngine, build_dependency_graph
from src.dashboard.semantic_widget_generator import SemanticWidgetGenerator
from src.dashboard.widget_converter import (
    WidgetConverter, widget_to_semantic, semantic_to_widget_dict,
    widget_batch_to_semantic,
)
from src.dashboard.composition_schema import (
    DashboardBlueprint, BlueprintMetadata, BlueprintSection,
    BlueprintSectionRole, WidgetGroup as BlueprintWidgetGroup,
    CompositionGraph, CompositionEdge, CompositionCluster,
    ReadingFlow, FlowStep, VisualHierarchy,
)
from src.dashboard.section_planner import SectionPlanner
from src.dashboard.widget_grouping import WidgetGroupingEngine
from src.dashboard.composition_rules import (
    CompositionStrategy, CompositionStrategySelector,
    COMPOSITION_STRATEGIES,
)
from src.dashboard.composition_graph_builder import CompositionGraphBuilder
from src.dashboard.reading_flow import ReadingFlowBuilder
from src.dashboard.visual_hierarchy import VisualHierarchyBuilder
from src.dashboard.composition_planner import DashboardCompositionPlanner
from src.dashboard.layout_strategy import (
    LayoutStrategy, LayoutStrategySelector, LAYOUT_STRATEGIES,
)
from src.dashboard.grid_system import GridSystem, GridSlot
from src.dashboard.section_placement import SectionPlacementEngine
from src.dashboard.widget_placement import WidgetPlacementEngine, WidgetPlacementPlan
from src.dashboard.visual_balance import VisualBalanceOptimizer
from src.dashboard.whitespace_optimizer import WhitespaceOptimizer
from src.dashboard.layout_optimizer import LayoutOptimizer, LayoutIssue
from src.dashboard.blueprint_layout_engine import DashboardLayoutEngine
from src.dashboard.layout_schema import (
    DashboardSchema, LayoutConfig,
    WidgetSlot, DashboardSection, BusinessGroup,
    SectionRole,
)
from src.dashboard.layout_engine import (
    LayoutEngine,
    BusinessGrouper, LayoutSelector, GridAllocator,
)
from src.dashboard.interaction_schema import (
    InteractionSchema,
    FilterRule, CrossFilterRule, DrillDownRule, HighlightRule,
    FilterType, FilterScope, InteractionPriority, HighlightType, DrillDownLevel,
    WidgetLinkageRule, LinkageType,
)
from src.dashboard.interaction_engine import (
    InteractionEngine,
    generate_interactions,
)
from src.dashboard.interaction_rules import (
    InteractionRuleEngine, InteractionRule, ALL_INTERACTION_RULES,
    FILTER_FIELD_LABELS, FILTER_FIELD_WIDGET_TYPES,
)
from src.dashboard.global_filter_generator import GlobalFilterGenerator
from src.dashboard.cross_filter_generator import CrossFilterGenerator
from src.dashboard.drill_down_generator import DrillDownGenerator
from src.dashboard.highlight_generator import HighlightGenerator
from src.dashboard.widget_linkage_builder import WidgetLinkageBuilder
from src.dashboard.dashboard_interaction_engine import (
    DashboardInteractionEngine, InteractionOptimizer,
    enrich_dashboard_interactions,
)

__all__ = [
    # Widget 层（旧版，兼容）
    "Widget", "WidgetType", "WidgetSize", "DisplayRole",
    "ANALYSIS_TO_WIDGET_MAPPING", "WidgetGenerator",
    # Semantic Widget 层（新版）
    "SemanticWidget", "BusinessTopic", "VisualRole", "AnalyticalRole",
    "PriorityLevel", "PreferredSize", "RecommendedSection",
    "InteractionCapability", "ImportanceDetail",
    "SemanticFilter", "SemanticDataSource",
    "DependencyGraph", "WidgetRelation", "RelationType",
    "SemanticClassifier", "ClassificationRule",
    "ImportanceScoreEngine",
    "RelationshipEngine", "build_dependency_graph",
    "SemanticWidgetGenerator",
    "WidgetConverter", "widget_to_semantic", "semantic_to_widget_dict",
    "widget_batch_to_semantic",
    # Composition Planner 层（新版）
    "DashboardBlueprint", "BlueprintMetadata", "BlueprintSection",
    "BlueprintSectionRole", "BlueprintWidgetGroup",
    "CompositionGraph", "CompositionEdge", "CompositionCluster",
    "ReadingFlow", "FlowStep", "VisualHierarchy",
    "SectionPlanner", "WidgetGroupingEngine",
    "CompositionStrategy", "CompositionStrategySelector", "COMPOSITION_STRATEGIES",
    "CompositionGraphBuilder", "ReadingFlowBuilder", "VisualHierarchyBuilder",
    "DashboardCompositionPlanner",
    # Layout Engine 层（新版）
    "LayoutStrategy", "LayoutStrategySelector", "LAYOUT_STRATEGIES",
    "GridSystem", "GridSlot",
    "SectionPlacementEngine", "WidgetPlacementEngine", "WidgetPlacementPlan",
    "VisualBalanceOptimizer", "WhitespaceOptimizer",
    "LayoutOptimizer", "LayoutIssue",
    "DashboardLayoutEngine",
    # Layout/Schema 层
    "DashboardSchema", "LayoutConfig",
    "WidgetSlot", "DashboardSection", "BusinessGroup", "SectionRole",
    "LayoutEngine", "BusinessGrouper", "LayoutSelector", "GridAllocator",
    # Interaction 层
    "InteractionSchema",
    "FilterRule", "CrossFilterRule", "DrillDownRule", "HighlightRule",
    "FilterType", "FilterScope", "InteractionPriority", "HighlightType", "DrillDownLevel",
    "WidgetLinkageRule", "LinkageType",
    "InteractionEngine", "generate_interactions",
    # Interaction Engine 层（新版）
    "InteractionRuleEngine", "InteractionRule", "ALL_INTERACTION_RULES",
    "FILTER_FIELD_LABELS", "FILTER_FIELD_WIDGET_TYPES",
    "GlobalFilterGenerator", "CrossFilterGenerator",
    "DrillDownGenerator", "HighlightGenerator",
    "WidgetLinkageBuilder",
    "DashboardInteractionEngine", "InteractionOptimizer",
    "enrich_dashboard_interactions",
    "build_dashboard_schema",
]


# ============================================================
# 全链路 Pipeline
# ============================================================

def build_dashboard_schema(
    packages,
    title: str = "数据分析驾驶舱",
    layout_name = None,  # Optional[str]
) -> DashboardSchema:
    """一站式管道：AnalysisPackage → DashboardSchema（含完整交互）

    使用方式：
        from src.dashboard import build_dashboard_schema
        schema = build_dashboard_schema(packages, title="我的驾驶舱")
        schema_dict = schema.to_dict()  # 可直接 JSON 序列化给前端
    """
    # Phase 1: Widget 生成
    gen = WidgetGenerator()
    widgets = gen.generate(packages)
    widget_dicts = [w.to_dict() for w in widgets]

    # Phase 2: 布局引擎
    layout_engine = LayoutEngine()
    schema = layout_engine.build(widget_dicts, title=title, layout_name=layout_name)

    # Phase 3: 交互引擎
    ischema = generate_interactions(widget_dicts, schema)

    # Phase 4: 合并交互进 Schema
    schema.merge_interactions(ischema)

    return schema