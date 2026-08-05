"""BUG1 回归测试：守卫在 LLM 简写图表标题时不应重复补图 / 新建重复章节，
且应把 LLM 简写标题对齐回源精确标题（保证前端图可加载）。

新结构（V4）：每个 section 用 chart_titles（字符串数组）声明引用图，守卫把高危图
标题补入 chart_titles 并就地对齐；section_charts（含 option）由后续 _bind 生成。
此处断言 chart_titles（守卫职责边界），不依赖 _bind。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai_agent.agent import (
    _enforce_high_severity_coverage,
    _title_to_slot,
    _norm_title,
)


def _make_funnel_sections_data():
    """源：funnel 包，一个 CRITICAL finding 引用 funnel_core 槽。"""
    return {
        "funnel_analysis": [
            {
                "analysis_type": "funnel",
                "dimension": "转化",
                "metric": "人数",
                "chart_data": [
                    {"slot": "funnel_core", "title": "转化漏斗（AARRR）", "type": "funnel"}
                ],
                "findings": [
                    {
                        "severity": "critical",
                        "title": "整体掉率偏高",
                        "category": "RISK",
                        "business_meaning": "掉率72.3%",
                        "business_impact": "需关注",
                        "recommendation": "优化转化",
                        "evidence": {"chart_slots": ["funnel_core"]},
                    }
                ],
                "kpis": [],
                "insights": [],
                "conclusions": [],
            }
        ]
    }


def _make_llm_sections_shortened():
    """LLM 已生成 funnel 章节，但把标题简写为 '转化漏斗'。"""
    return [
        {
            "type": "structure",
            "title": "漏斗分析",
            "content": "整体转化偏低，存在明显掉率。",
            "chart_titles": ["转化漏斗"],
        }
    ]


def test_title_to_slot_paraphrase():
    slot_to_title = {"funnel_core": "转化漏斗（AARRR）"}
    assert _title_to_slot("转化漏斗", slot_to_title) == "funnel_core"
    assert _title_to_slot("转化漏斗（AARRR）", slot_to_title) == "funnel_core"
    # 全半角 / 空格不一致也应识别
    assert _title_to_slot("转化漏斗(aarr)", slot_to_title) == "funnel_core"
    assert _title_to_slot("完全无关标题", slot_to_title) is None


def test_norm_title_collapses_spaces_and_fullwidth():
    assert _norm_title("RFM 8 大群体占比") == _norm_title("RFM 8大群体占比")
    assert _norm_title("客户生命周期价值（高/中/低 平均价值）") == \
        "客户生命周期价值(高/中/低平均价值)"


def test_guard_no_duplicate_when_llm_shortened_title():
    sd = _make_funnel_sections_data()
    sections = _make_llm_sections_shortened()
    out = _enforce_high_severity_coverage(sections, sd)

    # 1) LLM 简写标题被就地对齐为精确标题（前端可绑定）
    funnel_sec = out[0]
    assert funnel_sec["chart_titles"][0] == "转化漏斗（AARRR）"

    # 2) funnel_core 图只出现一次（守卫未重复补图）
    assert funnel_sec["chart_titles"].count("转化漏斗（AARRR）") == 1

    # 3) 未新建第二个章节（兄弟章节被正确识别，而非新建重复章节）
    assert len(out) == 1


def test_guard_injects_once_when_llm_missing():
    sd = _make_funnel_sections_data()
    sections = [{"type": "structure", "title": "漏斗分析", "content": "", "chart_titles": []}]
    out = _enforce_high_severity_coverage(sections, sd)

    # 守卫在空壳 section 上会把高危图 title 补入其 chart_titles（落位边界），
    # 这里对全部 section 的 chart_titles 做全量检查。
    all_titles = [t for s in out for t in (s.get("chart_titles") or [])]
    assert all_titles.count("转化漏斗（AARRR）") == 1  # 兜底去重后无重复


def test_guard_dedup_safeguard_on_double_injection_attempt():
    """构造一个会让守卫尝试重复补图的极端输入，验证兜底去重生效。"""
    sd = _make_funnel_sections_data()
    # LLM 写出了一个精确标题的 chart_titles（已覆盖），守卫不应再补
    sections = [
        {
            "type": "structure",
            "title": "漏斗分析",
            "content": "整体转化偏低。",
            "chart_titles": ["转化漏斗（AARRR）"],
        }
    ]
    out = _enforce_high_severity_coverage(sections, sd)
    funnel_sec = out[0]
    titles = funnel_sec["chart_titles"]
    assert titles.count("转化漏斗（AARRR）") == 1
    # 未新建第二个 section（已覆盖，未新建兄弟章节）
    assert len(out) == 1
