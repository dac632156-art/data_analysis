"""
持久化验证测试：模拟"后端重启"后数据能否从 SQLite 恢复。

核心验证点：
1. 写入 session/dataset/analysis_package 后落库。
2. 新建一个 SessionManager 实例（模拟重启，内存为空），get_session 能从 SQLite 重建。
3. DataFrame 能按 original_path 重新加载（不因重启丢失）。
4. saved_packages 等分析结果能读回。

运行：
    cd d:\数据分析项目
    python tests/test_db_persistence.py
（使用临时 DB_PATH，不污染真实 data/app.db）
"""
import os
import sys
import io
import tempfile
import shutil

# Windows 控制台 GBK 无法编码 emoji/部分中文，统一用 utf-8 包装 stdout
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 必须在导入 backend 模块前设置临时数据库路径
_TMP = tempfile.mkdtemp(prefix="datamind_test_db_")
os.environ["DB_PATH"] = os.path.join(_TMP, "test_app.db")

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
_backend = os.path.join(_project_root, "backend")
if _backend not in sys.path:
    sys.path.insert(0, _backend)

import pandas as pd

from backend.services.session_manager import SessionManager
from backend.db.connection import init_db, DB_PATH


def _make_df():
    return pd.DataFrame({
        "user_id": [1, 2, 3, 4],
        "amount": [100, 200, 150, 300],
        "city": ["北京", "上海", "广州", "深圳"],
    })


def main():
    init_db()
    print(f"使用测试数据库: {DB_PATH}")

    sid = "test-session-001"
    # ---- 第一次：写入数据（模拟运行时）----
    m1 = SessionManager()
    m1.create_session() if False else None  # create_session 返回新 id，这里直接用指定 sid
    # 直接构造会话并写入：用 add_dataset 走正式入口
    df = _make_df()
    did = m1.add_dataset(
        sid, df,
        file_name="test.csv", file_size_bytes=123, rows=4, columns=list(df.columns),
        column_info=[{"name": c, "type": str(df[c].dtype)} for c in df.columns],
        preview=df.head(3).to_dict("records"),
    )
    m1.set_custom_title(sid, "我的分析")
    m1.set_api_key(sid, "sk-test")
    m1.save_chart(sid, {"id": "c1", "title": "图1", "chart_type": "bar"})
    # 伪造一个分析包并暂存（set_analysis_packages 按 pkg_id 存 dict）
    fake_pkg = {
        "id": "pkg-1", "model": "rfm", "title": "RFM分析",
        "chart_data": [{"slot": "s1", "chart_type": "pie", "title": "占比", "data": [1, 2, 3]}],
        "kpis": [{"label": "总数", "value": 4}],
    }
    m1.set_analysis_packages(sid, {"pkg-1": fake_pkg})
    # 再将其保存进 saved_packages（save_packages 接收 pkg_id 列表）
    m1.save_packages(sid, ["pkg-1"])
    print(f"写入完成 did={did}")

    # ---- 第二次：模拟"重启"——新建 SessionManager 实例，内存为空 ----
    m2 = SessionManager()
    sess = m2.get_session(sid)
    assert sess is not None, "❌ 重启后无法从 SQLite 恢复会话"
    assert sess.custom_title == "我的分析", "❌ custom_title 未恢复"
    assert sess.api_key == "sk-test", "❌ api_key 未恢复"
    assert len(sess.saved_charts) == 1 and sess.saved_charts[0]["id"] == "c1", "❌ saved_charts 未恢复"
    assert len(sess.saved_packages) == 1 and sess.saved_packages[0]["id"] == "pkg-1", "❌ saved_packages 未恢复"
    print("✅ 会话轻量状态（标题/key/图表/分析包）重启后完整恢复")

    # ---- 验证 DataFrame 能按落盘路径 reload ----
    reloaded = m2.get_dataset_df(sid, did)
    assert reloaded is not None, "❌ 重启后 DataFrame 无法 reload"
    assert len(reloaded) == 4, "❌ reload 后行数不对"
    assert list(reloaded.columns) == ["user_id", "amount", "city"], "❌ reload 后列不对"
    print("✅ DataFrame 按 original_path 重启后成功 reload（行数/列正确）")

    # ---- 验证删除同步删库 ----
    m2.clear_data(sid)
    m3 = SessionManager()
    assert m3.get_session(sid) is None, "❌ clear_data 未同步删除 SQLite 记录"
    print("✅ clear_data 同步从 SQLite 删除（重启后查不到）")

    # 清理临时目录
    shutil.rmtree(_TMP, ignore_errors=True)
    print("\n🎉 全部持久化测试通过：重启/新实例可从 SQLite 恢复数据，删除同步落库。")


if __name__ == "__main__":
    main()
