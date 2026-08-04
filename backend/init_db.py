"""
数据库初始化入口。

用途：
1. 首次部署/分发时执行 `python backend/init_db.py`，按 schema.sql 建表。
2. 后端启动时（main.py startup 事件）也会调用 init_db()，保证表结构存在。

别人拿到本项目后，只需：
    pip install -r requirements.txt
    python backend/init_db.py
即可在本机创建 data/app.db 并使用（无需安装额外数据库软件）。
"""
import os
import sys


def main():
    # 确保 backend/ 在路径中，便于 from backend.db 导入
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    # project_root 也加入，确保 config / .env 可被加载
    project_root = os.path.dirname(backend_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from backend.db.connection import init_db
    init_db()
    print("✅ 数据库初始化完成（表结构已确保存在）")


if __name__ == "__main__":
    main()
