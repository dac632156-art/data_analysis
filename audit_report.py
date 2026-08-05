"""audit_report.py — 真实 LLM 报告「事实溯源」审计（需用户自备 API Key）

这是 #2 的「真机」入口：上传 CSV → 跑分析流水线得到 AnalysisPackage →
调真实 LLM 生成报告 → 对报告做事实溯源审计（src/ai_agent/report_audit.py）。

为何需要你自己的 Key：本项目的 API Key 是「每会话、运行时」提供（来自前端请求或
会话状态），从不落库进 git（.env 与 data/app.db 均被 .gitignore 忽略）。因此本机
没有任何可复用的 Key，必须由你提供才能调用真实 LLM 审计其输出质量。

用法（Windows cmd）：
  set AGNES_API_KEY=sk-你的密钥
  set AGNES_BASE_URL=https://apihub.agnes-ai.com/v1
  set AGNES_MODEL=agnes-2.5-flash
  python audit_report.py path/to/data.csv

或 PowerShell：
  $env:AGNES_API_KEY="sk-你的密钥"
  python audit_report.py path/to/data.csv
"""
import argparse
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    ap = argparse.ArgumentParser(description="真实 LLM 报告事实溯源审计")
    ap.add_argument("csv", help="待分析的 CSV 文件路径")
    ap.add_argument("--rows", type=int, default=5000, help="采样行数上限（默认 5000）")
    args = ap.parse_args()

    api_key = os.environ.get("AGNES_API_KEY")
    if not api_key:
        print("✗ 缺少环境变量 AGNES_API_KEY。请先设置你的 API Key 后再运行。")
        print("  例: set AGNES_API_KEY=sk-xxxx  然后 python audit_report.py data.csv")
        return 2
    base_url = os.environ.get("AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1")
    model = os.environ.get("AGNES_MODEL", "agnes-2.5-flash")

    import pandas as pd
    from backend.services.session_manager import manager
    from backend.routers.analysis import _resolve_process_items, _process_one
    from src.ai_agent.agent import DataAnalysisAgent
    from src.report_builder import ReportBuilder
    from src.ai_agent.report_audit import audit_report, format_audit

    session_id = f"audit_{uuid.uuid4().hex[:8]}"
    if not os.path.exists(args.csv):
        print(f"✗ 文件不存在: {args.csv}")
        return 2

    df = pd.read_csv(args.csv, nrows=args.rows)
    did = manager.add_dataset(
        session_id, df,
        file_name=os.path.basename(args.csv),
        file_size_bytes=os.path.getsize(args.csv),
        rows=len(df), columns=list(df.columns),
        column_info=[], preview=[], set_active=True,
    )
    print(f"[OK] 上传 {os.path.basename(args.csv)} -> {did[:8]} rows={len(df)}")

    items = _resolve_process_items(session_id, [did], {})
    print(f"[OK] 解析出 {len(items)} 个分析项")
    merged_packages = []
    for it in items:
        try:
            _count, merged = _process_one(session_id, it["dataset_id"], {})
            merged_packages.extend(merged)
        except Exception as e:  # noqa: BLE001
            print(f"  [WARN] 处理项失败: {e}")
    print(f"[OK] 生成 {len(merged_packages)} 个 AnalysisPackage")

    if not merged_packages:
        print("✗ 未生成任何分析包，无法审计。")
        return 1

    # 源真值（供溯源比对）
    builder = ReportBuilder()
    report_input = builder.build_input(merged_packages, None)
    sections_data = report_input["sections_data"]

    # 调用真实 LLM 生成报告
    agent = DataAnalysisAgent(api_key=api_key, model=model, base_url=base_url)
    print("[...] 调用 LLM 生成报告（可能耗时数十秒，超时将自动降级）")
    result = agent.generate_report_from_packages(merged_packages, None)
    sections = result.get("sections", []) or []
    degraded = result.get("degradation", {}).get("degraded", False)
    print(f"[OK] 报告生成 success={result.get('success')} degraded={degraded} sections={len(sections)}")

    # 事实溯源审计
    audit = audit_report(sections, sections_data)
    print()
    print(format_audit(audit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
