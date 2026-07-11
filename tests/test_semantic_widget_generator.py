"""
Semantic Widget Generator 测试

验证：
1. 输入已有 AnalysisPackage
2. 生成 SemanticWidget[]
3. 检查 business_topic / visual_role / importance_score / preferred_size / related_widgets
4. 输出测试 JSON

测试策略：
- 构造模拟 AnalysisPackage（包含各种 analysis_type）
- 验证各维度分类是否正确
- 验证 importance_score 计算是否合理
- 链路测试：AnalysisPackage → SemanticWidget[] → JSON
"""

import json
import sys
import os

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.dashboard.semantic_models import (
    SemanticWidget, BusinessTopic, VisualRole, AnalyticalRole,
    PriorityLevel, PreferredSize, RecommendedSection,
    ImportanceDetail, DependencyGraph,
)
from src.dashboard.semantic_widget_generator import SemanticWidgetGenerator
from src.dashboard.importance_engine import ImportanceScoreEngine
from src.dashboard.semantic_rules import SemanticClassifier, ClassificationRule, CLASSIFICATION_RULES
from src.dashboard.relationship_engine import RelationshipEngine, build_dependency_graph
from src.dashboard.widget_converter import WidgetConverter
from src.dashboard.models import Widget, WidgetType, WidgetSize, DisplayRole, WidgetFilter, WidgetDataSource
from src.domain.business_finding import BusinessFinding, Severity, Direction, FindingCategory, EvidenceRef
from src.analysis_templates.base import AnalysisPackage, KPIItem, ChartData


# ============================================================
# 测试辅助：构造模拟 AnalysisPackage
# ============================================================

def _make_finding(
    analysis_type: str = "growth_analysis",
    category: FindingCategory = FindingCategory.GROWTH,
    severity: Severity = Severity.HIGH,
    title: str = "华东同比增长12%",
    metric: str = "销售额",
    dimension: str = "地区",
    entity: str = "华东",
    value: float = 12.5,
    direction: Direction = Direction.UP,
    confidence: float = 0.9,
    business_meaning: str = "华东市场增长强劲，可能受政策利好驱动",
    business_impact: str = "若保持增长态势，全年营收可超预期5-8%",
    recommendation: str = "建议加大华东市场投入，同时关注竞品动态",
) -> BusinessFinding:
    """构造模拟 BusinessFinding"""
    return BusinessFinding(
        id=f"finding_{analysis_type}_{entity}",
        analysis_type=analysis_type,
        category=category,
        title=title,
        description=f"{entity}{metric}变化分析",
        metric=metric,
        dimension=dimension,
        entity=entity,
        value=value,
        unit="%",
        direction=direction,
        severity=severity,
        confidence=confidence,
        business_meaning=business_meaning,
        business_impact=business_impact,
        recommendation=recommendation,
    )


def _make_package(
    analysis_type: str = "growth_analysis",
    metric: str = "销售额",
    dimension: str = "时间",
    findings: list = None,
    kpis: list = None,
    chart_data: list = None,
    confidence: float = 0.85,
) -> dict:
    """构造模拟 AnalysisPackage dict"""
    if findings is None:
        cat_map = {
            "growth_analysis": FindingCategory.GROWTH,
            "ranking_analysis": FindingCategory.RANKING,
            "structure_analysis": FindingCategory.STRUCTURE,
            "concentration_analysis": FindingCategory.CONCENTRATION,
            "distribution_analysis": FindingCategory.DISTRIBUTION,
            "comparison_analysis": FindingCategory.COMPARISON,
            "geo_analysis": FindingCategory.GEO,
            "anomaly_analysis": FindingCategory.ANOMALY,
            "retention_analysis": FindingCategory.RETENTION,
            "proportion_analysis": FindingCategory.PROPORTION,
        }
        category = cat_map.get(analysis_type, FindingCategory.UNKNOWN)

        dir_map = {
            "growth_analysis": Direction.UP,
            "anomaly_analysis": Direction.UNKNOWN,
        }
        direction = dir_map.get(analysis_type, Direction.UP)

        sev_map = {
            "growth_analysis": Severity.HIGH,
            "ranking_analysis": Severity.MEDIUM,
            "anomaly_analysis": Severity.CRITICAL,
            "geo_analysis": Severity.MEDIUM,
        }
        severity = sev_map.get(analysis_type, Severity.INFO)

        findings = [
            _make_finding(
                analysis_type=analysis_type,
                category=category,
                severity=severity,
                direction=direction,
            )
        ]

    if kpis is None:
        kpis = [
            {"label": f"{metric}增长率", "value": "12.5%", "change": "+12.5%"},
            {"label": f"{metric}总量", "value": "1,250万", "change": "+8.3%"},
        ]

    if chart_data is None:
        chart_type_map = {
            "growth_analysis": "line",
            "ranking_analysis": "bar",
            "structure_analysis": "pie",
            "comparison_analysis": "bar",
            "geo_analysis": "map",
            "anomaly_analysis": "scatter",
        }
        ct = chart_type_map.get(analysis_type, "bar")
        chart_data = [
            {"slot": "main", "chart_type": ct, "title": f"{metric}分析",
             "x": dimension, "y": metric,
             "data": [{"x": f"维度{i}", "y": 100 + i * 50} for i in range(10)]}
        ]

    return {
        "id": f"pkg_{analysis_type}_001",
        "analysis_type": analysis_type,
        "business_question": f"{metric}变化趋势如何？",
        "algorithm": None,
        "dimension": dimension,
        "metric": metric,
        "findings": [f.to_dict() for f in findings] if all(hasattr(f, 'to_dict') for f in findings) else findings,
        "kpis": kpis,
        "chart_data": chart_data,
        "charts": [],
        "tables": [],
        "insights": [f.title for f in findings] if all(hasattr(f, 'title') for f in findings) else ["洞察1"],
        "conclusions": ["分析结论1"],
        "recommendations": ["建议1"],
        "confidence": confidence,
        "business_metrics": {},
        "derived_metrics": {},
        "data_profile": {
            "time_cols": ["月份"],
            "category_cols": ["地区", "产品"],
            "numeric_cols": [metric],
        },
        "metadata": {"version": "1.0"},
    }


# ============================================================
# Test 1: SemanticWidgetGenerator 全链路测试
# ============================================================

def test_semantic_widget_generator_full_pipeline():
    """全链路测试：AnalysisPackage → SemanticWidget[] → JSON"""
    print("\n" + "=" * 60)
    print("Test 1: SemanticWidgetGenerator 全链路测试")
    print("=" * 60)

    # 构造多个 AnalysisPackage
    packages = [
        _make_package(analysis_type="growth_analysis", metric="销售额", dimension="时间"),
        _make_package(analysis_type="ranking_analysis", metric="销售额", dimension="地区"),
        _make_package(analysis_type="structure_analysis", metric="销售额", dimension="产品"),
        _make_package(analysis_type="anomaly_analysis", metric="销售额", dimension="时间"),
    ]

    # 生成 SemanticWidget[]
    gen = SemanticWidgetGenerator()
    widgets = gen.generate_from_dicts(packages)

    # 验证
    print(f"\n[OK] 生成了 {len(widgets)} 个 SemanticWidget")

    for w in widgets:
        print(f"\n--- Widget: {w.title} ---")
        print(f"  id: {w.id}")
        print(f"  business_topic: {w.business_topic.value}")
        print(f"  business_purpose: {w.business_purpose}")
        print(f"  visual_role: {w.visual_role.value}")
        print(f"  analytical_role: {w.analytical_role.value}")
        print(f"  importance_score: {w.importance_score:.4f}")
        print(f"  importance_detail: {w.importance_detail.to_dict()}")
        print(f"  priority_level: {w.priority_level.value}")
        print(f"  preferred_size: {w.preferred_size.value}")
        print(f"  recommended_section: {w.recommended_section.value}")
        print(f"  chart_type: {w.chart_type}")
        print(f"  related_widgets: {len(w.related_widgets)} 个关系")

        # 检查关键字段不为空
        assert w.id, f"id 为空"
        assert w.title, f"title 为空"
        assert w.business_purpose, f"business_purpose 为空"
        assert 0 <= w.importance_score <= 1, f"importance_score 超出范围: {w.importance_score}"
        assert w.business_topic != BusinessTopic.GENERAL or w.analysis_type in ["distribution", "correlation"], \
            f"business_topic 为 GENERAL（预期更精确）"

    # 验证 Widget 间关系
    total_relations = sum(len(w.related_widgets) for w in widgets)
    print(f"\n[OK] Widget 间关系总计: {total_relations}")
    for w in widgets:
        for r in w.related_widgets:
            print(f"  {w.id} → {r.target_widget_id} ({r.relation_type.value}): {r.description}")

    assert total_relations > 0, f"应至少有 1 个 Widget 关系"

    # 输出 JSON
    json_output = [w.to_dict() for w in widgets]
    print(f"\n[OK] JSON 输出成功，包含 {len(json_output)} 个 SemanticWidget")

    # 保存测试 JSON
    output_path = os.path.join(os.path.dirname(__file__), "semantic_widget_test_output.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(json_output, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] 测试 JSON 已保存到: {output_path}")

    return widgets


# ============================================================
# Test 2: 语义分类验证
# ============================================================

def test_semantic_classification():
    """验证语义分类引擎对各 analysis_type 的分类是否正确"""
    print("\n" + "=" * 60)
    print("Test 2: 语义分类引擎验证")
    print("=" * 60)

    classifier = SemanticClassifier()

    test_cases = [
        # (analysis_type, expected_visual_role, expected_analytical_role, expected_business_topic)
        ("growth_analysis", VisualRole.PRIMARY_TREND, AnalyticalRole.MONITOR, BusinessTopic.GROWTH),
        ("ranking_analysis", VisualRole.RANKING, AnalyticalRole.COMPARE, BusinessTopic.SALES),
        ("structure_analysis", VisualRole.COMPOSITION, AnalyticalRole.EXPLAIN, BusinessTopic.GENERAL),
        ("geo_analysis", VisualRole.GEOGRAPHIC, AnalyticalRole.DISCOVER, BusinessTopic.OPERATION),
        ("anomaly_analysis", VisualRole.WARNING, AnalyticalRole.DISCOVER, BusinessTopic.RISK),
        ("comparison_analysis", VisualRole.COMPARISON, AnalyticalRole.COMPARE, BusinessTopic.GENERAL),
        ("distribution_analysis", VisualRole.DISTRIBUTION, AnalyticalRole.EXPLAIN, BusinessTopic.GENERAL),
        ("correlation_analysis", VisualRole.CORRELATION, AnalyticalRole.DISCOVER, BusinessTopic.GENERAL),
        ("concentration_analysis", VisualRole.CONCENTRATION, AnalyticalRole.EVALUATE, BusinessTopic.RISK),
        ("retention_analysis", VisualRole.OVERVIEW_METRIC, AnalyticalRole.MONITOR, BusinessTopic.CUSTOMER),
    ]

    for analysis_type, expected_role, expected_analytical, expected_topic in test_cases:
        result = classifier.classify(
            analysis_type=analysis_type,
            finding_category="",
            chart_type="",
            importance_score=0.7,
            metric="销售额",
            dimension="时间",
        )

        actual_role = result["visual_role"]
        actual_analytical = result["analytical_role"]
        actual_topic = result["business_topic"]

        print(f"\n  {analysis_type}:")
        print(f"    visual_role: {actual_role.value} (期望: {expected_role.value})")
        print(f"    analytical_role: {actual_analytical.value} (期望: {expected_analytical.value})")
        print(f"    business_topic: {actual_topic.value} (期望: {expected_topic.value})")

        assert actual_role == expected_role, \
            f"{analysis_type}: visual_role 错误，期望 {expected_role.value}, 实际 {actual_role.value}"
        assert actual_analytical == expected_analytical, \
            f"{analysis_type}: analytical_role 错误，期望 {expected_analytical.value}, 实际 {actual_analytical.value}"

    print("\n[OK] 所有 analysis_type 的语义分类正确")


# ============================================================
# Test 3: Importance Score 计算验证
# ============================================================

def test_importance_score():
    """验证 importance_score 5维度加权计算"""
    print("\n" + "=" * 60)
    print("Test 3: Importance Score 计算验证")
    print("=" * 60)

    engine = ImportanceScoreEngine()

    # 高重要性 Package（critical severity + 大 impact + 高 confidence）
    high_pkg = _make_package(
        analysis_type="growth_analysis",
        metric="销售额",
        dimension="时间",
        findings=[_make_finding(
            severity=Severity.CRITICAL,
            confidence=0.95,
            business_impact="若不干预，全年营收可能下降15-20%，影响公司整体战略目标",
            recommendation="建议立即成立专项小组，制定针对性干预方案",
        )],
        confidence=0.95,
    )

    score_high, detail_high = engine.calculate(high_pkg)
    print(f"\n高重要性 Package:")
    print(f"  importance_score: {score_high:.4f}")
    print(f"  detail: {detail_high.to_dict()}")
    print(f"  priority_level: {engine.score_to_priority_level(score_high).value}")
    assert score_high >= 0.6, f"高重要性 Package 的 score 应 >= 0.6, 实际 {score_high}"
    assert engine.score_to_priority_level(score_high) in (PriorityLevel.HERO, PriorityLevel.MAJOR), \
        f"高重要性 Package 应为 Hero/Major"

    # 低重要性 Package（low severity + 无 impact + 低 confidence）
    low_pkg = _make_package(
        analysis_type="distribution_analysis",
        metric="标准差",
        dimension="时间",
        findings=[_make_finding(
            severity=Severity.INFO,
            confidence=0.3,
            business_impact="",
            recommendation="",
            metric="偏度",
            value=0.5,
        )],
        confidence=0.3,
    )

    score_low, detail_low = engine.calculate(low_pkg)
    print(f"\n低重要性 Package:")
    print(f"  importance_score: {score_low:.4f}")
    print(f"  detail: {detail_low.to_dict()}")
    print(f"  priority_level: {engine.score_to_priority_level(score_low).value}")
    assert score_low < 0.7, f"低重要性 Package 的 score 应 < 0.7, 实际 {score_low}"
    assert score_low >= 0.0, f"score 不能为负"

    # 验证 score 在 0-1 范围内
    assert 0 <= score_high <= 1, f"importance_score 超出范围: {score_high}"
    assert 0 <= score_low <= 1, f"importance_score 超出范围: {score_low}"

    print("\n[OK] Importance Score 计算验证通过")


# ============================================================
# Test 4: Widget Relationship 验证
# ============================================================

def test_widget_relationships():
    """验证 Widget 间关系识别"""
    print("\n" + "=" * 60)
    print("Test 4: Widget Relationship 验证")
    print("=" * 60)

    # 构造多个 SemanticWidget
    widgets = [
        SemanticWidget(
            id="sales_trend_001",
            title="销售趋势",
            business_topic=BusinessTopic.GROWTH,
            visual_role=VisualRole.PRIMARY_TREND,
            analytical_role=AnalyticalRole.MONITOR,
            importance_score=0.92,
            analysis_type="growth",
            chart_type="line",
        ),
        SemanticWidget(
            id="region_sales_002",
            title="区域销售排名",
            business_topic=BusinessTopic.SALES,
            visual_role=VisualRole.RANKING,
            analytical_role=AnalyticalRole.COMPARE,
            importance_score=0.78,
            analysis_type="ranking",
            chart_type="bar",
        ),
        SemanticWidget(
            id="product_sales_003",
            title="产品销售结构",
            business_topic=BusinessTopic.GENERAL,
            visual_role=VisualRole.COMPOSITION,
            analytical_role=AnalyticalRole.EXPLAIN,
            importance_score=0.65,
            analysis_type="structure",
            chart_type="pie",
        ),
    ]

    # 构建关系
    engine = RelationshipEngine()
    graph = engine.build_relationships(widgets)

    print(f"\nDependencyGraph:")
    print(f"  nodes: {len(graph.nodes)}")
    print(f"  edges: {len(graph.edges)}")

    for edge in graph.edges:
        print(f"  {edge['source']} → {edge['target']} ({edge['type']}): {edge['description']}")

    # 验证：sales_trend 应与 ranking/structure 有关系
    trend_edges = [e for e in graph.edges if e["source"] == "sales_trend_001"]
    print(f"\n[OK] sales_trend_001 有 {len(trend_edges)} 个关系边")

    assert len(trend_edges) >= 1, f"sales_trend_001 应至少有 1 个关系"

    # 验证简化依赖图
    dep_graph = build_dependency_graph(widgets)
    print(f"\nSimplified Dependency Graph:")
    for wid, related in dep_graph.items():
        print(f"  {wid} → {related}")

    assert "sales_trend_001" in dep_graph, f"sales_trend_001 应在依赖图中"
    assert len(dep_graph["sales_trend_001"]) >= 1, f"sales_trend_001 应有至少 1 个关联 Widget"

    print("\n[OK] Widget Relationship 验证通过")


# ============================================================
# Test 5: Widget → SemanticWidget 转换验证
# ============================================================

def test_widget_converter():
    """验证旧 Widget → SemanticWidget 转换"""
    print("\n" + "=" * 60)
    print("Test 5: Widget → SemanticWidget 转换验证")
    print("=" * 60)

    # 构造旧 Widget
    old_widget = Widget(
        id="old_widget_001",
        title="销售增长趋势",
        description="展示销售额随时间的变化",
        widget_type=WidgetType.CHART,
        analysis_type="growth",
        business_topic="增长趋势",
        finding_summary="华东同比增长12%",
        importance_score=80,  # 旧版 0-100
        chart_type="line",
        chart_config={"chart_type": "line", "data_available": True},
        preferred_size=WidgetSize.LARGE,
        priority=8,
        display_role=DisplayRole.MAIN,
        supported_filters=[WidgetFilter(field="time", label="时间范围", filter_type="date_range")],
        drill_down=True,
        cross_filter=False,
    )

    # 转换为 SemanticWidget
    converter = WidgetConverter()
    semantic_widget = converter.upgrade(old_widget)

    print(f"\n旧 Widget:")
    print(f"  id: {old_widget.id}")
    print(f"  importance_score: {old_widget.importance_score} (0-100)")
    print(f"  widget_type: {old_widget.widget_type.value}")
    print(f"  preferred_size: {old_widget.preferred_size.value}")

    print(f"\n新 SemanticWidget:")
    print(f"  id: {semantic_widget.id}")
    print(f"  importance_score: {semantic_widget.importance_score:.4f} (0-1)")
    print(f"  visual_role: {semantic_widget.visual_role.value}")
    print(f"  business_topic: {semantic_widget.business_topic.value}")
    print(f"  priority_level: {semantic_widget.priority_level.value}")
    print(f"  preferred_size: {semantic_widget.preferred_size.value}")
    print(f"  business_purpose: {semantic_widget.business_purpose}")

    # 验证转换正确性
    assert semantic_widget.importance_score == 0.8, \
        f"importance_score 应为 0.8, 实际 {semantic_widget.importance_score}"
    assert semantic_widget.visual_role == VisualRole.PRIMARY_TREND, \
        f"chart_type=line 应映射为 PRIMARY_TREND"
    assert semantic_widget.priority_level == PriorityLevel.MAJOR, \
        f"score=0.8 应为 MAJOR"
    assert semantic_widget.preferred_size == PreferredSize.LARGE, \
        f"LARGE → LARGE 映射"

    # 验证降级转换
    legacy_dict = converter.downgrade(semantic_widget)
    print(f"\n降级 Widget dict:")
    print(f"  importance_score: {legacy_dict['importance_score']} (0-100)")
    print(f"  preferred_size: {legacy_dict['preferred_size']}")
    print(f"  display_role: {legacy_dict['display_role']}")

    assert legacy_dict["importance_score"] == 80, \
        f"降级 importance_score 应为 80, 实际 {legacy_dict['importance_score']}"

    print("\n[OK] Widget → SemanticWidget 转换验证通过")


# ============================================================
# Main：运行所有测试
# ============================================================

def main():
    print("\n" + "=" * 70)
    print("Semantic Widget Generator 测试套件")
    print("=" * 70)

    results = {}

    # Test 1: 全链路测试
    try:
        widgets = test_semantic_widget_generator_full_pipeline()
        results["全链路测试"] = "PASS"
    except Exception as e:
        results["全链路测试"] = f"FAIL: {e}"
        print(f"  [FAIL] 全链路测试失败: {e}")

    # Test 2: 语义分类验证
    try:
        test_semantic_classification()
        results["语义分类"] = "PASS"
    except Exception as e:
        results["语义分类"] = f"FAIL: {e}"
        print(f"  [FAIL] 语义分类失败: {e}")

    # Test 3: Importance Score 验证
    try:
        test_importance_score()
        results["Importance Score"] = "PASS"
    except Exception as e:
        results["Importance Score"] = f"FAIL: {e}"
        print(f"  [FAIL] Importance Score 失败: {e}")

    # Test 4: Widget Relationship 验证
    try:
        test_widget_relationships()
        results["Widget Relationship"] = "PASS"
    except Exception as e:
        results["Widget Relationship"] = f"FAIL: {e}"
        print(f"  [FAIL] Widget Relationship 失败: {e}")

    # Test 5: Widget 转换验证
    try:
        test_widget_converter()
        results["Widget 转换"] = "PASS"
    except Exception as e:
        results["Widget 转换"] = f"FAIL: {e}"
        print(f"  [FAIL] Widget 转换失败: {e}")

    # 汇总
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    for name, result in results.items():
        status = "[PASS]" if result == "PASS" else "[FAIL]"
        print(f"  {status} {name}: {result}")

    pass_count = sum(1 for r in results.values() if r == "PASS")
    total_count = len(results)
    print(f"\n通过率: {pass_count}/{total_count}")

    return pass_count == total_count


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
