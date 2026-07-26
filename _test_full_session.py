"""完整端到端模拟：使用全局 manager + 上传 + process_datasets 流水线"""
import sys
sys.path.insert(0, '.')
import os
import pandas as pd
import uuid
from backend.services.session_manager import manager

session_id = f"test_{uuid.uuid4().hex[:8]}"
print(f"Session: {session_id}")

# 上传测试4所有表到全局 manager
base = '数据测试集/测试4'
tables_to_upload = ['orders', 'customers', 'events', 'order_items', 'products', 'reviews', 'sessions']
for i, name in enumerate(tables_to_upload):
    try:
        df = pd.read_csv(f'{base}/{name}.csv', nrows=2000)
        did = manager.add_dataset(
            session_id, df,
            file_name=f"{name}.csv",
            file_size_bytes=os.path.getsize(f'{base}/{name}.csv'),
            rows=len(df),
            columns=list(df.columns),
            column_info=[],
            preview=[],
            set_active=(i == 0)
        )
        print(f"  [OK] {name} -> {did[:8]} (active={i==0})")
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")

# 检查 session
all_dids = list(manager.get_session(session_id).datasets.keys())
print(f"\nSession 中数据集: {len(all_dids)} 个")
for did in all_dids:
    ds = manager.get_session(session_id).datasets[did]
    has_df = ds.df is not None
    has_pickle = ds.original_path and os.path.exists(ds.original_path)
    df_test = manager.get_dataset_df(session_id, did)
    print(f"  {did[:8]} ({ds.file_name}): df_in_mem={has_df}, pickle_exists={has_pickle}, get_df={'OK' if df_test is not None else 'NONE!'}")

# 跑真实的 _resolve_process_items
from backend.routers.analysis import _resolve_process_items, _process_one
print("\n=== 执行 _resolve_process_items ===")
items = _resolve_process_items(session_id, all_dids, {})
print(f"产生 {len(items)} 个处理项:")
for it in items:
    print(f"  {it['kind']}: id={it['dataset_id'][:8]}, sources={it.get('sources',[])}")

# 跑 _process_one
print("\n=== 执行 _process_one ===")
total_pkgs = 0
for idx, it in enumerate(items):
    did = it["dataset_id"]
    print(f"\n--- 项 {idx+1}/{len(items)}: {did[:8]} ({it['kind']}) ---")
    try:
        pkg_count, merged = _process_one(session_id, did, {})
        print(f"  结果: pkg_count={pkg_count}, merged列表长度={len(merged)}")
        for p in merged:
            pid = p.get("id", "?")
            cr = p.get("can_run", "?")
            reason = p.get("fallback_reason", "")
            print(f"    -> {pid}: can_run={cr}" + (f", reason={reason}" if reason else ""))
        total_pkgs += pkg_count
    except Exception as e:
        import traceback
        print(f"  [ERROR] {e}")
        traceback.print_exc()

print(f"\n====== 总计: {total_pkgs} 个包 ======")

# dataset_packages
print("\n=== dataset_packages ===")
for did in all_dids:
    pkgs = manager.get_dataset_packages(session_id, did)
    print(f"  {did[:8]}: {len(pkgs)} 个包")
