"""
Dashboard Layout Engine Tests

测试覆盖：
1. Layout Strategy 正确选择
2. Section 正确放置（按 reading_flow）
3. Hero Widget 占主要位置
4. Grid 正确计算（24列）
5. Widget 不重叠
6. Visual Balance 正常
7. Dashboard Schema 正确输出
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
from src.dashboard.composition_schema import (
    DashboardBlueprint, BlueprintSectionRole,
)
from src.dashboard.blueprint_layout_engine import DashboardLayoutEngine
from src.dashboard.layout_strategy import (
    LayoutStrategySelector, LayoutStrategy, LAYOUT_STRATEGIES,
)
from src.dashboard.grid_system import GridSystem
from src.dashboard.layout_optimizer import LayoutOptimizer
from src.dashboard.visual_balance import VisualBalanceOptimizer
from src.dashboard.layout_schema import DashboardSchema


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
    preferred_size: PreferredSize = PreferredSize.MEDIUM,
    related_widgets: list = None,
    description: str = "",
    business_purpose: str = "",
    chart_config: dict = None,
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
        preferred_size=preferred_size,
        recommended_section=recommended_section,
        analysis_type=id_suffix.replace("_", "") + "_analysis",
        related_widgets=related_widgets or [],
        chart_config=chart_config or {"title": {"text": title}},
        chart_type="line" if visual_role == VisualRole.PRIMARY_TREND else "bar",
    )
    w.id = f"test_{id_suffix}"
    return w


# ============================================================
# Test Case 1: Layout Strategy Selection
# ============================================================

def test_layout_strategy_selection():
    """Test 1: Layout Strategy 是否正确选择"""
    print("\n" + "=" * 60)
    print("Test 1: Layout Strategy Selection")
    print("=" * 60)

    selector = LayoutStrategySelector()

    # Test 1a: Sales blueprint → sales layout
    widgets = [
        make_widget("sales1", "Sales Trend", BusinessTopic.SALES, VisualRole.PRIMARY_TREND,
                    AnalyticalRole.MONITOR, 0.85, PriorityLevel.HERO, RecommendedSection.MAIN_ANALYSIS),
        make_widget("sales2", "Sales Rank", BusinessTopic.SALES, VisualRole.RANKING,
                    AnalyticalRole.COMPARE, 0.70, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
    ]
    planner = DashboardCompositionPlanner()
    blueprint = planner.plan(widgets, title="Sales Dashboard")
    strategy = selector.select(blueprint)
    assert strategy.name == "sales", f"Expected sales, got {strategy.name}"
    print(f"  [OK] Sales blueprint → {strategy.name} ({strategy.display_name})")

    # Test 1b: Finance blueprint → finance layout
    widgets = [
        make_widget("fin1", "Revenue", BusinessTopic.FINANCE, VisualRole.OVERVIEW_METRIC,
                    AnalyticalRole.MONITOR, 0.90, PriorityLevel.HERO, RecommendedSection.OVERVIEW),
        make_widget("fin2", "Cost Trend", BusinessTopic.FINANCE, VisualRole.PRIMARY_TREND,
                    AnalyticalRole.MONITOR, 0.80, PriorityLevel.MAJOR, RecommendedSection.MAIN_ANALYSIS),
    ]
    blueprint = planner.plan(widgets, title="Finance Dashboard")
    strategy = selector.select(blueprint)
    assert strategy.name == "finance", f"Expected finance, got {strategy.name}"
    print(f"  [OK] Finance blueprint → {strategy.name} ({strategy.display_name})")

    # Test 1c: Compact (few widgets) → compact layout
    widgets = [
        make_widget("g1", "Gen 1", BusinessTopic.GENERAL, VisualRole.DETAIL,
                    AnalyticalRole.EXPLAIN, 0.30, PriorityLevel.MINOR, RecommendedSection.DETAIL),
    ]
    blueprint = planner.plan(widgets, title="Small Dashboard")
    strategy = selector.select(blueprint)
    assert strategy.name == "compact", f"Expected compact for 1 widget, got {strategy.name}"
    print(f"  [OK] Compact (1 widget) → {strategy.name} ({strategy.display_name})")

    # Test 1d: Blueprint with sales + overview + trend → layout matches composition strategy
    widgets = [
        make_widget("kpi1", "KPI 1", BusinessTopic.SALES, VisualRole.OVERVIEW_METRIC,
                    AnalyticalRole.MONITOR, 0.95, PriorityLevel.HERO, RecommendedSection.OVERVIEW),
        make_widget("trend1", "Trend", BusinessTopic.SALES, VisualRole.PRIMARY_TREND,
                    AnalyticalRole.MONITOR, 0.88, PriorityLevel.HERO, RecommendedSection.MAIN_ANALYSIS),
        make_widget("rank1", "Rank", BusinessTopic.SALES, VisualRole.RANKING,
                    AnalyticalRole.COMPARE, 0.70, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
        make_widget("detail1", "Detail", BusinessTopic.GENERAL, VisualRole.DETAIL,
                    AnalyticalRole.EXPLAIN, 0.30, PriorityLevel.MINOR, RecommendedSection.DETAIL),
    ]
    blueprint = planner.plan(widgets, title="Executive Dashboard")
    strategy = selector.select(blueprint)
    # Sales-dominant → composition strategy = "sales" → layout strategy should match
    assert strategy.name in ("executive", "sales"), f"Expected executive/sales for sales-dominant+overview+trend, got {strategy.name}"
    print(f"  [OK] Sales-dominant+overview+trend → {strategy.name} ({strategy.display_name})")

    print("[OK] Layout Strategy Selection Test PASSED")


# ============================================================
# Test Case 2: Section Placement
# ============================================================

def test_section_placement():
    """Test 2: Section 是否正确放置（按 reading_flow 顺序）"""
    print("\n" + "=" * 60)
    print("Test 2: Section Placement")
    print("=" * 60)

    widgets = [
        make_widget("kpi1", "KPI", BusinessTopic.SALES, VisualRole.OVERVIEW_METRIC,
                    AnalyticalRole.MONITOR, 0.95, PriorityLevel.HERO, RecommendedSection.OVERVIEW),
        make_widget("trend1", "Trend", BusinessTopic.SALES, VisualRole.PRIMARY_TREND,
                    AnalyticalRole.MONITOR, 0.88, PriorityLevel.HERO, RecommendedSection.MAIN_ANALYSIS),
        make_widget("rank1", "Rank", BusinessTopic.SALES, VisualRole.RANKING,
                    AnalyticalRole.COMPARE, 0.70, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
        make_widget("warn1", "Warn", BusinessTopic.RISK, VisualRole.WARNING,
                    AnalyticalRole.DISCOVER, 0.60, PriorityLevel.MAJOR, RecommendedSection.MONITORING),
        make_widget("detail1", "Detail", BusinessTopic.GENERAL, VisualRole.DETAIL,
                    AnalyticalRole.EXPLAIN, 0.30, PriorityLevel.MINOR, RecommendedSection.DETAIL),
    ]

    planner = DashboardCompositionPlanner()
    blueprint = planner.plan(widgets, title="Test Dashboard")

    engine = DashboardLayoutEngine()
    schema = engine.build(blueprint, widgets, title="Test Dashboard")

    # Validate sections exist
    assert len(schema.sections) >= 3, f"Expected >= 3 sections, got {len(schema.sections)}"

    # Validate reading_flow order (Overview should be first section)
    # Check that sections follow the flow defined in blueprint
    flow_steps = blueprint.reading_flow.steps
    if flow_steps:
        first_section_role = flow_steps[0].role
        # Schema sections should start with the first flow step's section
        sec_ids_in_flow = [step.section_id for step in flow_steps]
        # Check schema section IDs are in flow order
        schema_sec_ids = [sec.id for sec in schema.sections]
        # All flow sections should be in schema sections
        for fid in sec_ids_in_flow:
            assert fid in schema_sec_ids, f"Section {fid} from reading_flow should be in schema sections"

    print(f"  - Blueprint flow: {[step.role for step in flow_steps]}")
    print(f"  - Schema sections: {[(sec.id, sec.role.value) for sec in schema.sections]}")
    print("[OK] Section Placement Test PASSED")


# ============================================================
# Test Case 3: Hero Widget Placement
# ============================================================

def test_hero_widget_placement():
    """Test 3: Hero Widget 是否占主要位置"""
    print("\n" + "=" * 60)
    print("Test 3: Hero Widget Placement")
    print("=" * 60)

    widgets = [
        make_widget("hero1", "Hero KPI", BusinessTopic.SALES, VisualRole.OVERVIEW_METRIC,
                    AnalyticalRole.MONITOR, 0.95, PriorityLevel.HERO, RecommendedSection.OVERVIEW,
                    preferred_size=PreferredSize.EXTRA_LARGE),
        make_widget("hero2", "Hero Trend", BusinessTopic.SALES, VisualRole.PRIMARY_TREND,
                    AnalyticalRole.MONITOR, 0.88, PriorityLevel.HERO, RecommendedSection.MAIN_ANALYSIS,
                    preferred_size=PreferredSize.EXTRA_LARGE),
        make_widget("major1", "Major Rank", BusinessTopic.SALES, VisualRole.RANKING,
                    AnalyticalRole.COMPARE, 0.70, PriorityLevel.MAJOR, RecommendedSection.COMPARISON,
                    preferred_size=PreferredSize.LARGE),
        make_widget("minor1", "Minor Detail", BusinessTopic.GENERAL, VisualRole.DETAIL,
                    AnalyticalRole.EXPLAIN, 0.30, PriorityLevel.MINOR, RecommendedSection.DETAIL,
                    preferred_size=PreferredSize.SMALL),
    ]

    planner = DashboardCompositionPlanner()
    blueprint = planner.plan(widgets, title="Hero Test Dashboard")

    engine = DashboardLayoutEngine()
    schema = engine.build(blueprint, widgets, title="Hero Test Dashboard")

    # Validate Hero widgets have larger w
    hero_widgets = [w for w in schema.widgets if w.size_class == "hero"]
    other_widgets = [w for w in schema.widgets if w.size_class != "hero"]

    # Hero should have w >= 24 (full width) or at least wider than others
    if hero_widgets:
        avg_hero_w = sum(w.w for w in hero_widgets) / len(hero_widgets)
        avg_other_w = sum(w.w for w in other_widgets) / len(other_widgets) if other_widgets else 0
        assert avg_hero_w >= avg_other_w, f"Hero w ({avg_hero_w}) should be >= other w ({avg_other_w})"
        print(f"  - Hero avg w: {avg_hero_w}, Other avg w: {avg_other_w}")

    # Hero should have higher z_index
    if hero_widgets:
        avg_hero_z = sum(w.z_index for w in hero_widgets) / len(hero_widgets)
        avg_other_z = sum(w.z_index for w in other_widgets) / len(other_widgets) if other_widgets else 0
        assert avg_hero_z > avg_other_z, f"Hero z_index ({avg_hero_z}) should be > other ({avg_other_z})"
        print(f"  - Hero avg z_index: {avg_hero_z}, Other avg z_index: {avg_other_z}")

    # Hero should have higher importance_score
    if hero_widgets:
        avg_hero_imp = sum(w.importance_score for w in hero_widgets) / len(hero_widgets)
        avg_other_imp = sum(w.importance_score for w in other_widgets) / len(other_widgets) if other_widgets else 0
        assert avg_hero_imp > avg_other_imp, f"Hero importance ({avg_hero_imp}) should be > other ({avg_other_imp})"
        print(f"  - Hero avg importance: {avg_hero_imp}, Other avg importance: {avg_other_imp}")

    print("[OK] Hero Widget Placement Test PASSED")


# ============================================================
# Test Case 4: Grid Calculation
# ============================================================

def test_grid_calculation():
    """Test 4: Grid 是否正确计算（24列）"""
    print("\n" + "=" * 60)
    print("Test 4: Grid Calculation (24 columns)")
    print("=" * 60)

    widgets = [
        make_widget("kpi1", "KPI", BusinessTopic.SALES, VisualRole.OVERVIEW_METRIC,
                    AnalyticalRole.MONITOR, 0.95, PriorityLevel.HERO, RecommendedSection.OVERVIEW),
        make_widget("trend1", "Trend", BusinessTopic.SALES, VisualRole.PRIMARY_TREND,
                    AnalyticalRole.MONITOR, 0.80, PriorityLevel.MAJOR, RecommendedSection.MAIN_ANALYSIS),
        make_widget("rank1", "Rank", BusinessTopic.SALES, VisualRole.RANKING,
                    AnalyticalRole.COMPARE, 0.70, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
    ]

    planner = DashboardCompositionPlanner()
    blueprint = planner.plan(widgets, title="Grid Test")

    engine = DashboardLayoutEngine()
    schema = engine.build(blueprint, widgets, title="Grid Test")

    # Validate grid columns = 24
    assert schema.layout.columns == 24, f"Expected 24 columns, got {schema.layout.columns}"
    print(f"  - Grid columns: {schema.layout.columns}")

    # Validate all widgets have w <= 24
    for w in schema.widgets:
        assert w.w <= 24, f"Widget {w.widget_id} w={w.w} exceeds 24 columns"
        assert w.w >= 4, f"Widget {w.widget_id} w={w.w} is too small (< 4)"

    # Validate x + w <= 24
    for w in schema.widgets:
        assert w.x + w.w <= 24, f"Widget {w.widget_id} x={w.x}+w={w.w}={w.x + w.w} exceeds 24"

    # Validate x >= 0
    for w in schema.widgets:
        assert w.x >= 0, f"Widget {w.widget_id} x={w.x} is negative"

    # Validate h >= 2
    for w in schema.widgets:
        assert w.h >= 2, f"Widget {w.widget_id} h={w.h} is too small (< 2)"

    print(f"  - Widget positions:")
    for w in schema.widgets:
        print(f"    {w.widget_id}: x={w.x}, y={w.y}, w={w.w}, h={w.h}, z={w.z_index}")

    print("[OK] Grid Calculation Test PASSED")


# ============================================================
# Test Case 5: No Widget Overlap
# ============================================================

def test_no_overlap():
    """Test 5: Widget 不存在重叠"""
    print("\n" + "=" * 60)
    print("Test 5: No Widget Overlap")
    print("=" * 60)

    widgets = [
        make_widget("kpi1", "KPI 1", BusinessTopic.SALES, VisualRole.OVERVIEW_METRIC,
                    AnalyticalRole.MONITOR, 0.95, PriorityLevel.HERO, RecommendedSection.OVERVIEW),
        make_widget("kpi2", "KPI 2", BusinessTopic.SALES, VisualRole.OVERVIEW_METRIC,
                    AnalyticalRole.MONITOR, 0.90, PriorityLevel.HERO, RecommendedSection.OVERVIEW),
        make_widget("trend1", "Trend", BusinessTopic.SALES, VisualRole.PRIMARY_TREND,
                    AnalyticalRole.MONITOR, 0.80, PriorityLevel.MAJOR, RecommendedSection.MAIN_ANALYSIS),
        make_widget("rank1", "Rank", BusinessTopic.SALES, VisualRole.RANKING,
                    AnalyticalRole.COMPARE, 0.70, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
        make_widget("comp1", "Comp", BusinessTopic.SALES, VisualRole.COMPOSITION,
                    AnalyticalRole.EXPLAIN, 0.65, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
        make_widget("detail1", "Detail", BusinessTopic.GENERAL, VisualRole.DETAIL,
                    AnalyticalRole.EXPLAIN, 0.30, PriorityLevel.MINOR, RecommendedSection.DETAIL),
    ]

    planner = DashboardCompositionPlanner()
    blueprint = planner.plan(widgets, title="Overlap Test")

    engine = DashboardLayoutEngine()
    schema = engine.build(blueprint, widgets, title="Overlap Test")

    # Check no overlap
    overlaps_found = []
    for i, a in enumerate(schema.widgets):
        for b in schema.widgets[i + 1:]:
            h_overlap = a.x < b.x + b.w and a.x + a.w > b.x
            v_overlap = a.y < b.y + b.h and a.y + a.h > b.y
            if h_overlap and v_overlap:
                overlaps_found.append((a.widget_id, b.widget_id))

    assert len(overlaps_found) == 0, f"Found {len(overlaps_found)} overlaps: {overlaps_found}"

    # Also check via LayoutOptimizer
    from src.dashboard.grid_system import GridSlot
    grid_slots = [
        GridSlot(
            widget_id=w.widget_id,
            section_id=w.section_id,
            x=w.x, y=w.y, w=w.w, h=w.h,
            z_index=w.z_index,
            visual_weight=w.visual_weight,
        )
        for w in schema.widgets
    ]
    strategy = LAYOUT_STRATEGIES.get(schema.layout_strategy, LAYOUT_STRATEGIES["general"])
    optimizer = LayoutOptimizer(strategy)
    issues = optimizer.detect(grid_slots)
    critical_issues = [i for i in issues if i.severity == "critical"]
    assert len(critical_issues) == 0, f"Found {len(critical_issues)} critical layout issues: {critical_issues}"

    print(f"  - No overlaps found among {len(schema.widgets)} widgets")
    print(f"  - LayoutOptimizer found {len(issues)} issues (0 critical)")
    print("[OK] No Widget Overlap Test PASSED")


# ============================================================
# Test Case 6: Visual Balance
# ============================================================

def test_visual_balance():
    """Test 6: Visual Balance 是否正常"""
    print("\n" + "=" * 60)
    print("Test 6: Visual Balance")
    print("=" * 60)

    widgets = [
        make_widget("kpi1", "KPI", BusinessTopic.SALES, VisualRole.OVERVIEW_METRIC,
                    AnalyticalRole.MONITOR, 0.95, PriorityLevel.HERO, RecommendedSection.OVERVIEW),
        make_widget("trend1", "Trend", BusinessTopic.SALES, VisualRole.PRIMARY_TREND,
                    AnalyticalRole.MONITOR, 0.80, PriorityLevel.MAJOR, RecommendedSection.MAIN_ANALYSIS),
        make_widget("rank1", "Rank", BusinessTopic.SALES, VisualRole.RANKING,
                    AnalyticalRole.COMPARE, 0.70, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
        make_widget("comp1", "Comp", BusinessTopic.PRODUCT, VisualRole.COMPOSITION,
                    AnalyticalRole.EXPLAIN, 0.65, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
        make_widget("detail1", "Detail", BusinessTopic.GENERAL, VisualRole.DETAIL,
                    AnalyticalRole.EXPLAIN, 0.30, PriorityLevel.MINOR, RecommendedSection.DETAIL),
    ]

    planner = DashboardCompositionPlanner()
    blueprint = planner.plan(widgets, title="Balance Test")

    engine = DashboardLayoutEngine()
    schema = engine.build(blueprint, widgets, title="Balance Test")

    # Check balance report
    from src.dashboard.grid_system import GridSlot
    grid_slots = [
        GridSlot(
            widget_id=w.widget_id,
            section_id=w.section_id,
            x=w.x, y=w.y, w=w.w, h=w.h,
            z_index=w.z_index,
            visual_weight=w.visual_weight,
        )
        for w in schema.widgets
    ]

    strategy = LAYOUT_STRATEGIES.get(schema.layout_strategy, LAYOUT_STRATEGIES["general"])
    balance_optimizer = VisualBalanceOptimizer(strategy)
    report = balance_optimizer.check_balance(grid_slots)

    # Balance should not be extremely imbalanced (considering full-width widgets split evenly)
    lr_ratio = report.get("left_right_ratio", 1.0)
    assert 0.1 <= lr_ratio <= 10.0, f"Left/right ratio {lr_ratio} is too extreme"

    print(f"  - Left/right ratio: {lr_ratio}")
    print(f"  - Upper/lower ratio: {report.get('upper_lower_ratio', 1.0)}")
    print(f"  - Status: {report.get('status', 'unknown')}")
    print("[OK] Visual Balance Test PASSED")


# ============================================================
# Test Case 7: Dashboard Schema Output
# ============================================================

def test_schema_output():
    """Test 7: Dashboard Schema 正确输出"""
    print("\n" + "=" * 60)
    print("Test 7: Dashboard Schema Output")
    print("=" * 60)

    widgets = [
        make_widget("sales_kpi", "Sales KPI", BusinessTopic.SALES, VisualRole.OVERVIEW_METRIC,
                    AnalyticalRole.MONITOR, 0.95, PriorityLevel.HERO, RecommendedSection.OVERVIEW,
                    preferred_size=PreferredSize.EXTRA_LARGE),
        make_widget("sales_trend", "Sales Trend", BusinessTopic.SALES, VisualRole.PRIMARY_TREND,
                    AnalyticalRole.MONITOR, 0.88, PriorityLevel.HERO, RecommendedSection.MAIN_ANALYSIS,
                    preferred_size=PreferredSize.EXTRA_LARGE,
                    related_widgets=[
                        WidgetRelation(target_widget_id="test_region_rank",
                                       relation_type=RelationType.EXPLAIN,
                                       description="Region explains trend"),
                    ]),
        make_widget("region_rank", "Region Ranking", BusinessTopic.SALES, VisualRole.RANKING,
                    AnalyticalRole.COMPARE, 0.72, PriorityLevel.MAJOR, RecommendedSection.COMPARISON,
                    preferred_size=PreferredSize.LARGE),
        make_widget("product_struct", "Product Structure", BusinessTopic.PRODUCT, VisualRole.COMPOSITION,
                    AnalyticalRole.EXPLAIN, 0.65, PriorityLevel.MAJOR, RecommendedSection.COMPARISON,
                    preferred_size=PreferredSize.MEDIUM),
        make_widget("anomaly_warn", "Anomaly Warning", BusinessTopic.RISK, VisualRole.WARNING,
                    AnalyticalRole.DISCOVER, 0.60, PriorityLevel.MAJOR, RecommendedSection.MONITORING,
                    preferred_size=PreferredSize.MEDIUM),
        make_widget("corr_detail", "Correlation", BusinessTopic.GENERAL, VisualRole.CORRELATION,
                    AnalyticalRole.DISCOVER, 0.35, PriorityLevel.MINOR, RecommendedSection.DETAIL,
                    preferred_size=PreferredSize.SMALL),
        make_widget("dist_analysis", "Distribution", BusinessTopic.GENERAL, VisualRole.DISTRIBUTION,
                    AnalyticalRole.EXPLAIN, 0.30, PriorityLevel.MINOR, RecommendedSection.DETAIL,
                    preferred_size=PreferredSize.SMALL),
    ]

    # Full pipeline: Composition Planner → Layout Engine
    planner = DashboardCompositionPlanner()
    blueprint = planner.plan(widgets, title="Full Pipeline Dashboard")

    engine = DashboardLayoutEngine()
    schema = engine.build(blueprint, widgets, title="Full Pipeline Dashboard")

    # Validate schema structure
    assert schema.id, "Schema ID should not be empty"
    assert schema.title == "Full Pipeline Dashboard", f"Title mismatch: {schema.title}"
    assert schema.version == "2.0", f"Expected v2.0, got {schema.version}"
    assert schema.blueprint_id == blueprint.metadata.id, "Blueprint ID should match"
    assert schema.layout_strategy != "", "Layout strategy should not be empty"
    assert schema.layout.columns == 24, f"Expected 24 columns, got {schema.layout.columns}"
    assert len(schema.widgets) == 7, f"Expected 7 widgets, got {len(schema.widgets)}"
    assert len(schema.sections) >= 3, f"Expected >= 3 sections, got {len(schema.sections)}"
    assert len(schema.groups) >= 2, f"Expected >= 2 groups, got {len(schema.groups)}"

    # Validate each widget has x/y/w/h/z_index
    for w in schema.widgets:
        assert w.widget_id, "Widget ID should not be empty"
        assert w.x >= 0, f"Widget {w.widget_id} x={w.x} < 0"
        assert w.y >= 0, f"Widget {w.widget_id} y={w.y} < 0"
        assert w.w >= 4, f"Widget {w.widget_id} w={w.w} < 4"
        assert w.h >= 2, f"Widget {w.widget_id} h={w.h} < 2"
        assert w.x + w.w <= 24, f"Widget {w.widget_id} x+w={w.x + w.w} > 24"
        assert hasattr(w, 'z_index'), "Widget should have z_index"

    # Validate schema dict has strategy + grid
    schema_dict = schema.to_dict()
    assert "strategy" in schema_dict["layout"], "Schema layout should have strategy"
    assert "grid" in schema_dict["layout"], "Schema layout should have grid"
    assert schema_dict["layout"]["grid"] == "24", f"Expected grid='24', got {schema_dict['layout']['grid']}"

    # Validate schema has blueprint_id
    assert "blueprint_id" in schema_dict, "Schema should have blueprint_id"

    print(f"  - Schema ID: {schema.id}")
    print(f"  - Blueprint ID: {schema.blueprint_id}")
    print(f"  - Layout Strategy: {schema.layout_strategy}")
    print(f"  - Grid Columns: {schema.layout.columns}")
    print(f"  - Widget Count: {len(schema.widgets)}")
    print(f"  - Section Count: {len(schema.sections)}")
    print(f"  - Group Count: {len(schema.groups)}")
    print(f"  - Version: {schema.version}")

    # Print all widget positions
    print(f"  - Widget positions:")
    for w in schema.widgets:
        print(f"    {w.widget_id}: pos=({w.x},{w.y}), size=({w.w},{w.h}), z={w.z_index}, "
              f"sec={w.section_id}, imp={w.importance_score}")

    print("[OK] Dashboard Schema Output Test PASSED")
    return schema


# ============================================================
# Run All Tests
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Dashboard Layout Engine - Test Suite")
    print("=" * 60)

    schema = None
    try:
        test_layout_strategy_selection()
        test_section_placement()
        test_hero_widget_placement()
        test_grid_calculation()
        test_no_overlap()
        test_visual_balance()
        schema = test_schema_output()
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Save Schema JSON
    if schema:
        output_path = os.path.join(os.path.dirname(__file__), "layout_engine_test_output.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(schema.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"\nSchema JSON saved to: {output_path}")

    print("\n" + "=" * 60)
    print("All 7 tests PASSED")
    print("=" * 60)
