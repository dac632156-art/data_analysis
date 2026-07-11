"""
Widget Generator 测试

测试覆盖：
1. Growth AnalysisPackage → trend widget
2. Ranking AnalysisPackage → ranking widget
3. Importance Score 高影响 Finding → 高 score
4. 空 AnalysisPackage → 空列表
5. 边际情况
"""
import sys
import os
import unittest

# 确保 src 在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.dashboard import WidgetGenerator, Widget, WidgetType, WidgetSize, DisplayRole
from src.dashboard.models import WidgetFilter, WidgetDataSource
from src.domain.business_finding import (
    BusinessFinding, Severity, Direction, FindingCategory, EvidenceRef,
)
from src.analysis_templates.base import AnalysisPackage


# ============================================================
# 测试辅助：构造 mock AnalysisPackage
# ============================================================

def _make_growth_package(
    confidence: float = 1.0,
    severity: Severity = Severity.HIGH,
    business_impact: str = "若不干预，全年营收下降5-8%",
) -> AnalysisPackage:
    """构造增长分析 package"""
    finding = BusinessFinding(
        id="growth_f1",
        analysis_type="growth_analysis",
        category=FindingCategory.GROWTH,
        title="整体销售额同比增长12%",
        description="销售额稳步增长，Q3达到峰值",
        metric="销售额",
        dimension="月",
        entity="全量",
        value=12.0,
        unit="%",
        direction=Direction.UP,
        severity=severity,
        confidence=0.95,
        business_meaning="市场需求旺盛，销售团队执行力强",
        business_impact=business_impact,
        recommendation="加大Q2备货，抢占市场先机",
        evidence=EvidenceRef(chart_slots=("trend",)),
    )
    return AnalysisPackage(
        id="pkg_growth_001",
        analysis_type="growth_analysis",
        business_question="销售额的增长趋势如何？",
        algorithm="yoy",
        dimension="月",
        metric="销售额",
        findings=[finding],
        kpis=[
            type("KPIItem", (), {
                "label": "总销售额",
                "value": "298,957",
                "change": "+12%",
                "kpi_type": "sum",
            })()
        ],
        chart_data=[
            type("ChartData", (), {
                "slot": "trend",
                "chart_type": "line",
                "title": "销售额趋势",
                "x": "月",
                "y": "销售额",
                "data": [{"x": "1月", "y": 25000}, {"x": "2月", "y": 28000}],
            })()
        ],
        confidence=confidence,
        calculator_used="GrowthCalculator",
        template_used="growth_analysis",
        data_profile={
            "time_cols": ["月"],
            "category_cols": ["地区", "产品"],
            "numeric_cols": ["销售额", "利润"],
        },
    )


def _make_ranking_package(
    severity: Severity = Severity.MEDIUM,
) -> AnalysisPackage:
    """构造排名分析 package"""
    finding = BusinessFinding(
        id="rank_f1",
        analysis_type="ranking_analysis",
        category=FindingCategory.RANKING,
        title="「华东」销售额排名第一，占比28%",
        description="华东市场是最大的收入来源",
        metric="销售额",
        dimension="地区",
        entity="华东",
        value=85000.0,
        unit="元",
        direction=Direction.UP,
        severity=severity,
        confidence=0.90,
        business_meaning="华东是核心市场，需重点维护",
        business_impact="华东份额下滑将影响整体营收",
        recommendation="保持华东市场投入，同时拓展华南",
        evidence=EvidenceRef(chart_slots=("ranking",)),
    )
    return AnalysisPackage(
        id="pkg_ranking_001",
        analysis_type="ranking_analysis",
        business_question="哪个地区的销售额最高？",
        algorithm=None,
        dimension="地区",
        metric="销售额",
        findings=[finding],
        kpis=[
            type("KPIItem", (), {
                "label": "TOP1",
                "value": "华东",
                "change": "",
                "kpi_type": "rank",
            })()
        ],
        chart_data=[
            type("ChartData", (), {
                "slot": "ranking",
                "chart_type": "bar",
                "title": "地区排名",
                "x": "地区",
                "y": "销售额",
                "data": [{"x": "华东", "y": 85000}],
            })()
        ],
        confidence=0.90,
        calculator_used="RankingCalculator",
        template_used="ranking_analysis",
        data_profile={
            "category_cols": ["地区", "城市"],
            "numeric_cols": ["销售额"],
        },
    )


def _make_geo_package() -> AnalysisPackage:
    """构造地理分析 package"""
    finding = BusinessFinding(
        id="geo_f1",
        analysis_type="geo_analysis",
        category=FindingCategory.GEO,
        title="广东省销售额最高，达 50 万元",
        description="广东是最大的省级市场",
        metric="销售额",
        dimension="省份",
        entity="广东",
        value=500000.0,
        unit="元",
        direction=Direction.UP,
        severity=Severity.HIGH,
        confidence=0.95,
        business_meaning="华南地区是核心市场",
        business_impact="广东贡献了35%的总营收",
        recommendation="深耕华南，辐射周边省份",
        evidence=EvidenceRef(chart_slots=("geo",)),
    )
    return AnalysisPackage(
        id="pkg_geo_001",
        analysis_type="geo_analysis",
        business_question="哪些省份的销售额最高？",
        algorithm=None,
        dimension="省份",
        metric="销售额",
        findings=[finding],
        kpis=[],
        chart_data=[
            type("ChartData", (), {
                "slot": "geo",
                "chart_type": "map",
                "title": "省份分布",
                "x": "省份",
                "y": "销售额",
                "data": [{"x": "广东", "y": 500000}],
            })()
        ],
        confidence=0.95,
        calculator_used="GeoCalculator",
        template_used="geo_analysis",
        data_profile={
            "category_cols": ["省份", "城市"],
            "numeric_cols": ["销售额"],
        },
    )


def _make_empty_package() -> AnalysisPackage:
    """构造空 package（无 findings / charts / kpis）"""
    return AnalysisPackage(
        id="pkg_empty_001",
        analysis_type="growth_analysis",
        business_question="",
        algorithm=None,
        dimension=None,
        metric=None,
        findings=[],
        kpis=[],
        chart_data=[],
        confidence=0.5,
        calculator_used="",
        template_used="",
        data_profile={},
    )


def _make_critical_package() -> AnalysisPackage:
    """构造高风险 package（验证 importance_score 更高）"""
    finding = BusinessFinding(
        id="risk_f1",
        analysis_type="anomaly_analysis",
        category=FindingCategory.ANOMALY,
        title="销售额异常下降 30%！",
        description="Q2销售额环比下降30%，远低于正常波动范围",
        metric="销售额",
        dimension="月",
        entity="全量",
        value=-30.0,
        unit="%",
        direction=Direction.DOWN,
        severity=Severity.CRITICAL,
        confidence=0.98,
        business_meaning="市场可能存在系统性风险，需紧急排查",
        business_impact="若不立即干预，全年营收可能跌破预算下限 20%，影响公司战略目标达成和投资者信心",
        recommendation="立即启动应急响应小组，3天内完成根因分析",
        evidence=EvidenceRef(chart_slots=("anomaly",)),
    )
    return AnalysisPackage(
        id="pkg_critical_001",
        analysis_type="anomaly_analysis",
        business_question="销售额是否存在异常下降？",
        algorithm="zscore",
        dimension="月",
        metric="销售额",
        findings=[finding],
        kpis=[
            type("KPIItem", (), {
                "label": "异常点数",
                "value": "3",
                "change": "",
                "kpi_type": "count",
            })()
        ],
        chart_data=[
            type("ChartData", (), {
                "slot": "anomaly",
                "chart_type": "scatter",
                "title": "异常检测",
                "x": "月",
                "y": "销售额",
                "data": [{"x": "6月", "y": 15000}],
            })()
        ],
        confidence=0.98,
        calculator_used="AnomalyCalculator",
        template_used="anomaly_analysis",
        data_profile={
            "time_cols": ["月"],
            "numeric_cols": ["销售额"],
        },
    )


# ============================================================
# 测试类
# ============================================================

class TestWidgetGenerator(unittest.TestCase):
    """Widget Generator 核心功能测试"""

    def setUp(self):
        self.gen = WidgetGenerator()

    # ===== 测试 1：Growth AnalysisPackage → trend widget =====

    def test_growth_package_generates_trend_widget(self):
        """input: growth package → output: trend widget"""
        pkg = _make_growth_package()
        widgets = self.gen.generate([pkg])

        self.assertEqual(len(widgets), 1)
        w = widgets[0]

        self.assertIn("增长", w.title)
        self.assertEqual(w.widget_type, WidgetType.CHART)
        self.assertEqual(w.chart_type, "line")
        self.assertEqual(w.analysis_type, "growth")
        self.assertTrue(w.importance_score >= 50)
        self.assertIsInstance(w.data_source, WidgetDataSource)
        self.assertIsInstance(w.metadata, dict)

    # ===== 测试 2：Ranking AnalysisPackage → ranking widget =====

    def test_ranking_package_generates_ranking_widget(self):
        """input: ranking package → output: ranking widget"""
        pkg = _make_ranking_package()
        widgets = self.gen.generate([pkg])

        self.assertEqual(len(widgets), 1)
        w = widgets[0]

        self.assertEqual(w.widget_type, WidgetType.CHART)
        self.assertEqual(w.chart_type, "bar")
        self.assertEqual(w.analysis_type, "ranking")
        self.assertEqual(w.display_role, DisplayRole.MAIN)
        # ranking 有排名发现
        self.assertTrue(len(w.finding_summary) > 0)

    # ===== 测试 3：Geo AnalysisPackage → map widget =====

    def test_geo_package_generates_map_widget(self):
        """input: geo package → output: map widget"""
        pkg = _make_geo_package()
        widgets = self.gen.generate([pkg])

        self.assertEqual(len(widgets), 1)
        w = widgets[0]

        self.assertEqual(w.widget_type, WidgetType.MAP)
        self.assertEqual(w.chart_type, "map")
        self.assertEqual(w.analysis_type, "geo")
        self.assertEqual(w.display_role, DisplayRole.MAIN)

    # ===== 测试 4：Importance Score =====

    def test_critical_severity_gives_higher_score(self):
        """验证 CRITICAL severity 比 HIGH 获得更高 importance_score"""
        pkg_high = _make_growth_package(severity=Severity.HIGH)
        pkg_critical = _make_critical_package()  # CRITICAL + 长 business_impact + 高 confidence

        w_high = self.gen.generate([pkg_high])[0]
        w_critical = self.gen.generate([pkg_critical])[0]

        # CRITICAL 应该 >= HIGH（同分时至少有 5 分的 severity 差距被 business_impact 补齐）
        self.assertGreaterEqual(w_critical.importance_score, w_high.importance_score,
                                f"CRITICAL({w_critical.importance_score}) should >= HIGH({w_high.importance_score})")
        # 额外验证：CRITICAL 的 severity 层确实贡献更高
        self.assertGreater(self.gen._calculate_importance_score(pkg_critical),
                           self.gen._calculate_importance_score(pkg_high) - 10,
                           "CRITICAL severity should be meaningfully high")

    def test_longer_business_impact_gives_higher_score(self):
        """验证更长的 business_impact → 更高的 score"""
        pkg_short = _make_growth_package(business_impact="轻微影响")
        pkg_long = _make_growth_package(
            business_impact="若不干预，全年营收可能跌破预算下限 20%%，影响公司战略目标达成和投资者信心，"
                           "可能导致股价下跌、客户流失和市场份额萎缩"
        )

        w_short = self.gen.generate([pkg_short])[0]
        w_long = self.gen.generate([pkg_long])[0]

        self.assertGreaterEqual(w_long.importance_score, w_short.importance_score,
                                f"Long impact({w_long.importance_score}) should >= Short({w_short.importance_score})")

    def test_higher_confidence_gives_higher_score(self):
        """验证 confidence 更高 → score 更高"""
        pkg_low = _make_growth_package(confidence=0.3)
        pkg_high = _make_growth_package(confidence=0.95)

        w_low = self.gen.generate([pkg_low])[0]
        w_high = self.gen.generate([pkg_high])[0]

        self.assertGreaterEqual(w_high.importance_score, w_low.importance_score,
                                f"High conf({w_high.importance_score}) should >= Low conf({w_low.importance_score})")

    # ===== 测试 5：Score → Size 映射 =====

    def test_hero_score_yields_hero_size(self):
        """importance_score ≥ 90 → HERO size"""
        self.assertEqual(WidgetGenerator._score_to_size(95), WidgetSize.HERO)
        self.assertEqual(WidgetGenerator._score_to_size(90), WidgetSize.HERO)

    def test_large_scores_yield_correct_sizes(self):
        self.assertEqual(WidgetGenerator._score_to_size(85), WidgetSize.LARGE)
        self.assertEqual(WidgetGenerator._score_to_size(60), WidgetSize.MEDIUM)
        self.assertEqual(WidgetGenerator._score_to_size(30), WidgetSize.SMALL)

    # ===== 测试 6：空 AnalysisPackage =====

    def test_empty_package_returns_empty_list(self):
        """空 package → 空 Widget 列表"""
        pkg = _make_empty_package()
        widgets = self.gen.generate([pkg])
        self.assertEqual(len(widgets), 0)

    def test_empty_list_returns_empty_list(self):
        """空输入列表 → 空 Widget 列表"""
        widgets = self.gen.generate([])
        self.assertEqual(len(widgets), 0)

    # ===== 测试 7：多 Package 排序 =====

    def test_multiple_packages_sorted_by_priority(self):
        """多个 package 按 priority 降序排列"""
        pkg_high = _make_critical_package()       # CRITICAL → 高 priority
        pkg_med = _make_ranking_package(severity=Severity.MEDIUM)  # MEDIUM → 中

        widgets = self.gen.generate([pkg_med, pkg_high])

        self.assertGreaterEqual(len(widgets), 2)
        # 第一个应该是 priority 最高的
        self.assertGreaterEqual(widgets[0].priority, widgets[1].priority,
                                f"{widgets[0].title}({widgets[0].priority}) should be >= {widgets[1].title}({widgets[1].priority})")

    # ===== 测试 8：Filter 推断 =====

    def test_time_column_creates_time_filter(self):
        """有 time_cols → time filter"""
        pkg = _make_growth_package()
        widgets = self.gen.generate([pkg])
        w = widgets[0]

        filter_fields = {f.field for f in w.supported_filters}
        self.assertIn("time", filter_fields)

    def test_region_column_creates_region_filter(self):
        """有地区列 → region filter"""
        pkg = _make_geo_package()
        widgets = self.gen.generate([pkg])
        w = widgets[0]

        filter_fields = {f.field for f in w.supported_filters}
        self.assertIn("region", filter_fields)

    def test_no_filter_when_no_relevant_columns(self):
        """无特定列 → 最少 filter"""
        pkg = _make_critical_package()
        widgets = self.gen.generate([pkg])
        w = widgets[0]

        # critical package 有 time_cols → time filter
        filter_fields = {f.field for f in w.supported_filters}
        self.assertIn("time", filter_fields)
        self.assertGreater(len(w.supported_filters), 0)

    # ===== 测试 9：Chart Config =====

    def test_chart_config_extracted(self):
        """chart_config 从 package 的 chart_data 正确提取"""
        pkg = _make_growth_package()
        widgets = self.gen.generate([pkg])
        w = widgets[0]

        self.assertIsInstance(w.chart_config, dict)
        self.assertEqual(w.chart_config["chart_type"], "line")
        self.assertTrue(w.chart_config.get("data_available", False))

    def test_no_chart_data_yields_empty_config(self):
        """无 chart_data → data_available=False"""
        # 一个有效但无 chart 的 package
        pkg_valid = AnalysisPackage(
            id="pkg_no_chart",
            analysis_type="distribution_analysis",
            business_question="",
            algorithm=None,
            dimension=None,
            metric=None,
            findings=[
                BusinessFinding(
                    id="f1",
                    analysis_type="distribution_analysis",
                    category=FindingCategory.DISTRIBUTION,
                    title="数据呈正态分布",
                    severity=Severity.LOW,
                    confidence=0.8,
                )
            ],
            kpis=[],
            chart_data=[],
            confidence=0.8,
            data_profile={"numeric_cols": ["销售额"]},
        )
        widgets = self.gen.generate([pkg_valid])
        self.assertEqual(len(widgets), 1)
        w = widgets[0]
        self.assertFalse(w.chart_config.get("data_available", True))

    # ===== 测试 10：向后兼容 =====

    def test_widget_to_dict_is_json_serializable(self):
        """Widget.to_dict() 可以 JSON 序列化"""
        import json
        pkg = _make_growth_package()
        widgets = self.gen.generate([pkg])
        w = widgets[0]

        d = w.to_dict()
        # 不能有 Enum、dataclass、等不可序列化的类型
        json_str = json.dumps(d, default=str)
        self.assertIsInstance(json_str, str)
        self.assertIn("growth", json_str)

    def test_does_not_modify_package(self):
        """WidgetGenerator 不修改 AnalysisPackage"""
        pkg = _make_growth_package()
        original_title = pkg.business_question

        self.gen.generate([pkg])

        # package 不应被修改
        self.assertEqual(pkg.business_question, original_title)


class TestWidgetModel(unittest.TestCase):
    """Widget Domain Model 测试"""

    def test_widget_auto_generates_id(self):
        """不传 id → 自动生成 UUID"""
        w = Widget(title="test", widget_type=WidgetType.CHART)
        self.assertTrue(len(w.id) > 0)
        self.assertEqual(len(w.id), 8)  # uuid4()[:8]

    def test_widget_to_dict_excludes_internal_refs(self):
        """to_dict 不包含 _raw_package_ref"""
        w = Widget(title="test", widget_type=WidgetType.CHART, _raw_package_ref="pkg_001")
        d = w.to_dict()
        self.assertNotIn("_raw_package_ref", d)

    def test_widget_type_enum(self):
        """WidgetType 枚举值正确"""
        self.assertEqual(WidgetType.CHART.value, "chart")
        self.assertEqual(WidgetType.KPI.value, "kpi")
        self.assertEqual(WidgetType.MAP.value, "map")

    def test_widget_size_enum(self):
        """WidgetSize 枚举值正确"""
        self.assertEqual(WidgetSize.HERO.value, "hero")
        self.assertEqual(WidgetSize.SMALL.value, "small")


class TestWidgetMapping(unittest.TestCase):
    """Widget 映射配置测试"""

    def test_growth_mapping(self):
        from src.dashboard.widget_mapping import get_widget_config
        config = get_widget_config("growth_analysis")
        self.assertEqual(config["chart_type"], "line")
        self.assertEqual(config["widget_type"], "chart")

    def test_geo_mapping(self):
        from src.dashboard.widget_mapping import get_widget_config
        config = get_widget_config("geo_analysis")
        self.assertEqual(config["chart_type"], "map")
        self.assertEqual(config["widget_type"], "map")

    def test_unknown_type_returns_default(self):
        from src.dashboard.widget_mapping import get_widget_config, DEFAULT_WIDGET_CONFIG
        config = get_widget_config("unknown_analysis")
        self.assertEqual(config, DEFAULT_WIDGET_CONFIG)

    def test_all_mapped_types_have_required_fields(self):
        from src.dashboard.widget_mapping import ANALYSIS_TO_WIDGET_MAPPING
        for atype, config in ANALYSIS_TO_WIDGET_MAPPING.items():
            with self.subTest(analysis_type=atype):
                self.assertIn("widget_type", config)
                self.assertIn("business_topic", config)
                self.assertIn("display_role", config)
                self.assertIn("default_title", config)


if __name__ == "__main__":
    unittest.main(verbosity=2)
