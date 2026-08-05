"""#4 回归测试 — 高危发现防漏守卫 _enforce_high_severity_coverage

守卫保证所有 CRITICAL/HIGH 业务发现的「图表 + 文字」都出现在报告中。
覆盖四种关键路径：
1. 多图发现：一张 finding 引用多张图，缺哪张补哪张（不能 any() 短路漏掉兄弟图）；
2. 已覆盖：LLM 已引用该图 → 不重复注入；
3. 兄弟章节：注入到已存在且含兄弟图的 LLM 章节，而非新建章节；
4. 降级路径：_build_fallback_from_packages 后守卫仍能把高危图补入（#3 真触发路径）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai_agent.agent import (
    _build_fallback_from_packages,
    _enforce_high_severity_coverage,
)


def _make_sections_data(two_charts: bool = True):
    slots = (
        ["churn_tier_pie", "bubble_matrix__retention_priority"]
        if two_charts else ["churn_tier_pie"]
    )
    pkg = {
        "analysis_type": "churn_rule",
        "findings": [{
            "category": "RISK",
            "title": "整体流失率 70.9% 偏高",
            "severity": "HIGH",
            "evidence": {"chart_slots": slots},
            "business_meaning": "留存结构脆弱",
            "business_impact": "高价值客户仅 1234 人",
            "recommendation": "优先挽回高价值",
        }],
        "chart_data": [
            {"slot": "churn_tier_pie", "type": "pie", "title": "三档用户占比"},
            {"slot": "bubble_matrix__retention_priority", "type": "bubble",
             "title": "挽回优先级气泡矩阵"},
        ],
        "kpis": [], "tables": [], "insights": [], "conclusions": [], "recommendations": [],
    }
    return {"risk_analysis": [pkg]}


def _enforced_insights(sections):
    return [i for s in sections for i in s.get("insights", []) if i.get("_enforced")]


def test_guard_injects_both_charts_when_missing():
    sd = _make_sections_data()
    sections = [{"type": "executive_summary", "title": "执行摘要", "content": "摘要"}]
    out = _enforce_high_severity_coverage(sections, sd)
    enforced = _enforced_insights(out)
    titles = {i["chart_title"] for i in enforced}
    assert "三档用户占比" in titles
    assert "挽回优先级气泡矩阵" in titles
    assert len(enforced) == 2, f"两张高危图都应补入，实际 {len(enforced)}"


def test_guard_skips_already_covered():
    sd = _make_sections_data()
    # LLM 已引用饼图（三档用户占比），但没引用气泡矩阵
    sections = [{
        "type": "risk_analysis", "title": "风险",
        "insights": [{"chart_title": "三档用户占比", "analysis": "饼图已覆盖"}],
    }]
    out = _enforce_high_severity_coverage(sections, sd)
    enforced = _enforced_insights(out)
    titles = {i["chart_title"] for i in enforced}
    assert "三档用户占比" not in titles, "已覆盖的图不应重复注入"
    assert "挽回优先级气泡矩阵" in titles, "缺失的兄弟图应被补入"


def test_guard_injects_into_sibling_section():
    sd = _make_sections_data()
    # LLM 已有 risk_analysis 章节并引用了兄弟图（饼图）
    sections = [{
        "type": "risk_analysis", "title": "风险",
        "insights": [{"chart_title": "三档用户占比", "analysis": "x"}],
    }]
    out = _enforce_high_severity_coverage(sections, sd)
    risk_secs = [s for s in out if s.get("type") == "risk_analysis"]
    assert len(risk_secs) == 1, "不应新建额外章节，应注入到兄弟章节"
    bubble = [i for i in risk_secs[0].get("insights", [])
              if i.get("chart_title") == "挽回优先级气泡矩阵"]
    assert bubble, "气泡矩阵应注入到同一 risk_analysis 兄弟章节"


def test_guard_fallback_path():
    sd = _make_sections_data()
    raw_pkg = sd["risk_analysis"][0]
    report_input = {"sections_data": sd, "packages_summary": "", "data_profile": {}}
    fallback = _build_fallback_from_packages([raw_pkg], report_input)
    assert fallback, "降级报告不应为空"
    out = _enforce_high_severity_coverage(fallback, sd)
    # 降级自身会引用 charts[0]（饼图），故守卫只补入缺失的兄弟图（气泡矩阵）。
    # 最终报告必须同时包含两张高危图：饼图由降级引用，气泡矩阵由守卫补入。
    all_titles = {
        i.get("chart_title")
        for s in out for i in s.get("insights", []) if i.get("chart_title")
    }
    assert "三档用户占比" in all_titles
    assert "挽回优先级气泡矩阵" in all_titles
    # 缺失的那张（气泡矩阵）必须经守卫确定性补入
    enforced = _enforced_insights(out)
    assert "挽回优先级气泡矩阵" in {i["chart_title"] for i in enforced}
