"""
Dashboard Interaction Engine Tests

测试覆盖：
1. Global Filter 是否正确生成
2. Cross Filter 是否正确生成
3. Drill Down 是否正确生成
4. Highlight 是否正确生成
5. Interaction Graph (Linkage) 是否正确建立
6. Complete Dashboard Schema 是否正确输出
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
from src.dashboard.layout_schema import DashboardSchema
from src.dashboard.interaction_schema import (
    InteractionSchema, FilterRule, CrossFilterRule, DrillDownRule,
    HighlightRule, WidgetLinkageRule, FilterType, FilterScope,
    InteractionPriority, HighlightType, LinkageType,
)
from src.dashboard.dashboard_interaction_engine import (
    DashboardInteractionEngine, enrich_dashboard_interactions,
)
from src.dashboard.interaction_rules import (
    InteractionRuleEngine, InteractionRule,
)
from src.dashboard.global_filter_generator import GlobalFilterGenerator
from src.dashboard.cross_filter_generator import CrossFilterGenerator
from src.dashboard.drill_down_generator import DrillDownGenerator
from src.dashboard.highlight_generator import HighlightGenerator
from src.dashboard.widget_linkage_builder import WidgetLinkageBuilder


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
    chart_type: str = None,
    supported_filters: list = None,
    description: str = "",
    business_purpose: str = "",
) -> SemanticWidget:
    """创建测试 SemanticWidget"""
    # 默认 chart_type
    if chart_type is None:
        if visual_role == VisualRole.PRIMARY_TREND:
            chart_type = "line"
        elif visual_role == VisualRole.OVERVIEW_METRIC:
            chart_type = None  # KPI no chart_type
        elif visual_role == VisualRole.RANKING:
            chart_type = "bar"
        elif visual_role == VisualRole.COMPOSITION:
            chart_type = "pie"
        elif visual_role == VisualRole.GEOGRAPHIC:
            chart_type = "map"
        elif visual_role == VisualRole.WARNING:
            chart_type = "scatter"
        elif visual_role == VisualRole.DETAIL:
            chart_type = None  # table
        else:
            chart_type = "bar"

    # 默认 supported_filters
    if supported_filters is None:
        # 根据业务主题分配合理筛选器
        filters = []
        filters.append(SemanticFilter(field="time", label="时间范围", filter_type="date_range", business_meaning="筛选时间范围"))
        if business_topic == BusinessTopic.SALES or visual_role in (VisualRole.RANKING, VisualRole.GEOGRAPHIC):
            filters.append(SemanticFilter(field="region", label="地区", filter_type="dropdown", business_meaning="选择地区"))
        if business_topic in (BusinessTopic.SALES, BusinessTopic.PRODUCT) or visual_role in (VisualRole.COMPOSITION, VisualRole.RANKING):
            filters.append(SemanticFilter(field="product", label="产品", filter_type="dropdown", business_meaning="选择产品"))
        if business_topic in (BusinessTopic.FINANCE, BusinessTopic.SALES) or visual_role in (VisualRole.COMPOSITION):
            filters.append(SemanticFilter(field="category", label="分类", filter_type="dropdown", business_meaning="选择分类"))
        supported_filters = filters

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
        chart_type=chart_type,
        supported_filters=supported_filters,
        chart_config={"title": {"text": title}},
    )
    w.id = f"test_{id_suffix}"
    return w


def build_test_schema(widgets, title="Interaction Test Dashboard"):
    """构建测试 DashboardSchema（Layout Engine 输出）"""
    planner = DashboardCompositionPlanner()
    blueprint = planner.plan(widgets, title=title)

    layout_engine = DashboardLayoutEngine()
    schema = layout_engine.build(blueprint, widgets, title=title)
    return schema


# ============================================================
# Test Case 1: Global Filter Generation
# ============================================================

def test_global_filters():
    """Test 1: Global Filter 是否正确生成"""
    print("\n" + "=" * 60)
    print("Test 1: Global Filter Generation")
    print("=" * 60)

    widgets = [
        make_widget("sales_kpi", "Sales KPI", BusinessTopic.SALES, VisualRole.OVERVIEW_METRIC,
                    AnalyticalRole.MONITOR, 0.95, PriorityLevel.HERO, RecommendedSection.OVERVIEW),
        make_widget("sales_trend", "Sales Trend", BusinessTopic.SALES, VisualRole.PRIMARY_TREND,
                    AnalyticalRole.MONITOR, 0.88, PriorityLevel.HERO, RecommendedSection.MAIN_ANALYSIS),
        make_widget("region_rank", "Region Ranking", BusinessTopic.SALES, VisualRole.RANKING,
                    AnalyticalRole.COMPARE, 0.72, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
        make_widget("product_struct", "Product Structure", BusinessTopic.PRODUCT, VisualRole.COMPOSITION,
                    AnalyticalRole.EXPLAIN, 0.65, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
    ]

    schema = build_test_schema(widgets)

    engine = DashboardInteractionEngine()
    complete_schema = engine.enrich(schema)

    interactions = complete_schema.interactions
    global_filters = interactions.get("global_filters", [])

    # 应该有 time 全局筛选器（所有 Widget 都支持 time）
    assert len(global_filters) >= 1, f"Expected >= 1 global filters, got {len(global_filters)}"

    # time 应该是 global scope
    time_filter = next((f for f in global_filters if f["field"] == "time"), None)
    assert time_filter is not None, "time global filter should exist"
    assert time_filter["scope"] == "global", f"time filter scope should be 'global', got {time_filter['scope']}"
    print(f"  [OK] time global filter: scope={time_filter['scope']}, targets={time_filter['target_widgets']}")

    # region 应该存在（3 Widget 支持 region）
    region_filter = next((f for f in global_filters if f["field"] == "region"), None)
    if region_filter:
        print(f"  [OK] region filter: scope={region_filter['scope']}, targets={region_filter['target_widgets']}")

    # 每个 global filter 应有完整字段
    for f in global_filters:
        assert f["id"], f"Filter ID should not be empty"
        assert f["field"], f"Filter field should not be empty"
        assert f["scope"], f"Filter scope should not be empty"
        assert len(f["target_widgets"]) >= 2, f"Global filter should target >= 2 widgets, got {len(f['target_widgets'])}"

    print(f"  - Total global filters: {len(global_filters)}")
    print(f"  - Fields: {[f['field'] for f in global_filters]}")
    print("[OK] Global Filter Generation Test PASSED")


# ============================================================
# Test Case 2: Cross Filter Generation
# ============================================================

def test_cross_filters():
    """Test 2: Cross Filter 是否正确生成"""
    print("\n" + "=" * 60)
    print("Test 2: Cross Filter Generation")
    print("=" * 60)

    widgets = [
        make_widget("sales_bar", "Sales Bar", BusinessTopic.SALES, VisualRole.RANKING,
                    AnalyticalRole.COMPARE, 0.80, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
        make_widget("region_pie", "Region Pie", BusinessTopic.SALES, VisualRole.COMPOSITION,
                    AnalyticalRole.EXPLAIN, 0.70, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
        make_widget("sales_trend", "Sales Trend", BusinessTopic.SALES, VisualRole.PRIMARY_TREND,
                    AnalyticalRole.MONITOR, 0.85, PriorityLevel.HERO, RecommendedSection.MAIN_ANALYSIS),
    ]

    schema = build_test_schema(widgets)

    engine = DashboardInteractionEngine()
    complete_schema = engine.enrich(schema)

    interactions = complete_schema.interactions
    cross_filters = interactions.get("cross_filters", [])

    # bar/pie 应与同 field Widget 产生 cross filter
    if cross_filters:
        # 至少有一个 cross filter（region 共享）
        region_cross = [cf for cf in cross_filters if cf["field"] == "region"]
        if region_cross:
            print(f"  [OK] region cross filter: source={region_cross[0]['source_widget']}, targets={region_cross[0]['targets']}")

    # 每个 cross filter 应有完整字段
    for cf in cross_filters:
        assert cf["source_widget"], "CrossFilter source_widget should not be empty"
        assert cf["field"], "CrossFilter field should not be empty"
        assert len(cf["targets"]) >= 1, f"CrossFilter targets should >= 1, got {len(cf['targets'])}"

    print(f"  - Total cross filters: {len(cross_filters)}")
    print("[OK] Cross Filter Generation Test PASSED")


# ============================================================
# Test Case 3: Drill Down Generation
# ============================================================

def test_drill_downs():
    """Test 3: Drill Down 是否正确生成"""
    print("\n" + "=" * 60)
    print("Test 3: Drill Down Generation")
    print("=" * 60)

    # 创建含地理/产品维度的 Widget
    widgets = [
        make_widget("geo_rank", "Geo Ranking", BusinessTopic.SALES, VisualRole.GEOGRAPHIC,
                    AnalyticalRole.COMPARE, 0.80, PriorityLevel.MAJOR, RecommendedSection.COMPARISON,
                    supported_filters=[
                        SemanticFilter(field="time", label="时间", filter_type="date_range"),
                        SemanticFilter(field="province", label="省份", filter_type="dropdown"),
                        SemanticFilter(field="city", label="城市", filter_type="dropdown"),
                    ]),
        make_widget("product_rank", "Product Ranking", BusinessTopic.PRODUCT, VisualRole.RANKING,
                    AnalyticalRole.COMPARE, 0.70, PriorityLevel.MAJOR, RecommendedSection.COMPARISON,
                    supported_filters=[
                        SemanticFilter(field="time", label="时间", filter_type="date_range"),
                        SemanticFilter(field="category", label="分类", filter_type="dropdown"),
                        SemanticFilter(field="product", label="产品", filter_type="dropdown"),
                    ]),
    ]

    schema = build_test_schema(widgets)

    engine = DashboardInteractionEngine()
    complete_schema = engine.enrich(schema)

    interactions = complete_schema.interactions
    drill_downs = interactions.get("drill_downs", [])

    # 应至少有 1 个 drill down（province → city 或 category → product）
    assert len(drill_downs) >= 1, f"Expected >= 1 drill downs, got {len(drill_downs)}"

    # 检查 drill down 结构
    for dd in drill_downs:
        assert dd["widget_id"], "DrillDown widget_id should not be empty"
        assert dd["current_level"], "DrillDown current_level should not be empty"
        assert dd["next_level"], "DrillDown next_level should not be empty"
        print(f"  [OK] Drill: {dd['label']} ({dd['current_level']} → {dd['next_level']})")

    print(f"  - Total drill downs: {len(drill_downs)}")
    print("[OK] Drill Down Generation Test PASSED")


# ============================================================
# Test Case 4: Highlight Generation
# ============================================================

def test_highlights():
    """Test 4: Highlight 是否正确生成"""
    print("\n" + "=" * 60)
    print("Test 4: Highlight Generation")
    print("=" * 60)

    widgets = [
        make_widget("rank_bar", "Ranking Bar", BusinessTopic.SALES, VisualRole.RANKING,
                    AnalyticalRole.COMPARE, 0.80, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
        make_widget("trend_line", "Trend Line", BusinessTopic.SALES, VisualRole.PRIMARY_TREND,
                    AnalyticalRole.MONITOR, 0.85, PriorityLevel.HERO, RecommendedSection.MAIN_ANALYSIS),
        make_widget("kpi1", "KPI 1", BusinessTopic.SALES, VisualRole.OVERVIEW_METRIC,
                    AnalyticalRole.MONITOR, 0.95, PriorityLevel.HERO, RecommendedSection.OVERVIEW),
    ]

    schema = build_test_schema(widgets)

    engine = DashboardInteractionEngine()
    complete_schema = engine.enrich(schema)

    interactions = complete_schema.interactions
    highlights = interactions.get("highlights", [])

    # 应有 TOP 3 高亮（ranking/bar）
    top3_hl = [h for h in highlights if h["rule_type"] == "top_n"]
    assert len(top3_hl) >= 1, f"Expected >= 1 TOP 3 highlights, got {len(top3_hl)}"
    print(f"  [OK] TOP 3 highlight found for ranking widget")

    # 应有 growth highlight（trend/line）
    growth_hl = [h for h in highlights if h["rule_type"] == "high_growth"]
    assert len(growth_hl) >= 1, f"Expected >= 1 growth highlights, got {len(growth_hl)}"
    print(f"  [OK] Growth highlight found for trend widget")

    # 应有 threshold highlight（KPI）
    threshold_hl = [h for h in highlights if h["rule_type"] == "threshold"]
    assert len(threshold_hl) >= 1, f"Expected >= 1 threshold highlights, got {len(threshold_hl)}"
    print(f"  [OK] Threshold highlight found for KPI widget")

    # Hover highlight
    hover_hl = [h for h in highlights if "hover" in h.get("params", {}).get("interaction", "")]
    print(f"  - Hover highlights: {len(hover_hl)}")

    print(f"  - Total highlights: {len(highlights)}")
    print("[OK] Highlight Generation Test PASSED")


# ============================================================
# Test Case 5: Widget Linkage (Interaction Graph)
# ============================================================

def test_linkages():
    """Test 5: Interaction Graph (Linkage) 是否正确建立"""
    print("\n" + "=" * 60)
    print("Test 5: Widget Linkage (Interaction Graph)")
    print("=" * 60)

    widgets = [
        make_widget("sales_kpi", "Sales KPI", BusinessTopic.SALES, VisualRole.OVERVIEW_METRIC,
                    AnalyticalRole.MONITOR, 0.95, PriorityLevel.HERO, RecommendedSection.OVERVIEW),
        make_widget("sales_trend", "Sales Trend", BusinessTopic.SALES, VisualRole.PRIMARY_TREND,
                    AnalyticalRole.MONITOR, 0.88, PriorityLevel.HERO, RecommendedSection.MAIN_ANALYSIS),
        make_widget("region_rank", "Region Ranking", BusinessTopic.SALES, VisualRole.RANKING,
                    AnalyticalRole.COMPARE, 0.72, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
        make_widget("product_struct", "Product Structure", BusinessTopic.PRODUCT, VisualRole.COMPOSITION,
                    AnalyticalRole.EXPLAIN, 0.65, PriorityLevel.MAJOR, RecommendedSection.COMPARISON),
    ]

    schema = build_test_schema(widgets)

    engine = DashboardInteractionEngine()
    complete_schema = engine.enrich(schema)

    interactions = complete_schema.interactions
    linkages = interactions.get("linkages", [])

    # 应有 sales topic 联动
    assert len(linkages) >= 1, f"Expected >= 1 linkages, got {len(linkages)}"

    sales_link = next((l for l in linkages if l["business_topic"] == "sales"), None)
    if sales_link:
        assert len(sales_link["source_widgets"]) >= 1, "Linkage should have source widgets"
        assert len(sales_link["target_widgets"]) >= 1, "Linkage should have target widgets"
        assert sales_link["linkage_type"] in ("one_to_one", "one_to_many", "many_to_many"), \
            f"Linkage type should be valid, got {sales_link['linkage_type']}"
        print(f"  [OK] Sales linkage: {sales_link['linkage_type']}, sources={sales_link['source_widgets']}, targets={sales_link['target_widgets']}")

    # 跨 topic 联动
    cross_topic = [l for l in linkages if not l.get("business_topic")]
    if cross_topic:
        print(f"  [OK] Cross-topic linkages: {len(cross_topic)}")

    print(f"  - Total linkages: {len(linkages)}")
    print("[OK] Widget Linkage Test PASSED")


# ============================================================
# Test Case 6: Complete Dashboard Schema Output
# ============================================================

def test_complete_schema():
    """Test 6: Complete Dashboard Schema 是否正确输出"""
    print("\n" + "=" * 60)
    print("Test 6: Complete Dashboard Schema Output")
    print("=" * 60)

    widgets = [
        make_widget("sales_kpi", "Sales KPI", BusinessTopic.SALES, VisualRole.OVERVIEW_METRIC,
                    AnalyticalRole.MONITOR, 0.95, PriorityLevel.HERO, RecommendedSection.OVERVIEW,
                    preferred_size=PreferredSize.EXTRA_LARGE),
        make_widget("sales_trend", "Sales Trend", BusinessTopic.SALES, VisualRole.PRIMARY_TREND,
                    AnalyticalRole.MONITOR, 0.88, PriorityLevel.HERO, RecommendedSection.MAIN_ANALYSIS,
                    preferred_size=PreferredSize.EXTRA_LARGE),
        make_widget("region_rank", "Region Ranking", BusinessTopic.SALES, VisualRole.RANKING,
                    AnalyticalRole.COMPARE, 0.72, PriorityLevel.MAJOR, RecommendedSection.COMPARISON,
                    preferred_size=PreferredSize.LARGE),
        make_widget("product_struct", "Product Structure", BusinessTopic.PRODUCT, VisualRole.COMPOSITION,
                    AnalyticalRole.EXPLAIN, 0.65, PriorityLevel.MAJOR, RecommendedSection.COMPARISON,
                    preferred_size=PreferredSize.MEDIUM),
        make_widget("anomaly_warn", "Anomaly Warning", BusinessTopic.RISK, VisualRole.WARNING,
                    AnalyticalRole.DISCOVER, 0.60, PriorityLevel.MAJOR, RecommendedSection.MONITORING),
        make_widget("corr_detail", "Correlation", BusinessTopic.GENERAL, VisualRole.CORRELATION,
                    AnalyticalRole.DISCOVER, 0.35, PriorityLevel.MINOR, RecommendedSection.DETAIL,
                    preferred_size=PreferredSize.SMALL),
    ]

    # Full pipeline: Composition Planner → Layout Engine → Interaction Engine
    schema = build_test_schema(widgets, title="Complete Pipeline Dashboard")

    engine = DashboardInteractionEngine()
    complete_schema = engine.enrich(schema)

    # Validate interactions is not empty
    interactions = complete_schema.interactions
    assert interactions, "interactions field should not be empty"
    assert isinstance(interactions, dict), "interactions should be a dict"

    # Validate interaction fields
    assert "global_filters" in interactions, "interactions should have global_filters"
    assert "cross_filters" in interactions, "interactions should have cross_filters"
    assert "drill_downs" in interactions, "interactions should have drill_downs"
    assert "highlights" in interactions, "interactions should have highlights"
    assert "linkages" in interactions, "interactions should have linkages"
    assert "id" in interactions, "interactions should have id"
    assert "dashboard_id" in interactions, "interactions should have dashboard_id"
    assert "version" in interactions, "interactions should have version"
    assert interactions["version"] == "2.0", f"Expected version 2.0, got {interactions['version']}"

    # Validate metadata
    metadata = interactions.get("metadata", {})
    assert metadata.get("total_widgets") == 6, f"Expected 6 widgets in metadata, got {metadata.get('total_widgets')}"
    assert metadata.get("generator"), "metadata should have generator"
    print(f"  - Generator: {metadata.get('generator')}")
    print(f"  - Generated at: {metadata.get('generated_at')}")

    # Count all interactions
    gf_count = len(interactions.get("global_filters", []))
    cf_count = len(interactions.get("cross_filters", []))
    dd_count = len(interactions.get("drill_downs", []))
    hl_count = len(interactions.get("highlights", []))
    lg_count = len(interactions.get("linkages", []))

    print(f"  - Global Filters: {gf_count}")
    print(f"  - Cross Filters: {cf_count}")
    print(f"  - Drill Downs: {dd_count}")
    print(f"  - Highlights: {hl_count}")
    print(f"  - Linkages: {lg_count}")
    print(f"  - Total interactions: {gf_count + cf_count + dd_count + hl_count + lg_count}")

    # Validate each global filter has scope
    for f in interactions.get("global_filters", []):
        assert "scope" in f, f"Global filter {f['id']} should have scope"
        print(f"    Global Filter: {f['field']}, scope={f['scope']}, targets={len(f['target_widgets'])}")

    # Validate each highlight has rule_type
    for h in interactions.get("highlights", []):
        assert "rule_type" in h, f"Highlight {h['id']} should have rule_type"
        print(f"    Highlight: {h['widget_id']}, type={h['rule_type']}, label={h['label']}")

    # Validate schema structure is preserved (interactions added, not broken)
    assert complete_schema.id, "Schema ID should not be empty"
    assert len(complete_schema.widgets) == 6, f"Schema should still have 6 widgets, got {len(complete_schema.widgets)}"
    assert complete_schema.layout_strategy, "Layout strategy should be preserved"
    assert complete_schema.layout.columns == 24, "Grid columns should be preserved"

    # Validate the full to_dict output
    schema_dict = complete_schema.to_dict()
    assert "interactions" in schema_dict, "to_dict should include interactions"
    assert "global_filters" in schema_dict["interactions"], "interactions in to_dict should have global_filters"

    print(f"  - Schema ID: {complete_schema.id}")
    print(f"  - Layout Strategy: {complete_schema.layout_strategy}")
    print(f"  - Widget Count: {len(complete_schema.widgets)}")

    print("[OK] Complete Dashboard Schema Test PASSED")
    return complete_schema


# ============================================================
# Run All Tests
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Dashboard Interaction Engine - Test Suite")
    print("=" * 60)

    schema = None
    try:
        test_global_filters()
        test_cross_filters()
        test_drill_downs()
        test_highlights()
        test_linkages()
        schema = test_complete_schema()
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Save Schema JSON
    if schema:
        output_path = os.path.join(os.path.dirname(__file__), "interaction_engine_test_output.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(schema.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"\nComplete Dashboard Schema JSON saved to: {output_path}")

    print("\n" + "=" * 60)
    print("All 6 tests PASSED")
    print("=" * 60)
