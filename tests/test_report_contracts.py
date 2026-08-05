"""#4 回归测试 — 报告契约：V3 类型路由 + funnel 图表并入（锁定 #10 / #5 修复）

#10：此前 TYPE_TO_SECTION 缺失 V3 领域模型 analysis_type，导致 V3 包被丢弃、
     AI 报告为空。本测试锁定所有 V3 类型都已映射，且 build_input 能正确路由。

#5：funnel 等手写模型把图塞 `charts`(ChartItem) 字段而非 `chart_data`；
     报告侧 / 守卫只消费 `chart_data`。_extract_package 必须在 chart_data 为空时
     把 charts 并入 chart_data，否则 funnel 图在报告路径彻底隐形。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.report_builder import TYPE_TO_SECTION, ReportBuilder

# V3 领域模型 analysis_type（必须与 TYPE_TO_SECTION 一一对应）
V3_TYPES = [
    "rfm", "CLV", "cohort", "churn_rule", "churn_seg", "funnel",
    "association_rules", "user_profile", "sku_seg", "geo_seg",
    "activity_seg", "category_seg",
]


def test_v3_types_all_mapped():
    for t in V3_TYPES:
        assert t in TYPE_TO_SECTION, f"{t} 缺失于 TYPE_TO_SECTION（#10 回归）"
        assert TYPE_TO_SECTION[t], f"{t} 映射到空章节"


def test_build_input_routes_v3_rfm_package():
    pkg = {
        "analysis_type": "rfm",
        "business_question": "客户分层",
        "kpis": [{"label": "高价值客户占比", "value": "12.3%"}],
        "tables": [], "insights": ["i"], "conclusions": [], "recommendations": [],
        "chart_data": [], "findings": [],
    }
    out = ReportBuilder().build_input([pkg], None)
    assert "structure_analysis" in out["available_sections"]
    assert out["sections_data"]["structure_analysis"]


def test_funnel_charts_merged_into_chart_data():
    # funnel 模型走 `charts` 字段（非 chart_data）
    funnel_pkg = {
        "analysis_type": "funnel",
        "business_question": "转化漏斗",
        "kpis": [{"label": "整体转化率", "value": "12.3%"}],
        "tables": [], "insights": ["漏斗各层转化"], "conclusions": [], "recommendations": [],
        "chart_data": [],  # 空
        "charts": [  # 手写模型：图在 charts
            {"slot": "funnel_steps", "type": "funnel", "title": "转化漏斗各层", "data": [1, 2, 3]},
        ],
        "findings": [],
    }
    out = ReportBuilder().build_input([funnel_pkg], None)
    sec = out["sections_data"].get("funnel_analysis")
    assert sec is not None, "funnel 包应映射到 funnel_analysis 章节"
    charts = sec[0]["chart_data"]
    assert len(charts) == 1, "funnel 的 charts 必须并入 chart_data（#5 回归）"
    assert charts[0]["title"] == "转化漏斗各层"


def test_funnel_merge_not_duplicate_when_chart_data_present():
    # 其他模型经管线渲染出 charts 镜像，chart_data 已有内容时不应重复并入
    pkg = {
        "analysis_type": "funnel",
        "business_question": "q",
        "kpis": [], "tables": [], "insights": [], "conclusions": [], "recommendations": [],
        "chart_data": [{"slot": "a", "type": "funnel", "title": "已有图"}],
        "charts": [{"slot": "b", "type": "funnel", "title": "重复图"}],
        "findings": [],
    }
    out = ReportBuilder().build_input([pkg], None)
    charts = out["sections_data"]["funnel_analysis"][0]["chart_data"]
    titles = [c["title"] for c in charts]
    assert titles == ["已有图"], f"chart_data 非空时不应并入 charts 镜像，实际：{titles}"
