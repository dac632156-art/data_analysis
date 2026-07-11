"""
Dashboard Composition Planner Tests

测试覆盖：
1. Section 自动生成
2. Widget 正确分组
3. Priority 正确
4. Reading Flow 正确
5. Composition Graph 正确
6. Blueprint 正确输出
"""

import sys
import os
import json

# 确保项目根目录在 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.dashboard.semantic_models import (
    SemanticWidget, BusinessTopic, VisualRole, AnalyticalRole,
    PriorityLevel, PreferredSize, RecommendedSection,
    ImportanceDetail, SemanticFilter, SemanticDataSource,
    WidgetRelation, RelationType, InteractionCapability,
)
from src.dashboard.composition_planner import DashboardCompositionPlanner
from src.dashboard.section_planner import SectionPlanner
from src.dashboard.widget_grouping import WidgetGroupingEngine
from src.dashboard.composition_rules import CompositionStrategySelector
from src.dashboard.composition_graph_builder import CompositionGraphBuilder
from src.dashboard.reading_flow import ReadingFlowBuilder
from src.dashboard.visual_hierarchy import VisualHierarchyBuilder
from src.dashboard.composition_schema import (
    DashboardBlueprint, BlueprintSectionRole,
)


# ============================================================
# Test Data Factory
# ============================================================

def make_widget(
    id_suffix: str,
    title: str,
    business_topic: BusinessTopic,
    visual_role: VisualRole,
    analytical_role: AnalyticalRole,
    importance_score: float,
    priority_level: PriorityLevel,
    recommended_section: RecommendedSection,
    related_widgets: list = None,
    description: str = "",
    business_purpose: str = "",
) -> SemanticWidget:
    """创建测试 SemanticWidget"""
    w = SemanticWidget(
        id=f"test_{id_suffix}",
        title=title,
        description=description or f"Test widget: {title}",
        business_topic=business_topic,
        business_purpose=business_purpose or f"Test purpose: {title}",
        visual_role=visual_role,
        analytical_role=analytical_role,
        importance_score=importance_score,
        importance_detail=ImportanceDetail(weighted_total=importance_score),
        priority_level=priority_level,
        preferred_size=PreferredSize.MEDIUM,
        recommended_section=recommended_section,
        analysis_type=id_suffix.replace("_", "") + "_analysis",
        related_widgets=related_widgets or [],
    )
    # Force the id since SemanticWidget auto-generates
    w.id = f"test_{id_suffix}"
    return w


# ============================================================
# Test Case: Full Pipeline
# ============================================================

def test_full_pipeline():
    """Test 1: Full Composition Planner Pipeline

    Input: 7 SemanticWidgets (sales/growth/risk/customer/finance mix)
    Expected:
    - Sections auto-generated
    - Widgets correctly grouped
    - Reading Flow defined
    - Blueprint output correct
    """
    print("\n" + "=" * 60)
    print("Test 1: Full Pipeline - SemanticWidget[] -> DashboardBlueprint")
    print("=" * 60)

    # Create test widgets with relationships
    widgets = [
        # Hero widgets (overview)
        make_widget(
            "sales_kpi", "Sales KPI",
            BusinessTopic.SALES, VisualRole.OVERVIEW_METRIC,
            AnalyticalRole.MONITOR, 0.95, PriorityLevel.HERO,
            RecommendedSection.OVERVIEW,
            description="Total sales revenue",
            business_purpose="Monitor total sales revenue",
        ),
        # Main trend
        make_widget(
            "sales_trend", "Sales Trend",
            BusinessTopic.SALES, VisualRole.PRIMARY_TREND,
            AnalyticalRole.MONITOR, 0.88, PriorityLevel.HERO,
            RecommendedSection.MAIN_ANALYSIS,
            related_widgets=[
                WidgetRelation(
                    target_widget_id="test_region_rank",
                    relation_type=RelationType.EXPLAIN,
                    description="Region ranking explains sales trend source",
                ),
                WidgetRelation(
                    target_widget_id="test_product_struct",
                    relation_type=RelationType.EXPLAIN,
                    description="Product structure reveals composition reason",
                ),
            ],
            business_purpose="Monitor sales revenue trend changes",
        ),
        # Comparison (ranking)
        make_widget(
            "region_rank", "Region Ranking",
            BusinessTopic.SALES, VisualRole.RANKING,
            AnalyticalRole.COMPARE, 0.72, PriorityLevel.MAJOR,
            RecommendedSection.COMPARISON,
            related_widgets=[
                WidgetRelation(
                    target_widget_id="test_product_struct",
                    relation_type=RelationType.DRILL,
                    description="Product structure provides ranking detail",
                ),
            ],
        ),
        # Comparison (composition)
        make_widget(
            "product_struct", "Product Structure",
            BusinessTopic.PRODUCT, VisualRole.COMPOSITION,
            AnalyticalRole.EXPLAIN, 0.65, PriorityLevel.MAJOR,
            RecommendedSection.COMPARISON,
        ),
        # Monitoring (anomaly)
        make_widget(
            "anomaly_warn", "Anomaly Warning",
            BusinessTopic.RISK, VisualRole.WARNING,
            AnalyticalRole.DISCOVER, 0.60, PriorityLevel.MAJOR,
            RecommendedSection.MONITORING,
        ),
        # Detail
        make_widget(
            "corr_detail", "Correlation Detail",
            BusinessTopic.GENERAL, VisualRole.CORRELATION,
            AnalyticalRole.DISCOVER, 0.35, PriorityLevel.MINOR,
            RecommendedSection.DETAIL,
        ),
        # Distribution (Minor)
        make_widget(
            "dist_analysis", "Distribution Analysis",
            BusinessTopic.GENERAL, VisualRole.DISTRIBUTION,
            AnalyticalRole.EXPLAIN, 0.30, PriorityLevel.MINOR,
            RecommendedSection.DETAIL,
        ),
    ]

    # Run planner
    planner = DashboardCompositionPlanner()
    blueprint = planner.plan(widgets, title="Sales Dashboard")

    # Validate
    assert blueprint is not None, "Blueprint should not be None"
    assert blueprint.metadata.widget_count == 7, f"Expected 7 widgets, got {blueprint.metadata.widget_count}"
    assert len(blueprint.sections) >= 3, f"Expected >= 3 sections, got {len(blueprint.sections)}"
    assert len(blueprint.groups) >= 2, f"Expected >= 2 groups, got {len(blueprint.groups)}"
    assert len(blueprint.reading_flow.steps) >= 3, f"Expected >= 3 flow steps, got {len(blueprint.reading_flow.steps)}"
    assert len(blueprint.composition_graph.edges) >= 2, f"Expected >= 2 edges, got {len(blueprint.composition_graph.edges)}"
    assert blueprint.visual_hierarchy.hero_count >= 2, f"Expected >= 2 hero widgets, got {blueprint.visual_hierarchy.hero_count}"

    # Check sections
    section_roles = [sec.role.value for sec in blueprint.sections]
    assert "overview" in section_roles, f"Overview section missing: {section_roles}"
    assert "main_analysis" in section_roles, f"Main analysis section missing: {section_roles}"

    # Check no grid info (Blueprint sections should not have x/y/w/h position fields)
    bp_dict = blueprint.to_dict()
    # Check each section dict does NOT have position/x/y/w/h
    for sec in bp_dict.get("sections", []):
        assert "x" not in sec, f"Section should NOT contain x: {sec}"
        assert "y" not in sec, f"Section should NOT contain y: {sec}"
        assert "w" not in sec, f"Section should NOT contain w: {sec}"
        assert "h" not in sec, f"Section should NOT contain h: {sec}"
        assert "position" not in sec, f"Section should NOT contain position: {sec}"
    # Check overall Blueprint structure has no grid/position keys
    assert "layout" not in bp_dict or not any(k in str(bp_dict.get("layout", {})) for k in ["x_grid", "y_grid", "grid_position"]), "Blueprint should NOT contain grid position info"

    print("[OK] Full Pipeline Test PASSED")
    print(f"  - Blueprint ID: {blueprint.metadata.id}")
    print(f"  - Widget Count: {blueprint.metadata.widget_count}")
    print(f"  - Section Count: {len(blueprint.sections)}")
    print(f"  - Group Count: {len(blueprint.groups)}")
    print(f"  - Flow Steps: {len(blueprint.reading_flow.steps)}")
    print(f"  - Composition Strategy: {blueprint.metadata.composition_strategy}")
    print(f"  - Dominant Topic: {blueprint.metadata.dominant_topic}")
    print(f"  - Visual Hierarchy: Hero={blueprint.visual_hierarchy.hero_count}, Major={blueprint.visual_hierarchy.major_count}, Minor={blueprint.visual_hierarchy.minor_count}")

    return blueprint


# ============================================================
# Test Case: Section Planning
# ============================================================

def test_section_planning():
    """Test 2: Section auto-generation

    Expected:
    - Overview section for overview_metric widgets
    - Main section for primary_trend
    - Comparison section for ranking/composition
    - Monitoring section for warning
    - No Geographic section (no geographic widgets)
    """
    print("\n" + "=" * 60)
    print("Test 2: Section Planning")
    print("=" * 60)

    widgets = [
        make_widget("kpi1", "KPI 1", BusinessTopic.SALES, VisualRole.OVERVIEW_METRIC,
                    AnalyticalRole.MONITOR, 0.95, PriorityLevel.HERO, RecommendedSection.OVERVIEW),
        make_widget("kpi2", "KPI 2", BusinessTopic.SALES, VisualRole.OVERVIEW_METRIC,
                    AnalyticalRole.MONITOR, 0.90, PriorityLevel.HERO, RecommendedSection.OVERVIEW),
        make_widget("trend1", "Trend 1", BusinessTopic.GROWTH, VisualRole.PRIMARY_TREND,
                    AnalyticalRole.MONITOR, 0.80, PriorityLevel.MAJOR, RecommendedSection.MAIN_ANALYSIS),
        make_widget("rank1", "Rank 1", BusinessTopic.SALES, VisualRole.RANKING,
                    AnalyticalRole.COMPARE, 0.70, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
        make_widget("warn1", "Warn 1", BusinessTopic.RISK, VisualRole.WARNING,
                    AnalyticalRole.DISCOVER, 0.60, PriorityLevel.MAJOR, RecommendedSection.MONITORING),
        make_widget("detail1", "Detail 1", BusinessTopic.GENERAL, VisualRole.DETAIL,
                    AnalyticalRole.EXPLAIN, 0.30, PriorityLevel.MINOR, RecommendedSection.DETAIL),
    ]

    planner = SectionPlanner()
    sections = planner.plan(widgets)

    # Validate section roles
    roles = [sec.role for sec in sections]
    assert BlueprintSectionRole.OVERVIEW in roles, "Overview section should exist"
    assert BlueprintSectionRole.MAIN_ANALYSIS in roles, "Main analysis section should exist"
    assert BlueprintSectionRole.COMPARISON in roles, "Comparison section should exist"
    assert BlueprintSectionRole.MONITORING in roles, "Monitoring section should exist"
    assert BlueprintSectionRole.DETAIL in roles, "Detail section should exist"
    assert BlueprintSectionRole.GEOGRAPHIC not in roles, "Geographic section should NOT exist (no geo widgets)"

    # Validate widget assignment
    overview_sec = next(s for s in sections if s.role == BlueprintSectionRole.OVERVIEW)
    assert "test_kpi1" in overview_sec.widget_ids, "KPI 1 should be in Overview"
    assert "test_kpi2" in overview_sec.widget_ids, "KPI 2 should be in Overview"

    print("[OK] Section Planning Test PASSED")
    for sec in sections:
        print(f"  - Section: {sec.role.value} ({sec.title}), widgets: {sec.widget_ids}")


# ============================================================
# Test Case: Widget Grouping
# ============================================================

def test_widget_grouping():
    """Test 3: Widget grouping by business_topic

    Expected:
    - sales topic group
    - customer topic group
    - general topic group
    - Groups sorted by avg_importance descending
    """
    print("\n" + "=" * 60)
    print("Test 3: Widget Grouping")
    print("=" * 60)

    widgets = [
        make_widget("sales1", "Sales Trend", BusinessTopic.SALES, VisualRole.PRIMARY_TREND,
                    AnalyticalRole.MONITOR, 0.85, PriorityLevel.HERO, RecommendedSection.MAIN_ANALYSIS),
        make_widget("sales2", "Sales Ranking", BusinessTopic.SALES, VisualRole.RANKING,
                    AnalyticalRole.COMPARE, 0.70, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
        make_widget("cust1", "Retention", BusinessTopic.CUSTOMER, VisualRole.OVERVIEW_METRIC,
                    AnalyticalRole.MONITOR, 0.75, PriorityLevel.MAJOR, RecommendedSection.OVERVIEW),
        make_widget("gen1", "Distribution", BusinessTopic.GENERAL, VisualRole.DISTRIBUTION,
                    AnalyticalRole.EXPLAIN, 0.30, PriorityLevel.MINOR, RecommendedSection.DETAIL),
    ]

    engine = WidgetGroupingEngine()
    groups = engine.group(widgets)

    # Validate group topics
    topics = [g.topic for g in groups]
    assert "sales" in topics, "Sales group should exist"
    assert "customer" in topics, "Customer group should exist"
    assert "general" in topics, "General group should exist"

    # Validate sorting (avg_importance descending)
    for i in range(len(groups) - 1):
        assert groups[i].avg_importance >= groups[i + 1].avg_importance, "Groups should be sorted by avg_importance"

    # Validate sales group
    sales_group = next(g for g in groups if g.topic == "sales")
    assert "test_sales1" in sales_group.widget_ids, "Sales Trend should be in sales group"
    assert "test_sales2" in sales_group.widget_ids, "Sales Ranking should be in sales group"
    assert "primary_trend" in sales_group.visual_roles, "Sales group should have primary_trend"
    assert "ranking" in sales_group.visual_roles, "Sales group should have ranking"

    print("[OK] Widget Grouping Test PASSED")
    for g in groups:
        print(f"  - Group: {g.topic} ({g.title}), widgets: {g.widget_ids}, avg_importance: {g.avg_importance:.2f}")


# ============================================================
# Test Case: Priority and Reading Flow
# ============================================================

def test_priority_and_reading_flow():
    """Test 4: Priority and Reading Flow

    Expected:
    - Hero widgets listed first
    - Reading Flow follows executive pattern: Overview -> Main -> Comparison -> Detail
    - Flow type matches strategy
    """
    print("\n" + "=" * 60)
    print("Test 4: Priority and Reading Flow")
    print("=" * 60)

    widgets = [
        make_widget("hero1", "Hero KPI", BusinessTopic.SALES, VisualRole.OVERVIEW_METRIC,
                    AnalyticalRole.MONITOR, 0.95, PriorityLevel.HERO, RecommendedSection.OVERVIEW),
        make_widget("hero2", "Hero Trend", BusinessTopic.GROWTH, VisualRole.PRIMARY_TREND,
                    AnalyticalRole.MONITOR, 0.88, PriorityLevel.HERO, RecommendedSection.MAIN_ANALYSIS),
        make_widget("major1", "Major Rank", BusinessTopic.SALES, VisualRole.RANKING,
                    AnalyticalRole.COMPARE, 0.70, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
        make_widget("minor1", "Minor Detail", BusinessTopic.GENERAL, VisualRole.DETAIL,
                    AnalyticalRole.EXPLAIN, 0.30, PriorityLevel.MINOR, RecommendedSection.DETAIL),
    ]

    planner = DashboardCompositionPlanner()
    blueprint = planner.plan(widgets, title="Test Dashboard")

    # Validate visual hierarchy
    hierarchy = blueprint.visual_hierarchy
    assert hierarchy.hero_count == 2, f"Expected 2 hero widgets, got {hierarchy.hero_count}"
    assert hierarchy.major_count == 1, f"Expected 1 major widget, got {hierarchy.major_count}"
    assert hierarchy.minor_count == 1, f"Expected 1 minor widget, got {hierarchy.minor_count}"
    assert "test_hero1" in hierarchy.hero_widgets, "Hero KPI should be in hero list"
    assert "test_hero2" in hierarchy.hero_widgets, "Hero Trend should be in hero list"

    # Validate reading flow
    flow = blueprint.reading_flow
    assert flow.flow_type in ("executive", "sales", "analytical"), f"Unexpected flow type: {flow.flow_type}"
    assert len(flow.steps) >= 3, f"Expected >= 3 flow steps, got {len(flow.steps)}"

    # Check flow order: Overview should be first
    if flow.steps:
        assert flow.steps[0].role == "overview", f"First step should be overview, got {flow.steps[0].role}"

    print("[OK] Priority and Reading Flow Test PASSED")
    print(f"  - Visual Hierarchy: Hero={hierarchy.hero_count}, Major={hierarchy.major_count}, Minor={hierarchy.minor_count}")
    print(f"  - Reading Flow Type: {flow.flow_type}")
    print(f"  - Flow Steps:")
    for step in flow.steps:
        print(f"    {step.order}. {step.title} ({step.role}) - {step.purpose}")


# ============================================================
# Test Case: Composition Graph
# ============================================================

def test_composition_graph():
    """Test 5: Composition Graph

    Expected:
    - Edges built from widget related_widgets
    - Clusters identified around core widgets
    - Graph contains correct nodes
    """
    print("\n" + "=" * 60)
    print("Test 5: Composition Graph")
    print("=" * 60)

    widgets = [
        make_widget(
            "trend_core", "Sales Trend",
            BusinessTopic.SALES, VisualRole.PRIMARY_TREND,
            AnalyticalRole.MONITOR, 0.88, PriorityLevel.HERO,
            RecommendedSection.MAIN_ANALYSIS,
            related_widgets=[
                WidgetRelation(target_widget_id="test_region_comp", relation_type=RelationType.EXPLAIN, description="Region explains trend"),
                WidgetRelation(target_widget_id="test_product_comp", relation_type=RelationType.EXPLAIN, description="Product explains trend"),
            ],
        ),
        make_widget("region_comp", "Region Analysis",
                    BusinessTopic.SALES, VisualRole.RANKING,
                    AnalyticalRole.COMPARE, 0.70, PriorityLevel.MAJOR,
                    RecommendedSection.COMPARISON),
        make_widget("product_comp", "Product Analysis",
                    BusinessTopic.PRODUCT, VisualRole.COMPOSITION,
                    AnalyticalRole.EXPLAIN, 0.65, PriorityLevel.MAJOR,
                    RecommendedSection.COMPARISON),
    ]

    builder = CompositionGraphBuilder()
    graph = builder.build(widgets)

    # Validate nodes
    assert len(graph.nodes) == 3, f"Expected 3 nodes, got {len(graph.nodes)}"
    assert "test_trend_core" in graph.nodes, "Trend core should be a node"
    assert "test_region_comp" in graph.nodes, "Region comp should be a node"
    assert "test_product_comp" in graph.nodes, "Product comp should be a node"

    # Validate edges
    assert len(graph.edges) >= 2, f"Expected >= 2 edges, got {len(graph.edges)}"
    edge_types = [e.relation_type for e in graph.edges]
    assert "explain" in edge_types, "Should have explain edges"

    # Validate clusters
    assert len(graph.clusters) >= 1, f"Expected >= 1 cluster, got {len(graph.clusters)}"
    cluster = graph.clusters[0]
    assert cluster.core_widget_id == "test_trend_core", f"Core should be trend, got {cluster.core_widget_id}"
    assert "test_region_comp" in cluster.member_ids, "Region should be in cluster"
    assert "test_product_comp" in cluster.member_ids, "Product should be in cluster"

    print("[OK] Composition Graph Test PASSED")
    print(f"  - Nodes: {len(graph.nodes)}")
    print(f"  - Edges: {len(graph.edges)}")
    print(f"  - Clusters: {len(graph.clusters)}")
    for cluster in graph.clusters:
        print(f"    Cluster: core={cluster.core_widget_id}, type={cluster.cluster_type}, members={cluster.member_ids}")


# ============================================================
# Test Case: Strategy Selection
# ============================================================

def test_strategy_selection():
    """Test 6: Composition Strategy Selection

    Expected:
    - Sales-dominant widgets -> sales strategy
    - Risk-dominant widgets -> risk strategy
    - Customer-dominant widgets -> customer strategy
    - General widgets -> general strategy
    """
    print("\n" + "=" * 60)
    print("Test 6: Strategy Selection")
    print("=" * 60)

    selector = CompositionStrategySelector()

    # Test 6a: Sales dominant
    sales_widgets = [
        make_widget("s1", "Sales 1", BusinessTopic.SALES, VisualRole.PRIMARY_TREND,
                    AnalyticalRole.MONITOR, 0.85, PriorityLevel.HERO, RecommendedSection.MAIN_ANALYSIS),
        make_widget("s2", "Sales 2", BusinessTopic.SALES, VisualRole.RANKING,
                    AnalyticalRole.COMPARE, 0.70, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
        make_widget("g1", "Gen", BusinessTopic.GENERAL, VisualRole.DETAIL,
                    AnalyticalRole.EXPLAIN, 0.30, PriorityLevel.MINOR, RecommendedSection.DETAIL),
    ]
    strategy = selector.select(sales_widgets)
    assert strategy.name == "sales", f"Expected sales strategy, got {strategy.name}"
    print(f"  [OK] Sales dominant -> {strategy.name} ({strategy.display_name})")

    # Test 6b: Risk dominant
    risk_widgets = [
        make_widget("r1", "Risk 1", BusinessTopic.RISK, VisualRole.WARNING,
                    AnalyticalRole.DISCOVER, 0.80, PriorityLevel.MAJOR, RecommendedSection.MONITORING),
        make_widget("r2", "Risk 2", BusinessTopic.RISK, VisualRole.RANKING,
                    AnalyticalRole.EVALUATE, 0.70, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
    ]
    strategy = selector.select(risk_widgets)
    assert strategy.name == "risk", f"Expected risk strategy, got {strategy.name}"
    print(f"  [OK] Risk dominant -> {strategy.name} ({strategy.display_name})")

    # Test 6c: Customer dominant
    cust_widgets = [
        make_widget("c1", "Customer 1", BusinessTopic.CUSTOMER, VisualRole.OVERVIEW_METRIC,
                    AnalyticalRole.MONITOR, 0.80, PriorityLevel.MAJOR, RecommendedSection.OVERVIEW),
        make_widget("c2", "Customer 2", BusinessTopic.CUSTOMER, VisualRole.PRIMARY_TREND,
                    AnalyticalRole.MONITOR, 0.70, PriorityLevel.MAJOR, RecommendedSection.MAIN_ANALYSIS),
    ]
    strategy = selector.select(cust_widgets)
    assert strategy.name == "customer", f"Expected customer strategy, got {strategy.name}"
    print(f"  [OK] Customer dominant -> {strategy.name} ({strategy.display_name})")

    # Test 6d: General fallback
    gen_widgets = [
        make_widget("g1", "Gen 1", BusinessTopic.GENERAL, VisualRole.DETAIL,
                    AnalyticalRole.EXPLAIN, 0.40, PriorityLevel.MINOR, RecommendedSection.DETAIL),
    ]
    strategy = selector.select(gen_widgets)
    assert strategy.name == "general", f"Expected general strategy, got {strategy.name}"
    print(f"  [OK] General fallback -> {strategy.name} ({strategy.display_name})")

    print("[OK] Strategy Selection Test PASSED")


# ============================================================
# Run All Tests
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Dashboard Composition Planner - Test Suite")
    print("=" * 60)

    try:
        blueprint = test_full_pipeline()
        test_section_planning()
        test_widget_grouping()
        test_priority_and_reading_flow()
        test_composition_graph()
        test_strategy_selection()
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Save Blueprint JSON
    if blueprint:
        output_path = os.path.join(os.path.dirname(__file__), "composition_planner_test_output.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(blueprint.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"\nBlueprint JSON saved to: {output_path}")

    print("\n" + "=" * 60)
    print("All 6 tests PASSED")
    print("=" * 60)
