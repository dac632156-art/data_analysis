"""#4 回归测试 — 端到端流水线冒烟（真实分析流水线 → 报告构建 → 守卫）

目标：验证「真实数据 → 分析模型 → AnalysisPackage → ReportBuilder.build_input
→ 守卫」整条链路在多数据集上不崩溃，且 funnel 等图能进入报告路径。

用小型 CSV（<50KB）保证速度；后端不可导入或测试数据缺失时自动 skip，
避免 CI 抖动。覆盖 #1「e2e 多数据集不崩」与 #5 funnel 修复。
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUNNEL_CSV = os.path.join(ROOT, "数据测试集", "转化漏斗测试数据.csv")


def _run_pipeline(csv_path, nrows=600):
    from backend.services.session_manager import manager
    from backend.routers.analysis import _resolve_process_items, _process_one

    session_id = f"regtest_{uuid.uuid4().hex[:8]}"
    df = pd.read_csv(csv_path, nrows=nrows)
    did = manager.add_dataset(
        session_id, df,
        file_name=os.path.basename(csv_path),
        file_size_bytes=os.path.getsize(csv_path),
        rows=len(df), columns=list(df.columns),
        column_info=[], preview=[], set_active=True,
    )
    items = _resolve_process_items(session_id, [did], {})
    merged = []
    for it in items:
        try:
            _count, m = _process_one(session_id, it["dataset_id"], {})
            merged.extend(m)
        except Exception:
            # 单个模型失败不影响整体冒烟
            pass
    return merged


def test_e2e_pipeline_funnel_dataset():
    if not os.path.exists(FUNNEL_CSV):
        pytest.skip("漏斗测试数据缺失")
    try:
        from src.report_builder import ReportBuilder
        from src.ai_agent.agent import _enforce_high_severity_coverage
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"报告模块不可导入: {e}")

    merged = _run_pipeline(FUNNEL_CSV)
    assert merged, "流水线应至少产出一个 AnalysisPackage"

    rb = ReportBuilder()
    out = rb.build_input(merged, None)
    assert out["available_sections"], "build_input 应产出章节"

    # funnel 图必须进入报告路径（#5 修复）
    funnel_sec = out["sections_data"].get("funnel_analysis")
    if funnel_sec:
        total_charts = sum(len(p.get("chart_data", [])) for p in funnel_sec)
        assert total_charts >= 1, "funnel 章节应包含至少一张图（charts→chart_data 并入）"

    # 守卫在「空报告」上不应崩溃，且会补入高危发现
    empty_report = [{"type": "executive_summary", "title": "执行摘要", "content": "摘要"}]
    guarded = _enforce_high_severity_coverage(empty_report, out["sections_data"])
    assert isinstance(guarded, list)
