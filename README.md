# DataMind AI — 数据分析智能体

> 把一张原始表格，变成「可视化大屏 + 分析报告」的智能数据分析平台。
>
> 用户上传 Excel/CSV，平台自动清洗数据、AI 给解读、一键生成图表、拼成可投屏的大屏，最后还能导出一份能直接发的 HTML 分析报告。

---

## 一、核心能力

| # | 能力 | 说明 |
|---|------|------|
| 1 | **智能上传** | 拖入 CSV / Excel / JSON / SQLite，自动识别字段类型 |
| 2 | **数据清洗** | 补缺失值、揪异常值、去重 —— 可视化点选，不用写代码（AI 只出方案不动数据） |
| 3 | **AI 数据洞察** | 一键让 AI 读懂数据，输出「该分析什么」的建议 + 人话结论 |
| 4 | **智能分析出图** | 选个分析意图（趋势/排名/结构/地图/词云…），自动匹配算法出 ECharts 图表 |
| 5 | **可视化大屏** | 多套预设模板（指挥舱 / 网格 / 医疗看板 / 可视化看板…），图表按模板布局自动排布，可联动高亮、导出 HTML/PNG |
| 6 | **AI 分析报告 + 导出** | 一键生成管理层视角的 HTML 报告；大屏/报告可导出 HTML，大屏还可截 PNG |

---

## 二、技术栈

- **前端**：React 18 + TypeScript + Vite + Tailwind；图表用 **ECharts 6 + GL（3D 地图）+ wordcloud**
- **后端**：**FastAPI（Python）**，部署在 Render
- **AI**：**可插拔 LLM**（DeepSeek / 阿里百炼 / OpenAI，用户填 Key 即用）
- **存储**：**纯内存态，无数据库**（数据临时放内存，重启就清）
- **导出**：自研 HTML 生成引擎（大屏/报告）+ html2canvas（PNG）

---

## 三、目录结构

```text
数据分析项目/
├── backend/              # 后端 (FastAPI 入口 + 路由 + 会话管理)
│   ├── main.py           # 应用入口：CORS、注册 /api 路由、托管前端静态、健康检查
│   ├── routers/          # API 路由模块（upload/data/clean/chart/dashboard/insights/report/analysis…）
│   ├── services/         # 会话管理（内存单例：UUID、限流、DataFrame 备份、撤销栈）
│   └── requirements.txt  # 后端依赖
│
├── src/                  # 引擎层（核心分析逻辑，干活的工人）
│   ├── planner.py / data_loader.py / data_cleaner.py / column_classifier.py
│   ├── echart_generator.py   # ECharts 生成引擎（固定色板）
│   ├── ai_agent/             # LLM 推理（写文案的参谋）
│   ├── analysis_library/     # 分析知识库（YAML 注册中心，12 种分析类型）
│   ├── analysis_templates/   # 分析模板（计算→边界修复→Insight→Package）
│   ├── dashboard/            # 大屏布局引擎（蓝图/语义布局/交互）
│   └── reasoning/            # 业务推理管道（Rule → Evidence → LLM Reasoner）
│
├── frontend/             # 前端 (React + TypeScript + Vite + Tailwind + ECharts)
│   └── src/
│       ├── App.tsx           # 路由：/upload /clean /analysis /dashboard /ethereal-preview /reports …
│       ├── pages/            # 上传 / 清洗 / 分析 / 大屏 / 报告 等页面
│       ├── components/       # EChartView、大屏模板、DashboardRenderer（Schema 驱动引擎）
│       ├── layout/           # computeLayout 纯函数排版引擎
│       ├── theme/            # VDS 设计系统（色板 SSOT）
│       └── types/            # 类型定义（api.ts / dashboard.ts）
│
├── 可视化模板库/          # 大屏 HTML/JS 模板与配色素材
├── 知识库/                # Obsidian 知识库（架构讲解 + wikilink 索引）
├── 分析模型/              # 分析模型说明文档
├── 数据测试集/            # 示例 CSV 数据集
├── docs/                 # PRD / 架构文档
├── tests/               # 测试（py + json + ts）
├── config.py            # 全局配置（DeepSeek API、上传限制、图表配色）
└── 项目总结！！！.md       # 产品与流程设计总结
```

> 完整文件职责对照见 `知识库/代码文件总览.md` 与 `知识库/项目架构目录树.md`。

---

## 四、本地启动

### 1. 后端（端口 8001）

```bash
cd backend
pip install -r requirements.txt
python main.py
# 或：uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

需要 AI 功能时，在项目根目录创建 `.env` 并填入：

```env
DEEPSEEK_API_KEY=你的Key
# 可选：本地开发放开上传上限（默认 30MB，用于防 OOM）
# MAX_UPLOAD_SIZE_MB=5120
```

AI 不可用时，各功能自动走规则兜底，链路不会崩。

### 2. 前端（Vite dev server，默认 5173）

```bash
cd frontend
npm install
npm run dev
```

前端通过 Vite `/api` 代理把请求转发到后端 8001。生产构建用 `npm run build`，产物 `frontend/dist` 可由后端直接托管。

### 3. 访问

- 开发态：打开前端 dev server 地址（如 `http://localhost:5173`），封面页 `/` 进入各功能页
- 大屏页：`/dashboard`（多套模板切换 + AI 报告 + HTML 导出）
- 部署态：后端 `/` 直接返回前端 SPA（`/api/health` 健康检查）

---

## 五、设计原则（架构灵魂）

1. **AI 只动嘴，工人动手** —— LLM 只负责「写洞察、写报告、做轻量决策」，所有算数 / 匹配 / 画图都是确定性 Python 引擎，结果可复现。
2. **每个 AI 环节都有「没网也能跑」的兜底** —— AI 挂了，系统自动用规则顶上，整条链路不崩。
3. **故意不上数据库** —— 内存态 + 前端本地缓存副本，轻量、好部署、抗云服务的休眠重启。
4. **配色组件化、不随意改** —— 图表色板集中在 `frontend/src/theme/` 与 `src/echart_generator.py`，视觉风格（如大屏「仙气」配色）由组件层固化，排版/逻辑升级不得污染视觉。

### 智能大屏排版与 LLM 的关系（常被问到）

大屏排版**主体不依赖大模型**：

- **前端** `computeLayout()` 是一套纯函数规则引擎，按 12 列网格蓝图 + 三套模式把图表路由到固定槽位，**渲染链路上零 LLM 调用**。
- **后端** 仅有一处**可降级**的轻量 LLM 决策：读规则后输出 `slot_id + shape`（在固定蓝图槽位里做「选形状 + 挂槽」单选题）；LLM 不可达 / 解析失败时，自动回退为纯规则布局，大屏始终可渲染。

一句话概括：**「大屏排版由纯前端规则引擎驱动固定网格蓝图，大模型仅在后端做可降级的轻量挂槽决策，不进入前端渲染链路。」**

---

## 六、相关文档

- `知识库/项目架构产品视角.md` —— 一页看懂项目能干啥（给外人/简历用）
- `知识库/项目架构全景图.md` —— 技术视角系统三层架构图
- `知识库/README.md` —— 知识库索引（各概念笔记入口）
- `docs/DataMind_PRD框架.md` —— 产品需求框架
- `项目总结！！！.md` —— 数据上传 / 清洗 / 洞察 / 生图 全流程设计总结
