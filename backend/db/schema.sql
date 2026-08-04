-- ============================================================
-- DataMind AI 数据库结构定义（SQLite）
-- ============================================================
-- 用途：替代原"内存 + 临时 pickle"存储，使 session / 上传数据 / 分析结果
--       在后端重启或云实例休眠后不丢失，并可作为独立组件分发给他人。
--
-- 分发说明：别人拿到本 schema.sql + 任意 .db 文件（或空库），执行本脚本即可
--           重建全部表结构；无需安装额外数据库软件，Python 标准库 sqlite3 即可读写。
--
-- 建表幂等：全部使用 IF NOT EXISTS，可重复执行。
-- ============================================================

-- 会话表：存储单个会话的可序列化状态（不含 DataFrame 本体）。
-- DataFrame 体积可能很大（本地支持 1GB），不强行塞 BLOB，
-- 而是保留"落盘 pickle 文件"机制，路径索引在 datasets 表。
-- state_json 含：api_key / custom_title / cleaning_history / analysis_history /
--                saved_charts / analysis_packages / saved_packages / df_undo_stack /
--                dataset_packages 索引 / active_dataset_id / 各类时间戳标记。
CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    state_json   TEXT NOT NULL,            -- 会话可序列化状态（JSON）
    created_at   REAL NOT NULL,            -- 创建时间戳
    last_access  REAL NOT NULL             -- 最后访问时间戳（用于过期清理判断）
);

-- 数据集表：每个上传的报表对应一行。DataFrame 落盘为 pickle 文件，
-- 这里只记录其持久化路径（data/ 目录，已加入 .gitignore），重启后按路径 reload。
-- meta_json 含：file_name / file_size_bytes / rows / columns / column_info /
--               preview / is_merged / sources / merge_keys / uploaded_at。
CREATE TABLE IF NOT EXISTS datasets (
    dataset_id   TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    meta_json    TEXT NOT NULL,            -- 数据集元信息（JSON）
    original_path TEXT NOT NULL,           -- DataFrame pickle 持久化路径
    is_active    INTEGER NOT NULL DEFAULT 0,-- 是否为该会话当前 active 数据集
    created_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_datasets_session ON datasets(session_id);

-- 分析包表：AnalysisPackage 序列化后存储（dataclasses.asdict -> JSON）。
-- 一个数据集可对应多个分析包（package_id 唯一）。
CREATE TABLE IF NOT EXISTS analysis_packages (
    package_id   TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    dataset_id   TEXT NOT NULL,
    payload_json TEXT NOT NULL,            -- AnalysisPackage 完整 JSON
    saved_at     TEXT,                     -- 用户保存时间戳（可空）
    created_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_packages_session ON analysis_packages(session_id);
CREATE INDEX IF NOT EXISTS idx_packages_dataset ON analysis_packages(dataset_id);

-- 说明：saved_packages（用户已保存的分析包列表）已并入 sessions.state_json，
--       无需独立表；如需独立审计可后续拆分，但本版遵循最小改动原则。
