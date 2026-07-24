---
title: 后端/前端/src 三层职责分工
aliases: [三层分工, 前后端分工, backend frontend src, 三层架构角色]
tags: [架构, 后端, 前端, 引擎]
created: 2026-07-21
---

# 后端 / 前端 / src 三层职责分工

> 一句话：backend=**接口壳子**（前台接待员），frontend=**页面与组件**（店面装潢陈设），src=**真正干活的内核**（后厨）。三者通过 HTTP 接口 + 全局状态连接。逐文件清单见 [[代码文件总览]]，技术三维分层图见 [[项目架构全景图]]。

---

## 一、backend/ —— API 接口层（壳子）

后端不是"业务逻辑所在地"，而是**暴露给前端的 HTTP 接口层**。目录里基本是"薄路由"——拿到参数，调 `src/` 函数干活，返回 JSON。

```
backend/
├── main.py                 ← FastAPI 启动入口：挂载 10 个 /api 路由、CORS、静态托管
├── requirements.txt        ← Python 依赖清单
├── runtime.txt             ← Python 版本声明
├── Procfile                ← 部署配置
├── routers/                ← API 接口（共 10+ 个 .py）
│   ├── upload.py           ← 上传接口
│   ├── data.py             ← 获取数据
│   ├── analysis.py         ← 执行分析接口（调 src/planner、src/模板）
│   ├── chart.py            ← 生成图表接口（调 src/echart_generator）
│   ├── stats.py            ← 统计摘要接口
│   ├── insights.py         ← AI 洞察接口（调 src/ai_agent）
│   ├── dashboard.py        ← 仪表盘接口（调 src/dashboard）
│   ├── report.py           ← AI 报告接口（调 src/report_analyzer）
│   ├── reasoning.py        ← 深度推理接口
│   ├── clean.py            ← 数据清洗接口（调 src/data_cleaner）
│   └── __init__.py
├── services/
│   └── session_manager.py  ← 会话管理（内存单例，跨请求保持 DataFrame）
└── utils/
    └── ai_error.py         ← AI 错误处理
```

接口函数本体（以 `analysis.py` 为例）全是"调 src/ + 组装 JSON"：

```python
# backend/routers/analysis.py（示意）
from src.planner import Planner
from src.chart_renderer import ChartRenderer

@router.post("/analysis")
def run_analysis(data: AnalysisRequest):
    plan = _PLANNER.plan(intent, df)                  # ← 调 src/planner
    result = _execute_with_fallback(exec_df, ...)      # ← 调模板
    result.charts = _RENDERER.render_all(...)          # ← 调 src/chart_renderer
    return {"packages": sanitize_json(packages)}       # ← 调 src/utils
```

**backend/ 一共就 18 个非空文件**：11 个路由接口 + 1 会话管理 + 1 错误处理 + 4 入口/配置。**没有数据库、没有模型、没有模板引擎、没有缓存层。**

---

## 二、frontend/ —— 页面与组件层（陈设）

前端放的是**页面组件、UI 渲染、状态管理、工具函数**，跟"接口代码"完全不沾边。真正发请求的地方是 `frontend/src/api/`。

```
frontend/
├── index.html               ← 入口 HTML
├── main.tsx                 ← React 启动入口
├── App.tsx                  ← 根组件（路由分发）
├── pages/                   ← 页面级组件（路由对应整页）
│   ├── DashboardPage.tsx    ← 仪表盘页面
│   ├── AnalysisPage.tsx     ← 分析页面
│   └── ...
├── components/              ← 可复用 UI 组件
│   ├── EChartView.tsx       ← ECharts 图表渲染器（把 option 变图表）
│   ├── KPIWidget.tsx        ← KPI 卡片组件
│   ├── EGridLayout.tsx      ← 网格布局
│   ├── MedicalDashboard.tsx ← 医疗仪表板
│   └── ...（共 34 个 .tsx/.ts）
├── contexts/                ← React Context（全局状态）
├── api/                     ← 前端调后端的请求封装（真正发 fetch 的地方）
├── utils/                   ← 工具函数（导出 HTML 等）
├── theme/                   ← 主题系统（颜色/字体/暗色）
├── types/                   ← TypeScript 类型定义
├── dist/                    ← 构建产物
└── public/                  ← 静态资源（图片、GeoJSON）
```

前端通过 `fetch('/api/analysis/run')` 调 backend，拿到数据渲染到 `EChartView.tsx`。

---

## 三、src/ —— 核心逻辑层（内核）

`src/` 是**真正干活的地方**：贴标签、选列、算 KPI、出 ECharts option、调 LLM……全在这里。按功能分子目录：

```
src/
├── column_classifier.py     ← 贴四类标签（时间/指标/维度/其他）
├── planner.py               ← 意图 → 选列/选模板（语义词典匹配）
├── echart_generator.py      ← 出折线图/散点图/饼图/地图… option
├── chart_renderer.py        ← chart_data → ChartItem + ECharts option
├── data_loader.py / data_cleaner.py / stats_analyzer.py
├── report_analyzer.py / report_builder.py / dashboard_builder.py
├── card_generator.py / kpi_renderer.py / table_renderer.py / insight_renderer.py
├── ai_agent/                ← LLM 智能体（洞察/报告/意图）
├── analysis_library/        ← 12 个 .yaml 分析定义 + 注册/匹配逻辑
├── analysis_templates/      ← 各分析模板 .py（ranking/structure/geo…）
├── calculators/             ← 计算引擎
├── dashboard/               ← 大屏布局引擎
├── domain/ / reasoning/ / report/ / utils/
```

---

## 四、三层对照表

| 目录 | 放的什么 | 类比 | 改功能动哪些文件 |
|---|---|---|---|
| `backend/` | API 接口代码 | 前台接待员 | `routers/*.py` |
| `frontend/` | 页面、组件、样式、交互 | 店面装潢/陈设 | `components/*.tsx`、`pages/*.tsx` |
| `src/` | 真正干活的算法/计算/生成逻辑 | 后厨——所有菜在这炒 | `column_classifier.py`、`echart_generator.py`、`analysis_templates/*` |

**常见误区**：以为"后端贴标签/后端生图"在 `backend/` 里——其实全在 `src/` 里。`backend/` 只是"前端敲门的地方"，转手叫 `src/` 干活。

---

## 五、完整数据流

```
用户上传 CSV
  → frontend 调 backend/routers/upload.py
  → backend 调 src/data_loader.py 读数据
  → src/column_classifier.py 贴标签
  → 前端展示，用户点"分析"
  → backend/routers/analysis.py 调 src/planner.py
  → src/planner.py 选列/选模板 → src/analysis_templates/ 算 → src/echart_generator.py 出图
  → 返回 JSON → frontend EChartView.tsx 渲染
```

---

## 六、关联概念

- `other` 桶（ID 列）被彻底排除分析——见四类标签机制（[[代码文件总览]] 的 `column_classifier` 条目）
- 列名子串匹配（`SEMANTIC_ENTITIES`）让 `a销售金额` 也能对上——见 [[数据洞察分析后端全链路]]
- 详细 168 文件逐条职责见 [[代码文件总览]]；技术三维分层见 [[项目架构全景图]]、[[项目架构产品视角]]

---

> 相关笔记：[[代码文件总览]]、[[项目架构全景图]]、[[项目架构产品视角]]、[[后端技术栈]]、[[前端技术栈]]、[[数据洞察分析后端全链路]]
