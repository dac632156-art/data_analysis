"""#2 事实溯源审计器 — 单元测试 + 自证（无需真实 LLM / API Key）

验证 report_audit.audit_report 能：
1. 把 万/亿 量纲正确归一化；
2. 把源中存在的数字判为 TRACED；
3. 把凭空编造（量级偏离>5%）的数字判为 UNTRACEABLE（疑似幻觉）；
4. 把报告引用的、源中不存在的图表标题标记为缺失；
5. 过滤结构性数字（年/经验/段/条）以降低误报。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai_agent.report_audit import (
    audit_report,
    build_ground_numbers,
    extract_numbers,
    _normalize_number,
    _norm_title,
)


# ---------------------------------------------------------------------------
# 构造一个贴近 ReportBuilder.build_input 输出的 sections_data
# ---------------------------------------------------------------------------

def _make_sections_data():
    return {
        "retention_analysis": [
            {
                "analysis_type": "churn_rule",
                "kpis": [
                    {"label": "整体流失率", "value": "70.9%", "change": "", "type": "rate"},
                ],
                "tables": [
                    {
                        "title": "三档用户流失分布",
                        "columns": ["档位", "人数", "流失率"],
                        "rows": [
                            ["高价值", "1234", "12.3%"],
                            ["成长", "4500", "68.2%"],
                            ["长尾", "8900", "91.0%"],
                        ],
                        "total_rows": 3,
                    }
                ],
                "findings": [
                    {
                        "category": "RISK",
                        "title": "整体流失率 70.9% 偏高",
                        "description": "整体流失率 70.9%，长尾客户 8900 人流失率 91.0%。",
                        "metric": "churn_rate",
                        "entity": "全部",
                        "business_meaning": "留存结构脆弱",
                        "business_impact": "高价值客户仅 1234 人",
                        "recommendation": "挽回高价值",
                        "severity": "HIGH",
                        "evidence": {"chart_slots": ["churn_tier_pie"]},
                    }
                ],
                "insights": ["长尾客户流失率高达 91.0%"],
                "conclusions": ["留存是核心风险"],
                "chart_data": [
                    {"slot": "churn_tier_pie", "type": "pie", "title": "三档用户占比"},
                ],
            }
        ]
    }


def _make_report_with_fabrication():
    return [
        {
            "type": "executive_summary",
            "title": "执行摘要",
            "content": (
                "整体流失率高达 70.9%，其中高价值客户 1234 人。"
                "但某头部渠道贡献了 38.7% 的营收，另一渠道占 92.5%，"
                "长尾客户达 5678 人，本顾问拥有 15 年经验，提出 3 条建议。"
            ),
        },
        {
            "type": "retention_analysis",
            "title": "留存分析",
            "insights": [
                {
                    "chart_title": "三档用户占比",
                    "analysis": "三档中高价值客户 1234 人，流失率仅 12.3%。",
                },
                {
                    "chart_title": "不存在的图",
                    "analysis": "基于一张不存在的图表做出的解读。",
                },
            ],
        },
    ]


def test_normalize_scale():
    assert _normalize_number("1.2", "万", "") == 12000.0
    assert _normalize_number("3", "亿", "") == 300000000.0
    assert _normalize_number("70.9", "", "%") == 70.9
    assert _normalize_number("1,234", "", "") == 1234.0


def test_extract_numbers_handles_scale_and_pct():
    nums = extract_numbers("营收 1.2 亿，流失率 70.9%，人数 1,234")
    vals = [v for v, _r, _p, _s in nums]
    assert 120000000.0 in vals
    assert 70.9 in vals
    assert 1234.0 in vals


def test_ground_numbers_built():
    sd = _make_sections_data()
    ground = build_ground_numbers(sd)
    assert 70.9 in ground
    assert 1234 in ground
    assert 8900 in ground
    assert 91.0 in ground


def test_audit_flags_fabrication():
    sd = _make_sections_data()
    report = _make_report_with_fabrication()
    audit = audit_report(report, sd)

    untraceable_raws = {r.claim.raw for r in audit.untraceable}
    approx_raws = {r.claim.raw for r in audit.approx}
    # 38.7% 与 5678 是明显编造（源中无近似真值）→ UNTRACEABLE
    assert any("38.7" in r for r in untraceable_raws)
    assert any("5678" in r for r in untraceable_raws)
    # 92.5% 贴近一个语义无关的真实 91.0%（长尾流失率），被判 APPROX 需人工复核
    # （百分比量纲紧凑导致的已知局限，已在文档中说明）
    assert any("92.5" in r for r in approx_raws)

    # 真实数字应被判为可溯源
    traced_raws = {r.claim.raw for r in audit.claim_results if r.status == "TRACED"}
    assert any("70.9" in r for r in traced_raws)
    assert any("1234" in r for r in traced_raws)

    # 图表标题缺失检测
    assert "不存在的图" in audit.missing_chart_titles
    assert "三档用户占比" not in audit.missing_chart_titles

    # 结构性数字（15 年经验 / 3 条建议）不应进入待审列表
    all_raws = {r.claim.raw for r in audit.claim_results}
    # "15"（年经验）与 "3"（条建议）是结构性数字，应被过滤，不进入待审声明
    assert "15" not in all_raws
    assert "3" not in all_raws
    # 但真实业务数字 12.3%（流失率）必须保留
    assert any("12.3" in r for r in all_raws)


def test_audit_clean_report_has_no_untraceable():
    sd = _make_sections_data()
    clean_report = [
        {
            "type": "executive_summary",
            "title": "执行摘要",
            "content": "整体流失率 70.9%，高价值客户 1234 人，长尾客户 8900 人。",
        },
        {
            "type": "retention_analysis",
            "title": "留存分析",
            "insights": [
                {"chart_title": "三档用户占比", "analysis": "高价值客户流失率 12.3%。"}
            ],
        },
    ]
    audit = audit_report(clean_report, sd)
    assert audit.untraceable == []
    assert audit.missing_chart_titles == []


def test_norm_title_collapses_spaces_and_fullwidth():
    # 去空白 + NFKC 全角→半角，使 LLM 改写版本与源标题归一化后一致
    assert _norm_title("RFM 8 大群体占比") == _norm_title("RFM 8大群体占比")
    assert _norm_title("同期群质量趋势（偏移 j 留存率）") == _norm_title("同期群质量趋势（偏移j留存率）")
    assert _norm_title("客户生命周期价值 分布直方图（等宽分箱）") == "客户生命周期价值分布直方图(等宽分箱)"


def test_chart_title_paraphrase_not_flagged_missing():
    # 真机审计中观察到的 4 个「误报缺失」：源标题含空格/括号注，LLM 引用时省略
    sd = {
        "structure_analysis": [
            {"chart_data": [{"slot": "s1", "type": "pie", "title": "RFM 8 大群体占比"}]}
        ],
        "concentration_analysis": [
            {
                "chart_data": [
                    {"slot": "c1", "type": "hist", "title": "客户生命周期价值 分布直方图（等宽分箱）"},
                    {"slot": "c2", "type": "bar", "title": "客户生命周期价值 分层（高/中/低 平均价值）"},
                ]
            }
        ],
        "retention_analysis": [
            {"chart_data": [{"slot": "r1", "type": "line", "title": "同期群质量趋势（偏移 j 留存率）"}]}
        ],
    }
    report = [
        {
            "type": "structure_analysis",
            "insights": [
                {"chart_title": "RFM 8大群体占比", "analysis": "结构稳定。"},
                {"chart_title": "客户生命周期价值分布直方图", "analysis": "分布右偏。"},
                {"chart_title": "客户生命周期价值分层（高/中/低平均价值）", "analysis": "高价值占比低。"},
            ],
        },
        {
            "type": "retention_analysis",
            "insights": [
                {"chart_title": "同期群质量趋势（偏移j留存率）", "analysis": "留存下滑。"},
            ],
        },
    ]
    audit = audit_report(report, sd)
    for t in [
        "RFM 8大群体占比",
        "客户生命周期价值分布直方图",
        "客户生命周期价值分层（高/中/低平均价值）",
        "同期群质量趋势（偏移j留存率）",
    ]:
        assert t not in audit.missing_chart_titles, f"改写标题被误判缺失: {t}"

    # 真正不存在的标题仍应被标出（防止归一化把真缺失也吞掉）
    report[0]["insights"].append({"chart_title": "客户流失预测热力图", "analysis": "不存在的图。"})
    audit2 = audit_report(report, sd)
    assert "客户流失预测热力图" in audit2.missing_chart_titles
