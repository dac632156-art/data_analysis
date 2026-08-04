# DataMind AI 数据库分发说明（SQLite）

本文件说明：如何把本项目的数据库组件**单独发给别人、别人在本机直接用**，以及数据库与前端/后端的解耦关系。

---

## 一、这个数据库是什么

- **类型**：SQLite 单文件数据库（Python 标准库 `sqlite3` 即可读写，**无需安装任何数据库软件**）。
- **位置**：默认 `data/app.db`（由 `.env` 的 `DB_PATH` 配置，相对项目根）。
- **作用**：替代原"后端内存 + 临时 pickle 文件"存储，保存：
  - 用户会话（session）配置与轻量状态
  - 上传的数据集元信息 + DataFrame 落盘路径
  - 分析结果（AnalysisPackage，JSON）
- **价值**：后端重启、云实例休眠后数据不丢失；且可作为独立组件分发。

> ⚠️ **重要边界**：SQLite 是**文件级**数据库，不是网络服务。别人拿到后是**在自己的机器上用**（读文件），**不能跨网络远程连你的库**。若需"远程连数据库"，须换 Postgres/MySQL（本项目未采用）。

---

## 二、别人怎么用（本机使用，3 步）

### 方式 A：拿到整个项目（含代码）
1. 安装依赖：`pip install -r requirements.txt`
2. 初始化数据库：`python backend/init_db.py`（按 `schema.sql` 建表，幂等）
3. 启动后端，数据自动写入 `data/app.db`

### 方式 B：只拿到数据库文件（`app.db` + `schema.sql`）
别人已有自己的 DataMind 后端，只需：
1. 把 `app.db` 放到对方项目的 `data/` 目录下（或改对方 `.env` 的 `DB_PATH` 指向你的文件）。
2. 表结构以 `schema.sql` 为准；若对方库缺表，`backend/init_db.py` 会自动补齐。
3. 对方后端启动后即可直接读取你导出的数据。

### 直接查看数据（无需代码）
任何 SQLite 工具（DBeaver、DB Browser for SQLite、Navicat）或 Python 一行即可：
```python
import sqlite3, json
con = sqlite3.connect("data/app.db")
for row in con.execute("SELECT session_id, state_json FROM sessions"):
    print(row[0], json.loads(row[1]).keys())
```

---

## 三、表结构（schema.sql 定义）

| 表 | 主键 | 说明 | 主要字段 |
|---|---|---|---|
| `sessions` | session_id | 会话轻量状态（不含 DataFrame 本体） | `state_json`(JSON) / `created_at` / `last_access` |
| `datasets` | dataset_id | 数据集元信息 + 落盘路径 | `session_id`(FK) / `meta_json`(JSON) / `original_path` / `is_active` |
| `analysis_packages` | package_id | 分析结果完整 JSON | `session_id`(FK) / `dataset_id`(FK) / `payload_json`(JSON) / `saved_at` |

### state_json 内含（sessions 表）
`active_dataset_id` / `uploaded_bytes` / `dataset_packages` / `analysis_packages` / `saved_packages` / `api_key` / `custom_title` / `cleaning_history` / `analysis_history` / `saved_charts` / `df_undo_stack` 等。

### DataFrame 落盘说明
DataFrame 体积可能很大（本地支持 1GB），**不强行塞进 BLOB**，而是保留"落盘 pickle 文件"机制：
- 路径记录在 `datasets.original_path`（指向 `data/originals/*.pkl`）。
- 重启后 SessionManager 按该路径 `pd.read_pickle` 重新加载到内存。

---

## 四、三端解耦关系

```
前端  ──HTTP API──>  后端(FastAPI)
                         │
                         │ 统一数据访问层 backend/db/（crud.py + connection.py）
                         │
                         v
                    SQLite 文件 (data/app.db)
```

- **前端**：只认 API，完全不知道后端用内存还是数据库 → 存储层对前端透明，前端零改动。
- **后端**：所有数据库读写集中在 `backend/db/`，业务代码（SessionManager）不直接写 SQL → 将来换数据库只需改 `backend/db/`。
- **数据库**：路径配置化（`.env` 的 `DB_PATH`），换机器/换路径只改配置，不碰代码 → 支持分别部署。

---

## 五、迁移 / 升级表结构

- `schema.sql` 全部 `CREATE TABLE IF NOT EXISTS`，可重复执行，**不改已有数据**。
- 若未来需改字段，新增迁移脚本即可；当前版本无需。

---

## 六、注意事项（项目纪律）

- `data/` 已被根 `.gitignore` 忽略（仅保留 `data/.gitkeep`），数据库文件**不会进入 git/GitHub**（遵循 30MB 上传限制）。
- 分发 `.db` 文件请走网盘等带外渠道，不要提交到仓库。
- `.env` 含本地配置，同样 gitignore，分发时附 `.env.example` 即可。
