"""V4 重构回归测试：_bind_package_charts_to_sections 与 ReportBuilder 图表元数据传递。

1) option 为 None 的图必须被跳过——否则前端 EtherealRadarChart 对 null.title
   取值会崩溃整页（React 被 ErrorBoundary 重建）。与路由 report.py 的
   `not chart.get("option")` 过滤保持一致。
2) 同一 section 内按 slot 去重——LLM 重复声明同一张图（或 chart_titles 含一个
   slot 的多处引用）时，避免前端 key=slot 撞车（React 重复 key 警告
   `hbar__attr_dim_offset`）。
3) ReportBuilder._safe_chart_data 必须保留 option/raw_data/role——若被剥离，
   V4 绑定会把所有图当成「无 option」而跳过，导致报告中「有文字无图表」。
"""
from src.ai_agent.agent import _bind_package_charts_to_sections
from src.report_builder import ReportBuilder


def _sections_data():
    return {
        "structure": [
            {
                "chart_data": [
                    {
                        "title": "维度偏移图",
                        "slot": "hbar__attr_dim_offset",
                        "chart_type": "hbar_family",
                        "option": {"indicator": [{"name": "x", "max": 1}], "series": [{"data": [{"value": [1], "name": "a"}]}]},
                        "raw_data": [{"维度": "x", "偏移值": 1}],
                    },
                    {
                        "title": "无图元的图",
                        "slot": "broken_slot",
                        "chart_type": "radar",
                        "option": None,  # 未渲染出 option，应被跳过
                        "raw_data": None,
                    },
                ],
            }
        ]
    }


def test_bind_skips_null_option():
    sections = [
        {"type": "structure", "title": "结构分析", "chart_titles": ["维度偏移图", "无图元的图"]}
    ]
    out = _bind_package_charts_to_sections(sections, _sections_data())
    bound = out[0]["section_charts"]
    titles = [c["title"] for c in bound]
    assert "无图元的图" not in titles
    assert "维度偏移图" in titles
    # 绑定的图必须带真实 option
    assert all(c["option"] for c in bound)


def test_bind_dedup_same_slot_in_section():
    # LLM 把同一张图在 chart_titles 里声明了两次（简写/重复引用）
    sections = [
        {"type": "structure", "title": "结构分析", "chart_titles": ["维度偏移图", "维度偏移图"]}
    ]
    out = _bind_package_charts_to_sections(sections, _sections_data())
    bound = out[0]["section_charts"]
    assert len(bound) == 1
    slots = [c["slot"] for c in bound]
    assert slots.count("hbar__attr_dim_offset") == 1


def test_bind_unmatched_title_ignored():
    sections = [{"type": "structure", "title": "结构分析", "chart_titles": ["根本不存在的图"]}]
    out = _bind_package_charts_to_sections(sections, _sections_data())
    assert out[0]["section_charts"] == []


def test_report_builder_preserves_chart_option_for_binding():
    """完整链路：ReportBuilder 不能把 AnalysisPackage 里的 option/raw_data 剥离掉，
    否则 _bind_package_charts_to_sections 会因 option 为空而跳过所有图。"""
    packages = [
        {
            "analysis_type": "structure_analysis",
            "business_question": "用户结构如何？",
            "chart_data": [
                {
                    "title": "用户分层雷达图",
                    "slot": "rfm_radar",
                    "chart_type": "radar",
                    "option": {"indicator": [{"name": "R", "max": 5}], "series": [{"data": [{"value": [1, 2, 3], "name": "a"}]}]},
                    "raw_data": [{"维度": "R", "值": 1}],
                    "role": "evidence",
                }
            ],
            "findings": [],
        }
    ]
    report_input = ReportBuilder().build_input(packages, data_profile=None)
    sections_data = report_input["sections_data"]
    sections = [{"type": "structure", "title": "结构分析", "chart_titles": ["用户分层雷达图"]}]
    out = _bind_package_charts_to_sections(sections, sections_data)
    bound = out[0]["section_charts"]
    assert len(bound) == 1
    assert bound[0]["title"] == "用户分层雷达图"
    assert bound[0]["option"] is not None
    assert bound[0]["raw_data"] == [{"维度": "R", "值": 1}]
    assert bound[0]["role"] == "evidence"
