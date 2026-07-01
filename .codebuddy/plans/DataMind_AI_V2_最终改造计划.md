# DataMind AI V2 最终改造计划

> 合并来源：
> 1. 第一次 V2 计划（Phase 1-6：intent 枚举 / AI 输出 / 前端改造 / Feature Engine / 报告驱动 / Dashboard）
> 2. 第二次设计文档（分析可视化 + 仪表盘详细交互 + 统一协议 + 统一渲染）
> 3. 第三次深度分析方案（Analysis Library / 规则引擎 / 计算引擎 / 图表推荐器四层分离）

---

## 核心原则

> **程序负责确定性（Compute），AI负责不确定性（Think）。**

- **程序**负责所有可以写成规则的事：清洗、统计、特征工程、计算、图表渲染
- **AI**负责需要理解和判断的事：发现分析方向、提出业务问题、组织报告、输出洞察

---

## 改造范围

```
数据上传    →  不动
数据清洗    →  不动
分析可视化  →  ★ 重点修改
仪表盘      →  ★ 重点修改（指挥中心 / 数据看板 / 分析报告）
```

---

## 新架构：四层分离

```
AI 层         ← 只输出：业务问题（business_question）+ 分析目标（analysis_intent）
    │
    ▼
规则引擎层     ← 固定配置表：一个 intent 需要哪些计算步骤
    │            （例如 "ranking" → groupby → sort → topN）
    │
    ▼
计算引擎层     ← 固定模板：执行 groupby / 同比 / 环比 / 占比 / ABC / RFM / Pareto
    │
    ▼
图表推荐器层   ← 固定规则：根据 intent + 数据特征决定 chart_type
    │            （例如 intent=trend + 有时间列 → line；没有 → area）
    │
    ▼
统一渲染层     ← VisualizationItem：chart → ECharts | table → TableRenderer
```

**核心转变**：AI 不再说"画什么图"，而是说"回答什么业务问题"。
后端的规则引擎、计算引擎、图表推荐器各自完成自己的工作。

---

## Phase 0：Analysis Library 配置表（新增）

**目标**：建立全系统唯一的 intent → compute → chart 配置表。

### 新建文件
`src/analysis_library.py`

### 配置表结构
```python
ANALYSIS_LIBRARY = {
    "trend":          {"compute_rules": ["time_group"],        "chart_type": "line",       "table_type": "sort"},
    "ranking":        {"compute_rules": ["groupby", "sort"],   "chart_type": "bar",        "table_type": "sort"},
    "proportion":     {"compute_rules": ["groupby", "percent"],"chart_type": "pie",        "table_type": "summary"},
    "distribution":   {"compute_rules": ["histogram"],         "chart_type": "histogram",  "table_type": None},
    "correlation":    {"compute_rules": ["scatter"],           "chart_type": "scatter",    "table_type": "correlation"},
    "growth":         {"compute_rules": ["yoy"],               "chart_type": "line",       "table_type": "sort"},
    "composition":    {"compute_rules": ["groupby", "stack"],  "chart_type": "stacked_bar","table_type": "cross"},
    "concentration":  {"compute_rules": ["pareto_compute"],    "chart_type": "pareto",     "table_type": "sort"},
    "geo":            {"compute_rules": ["groupby", "sum"],    "chart_type": "map_3d",     "table_type": "summary"},
    "abc":            {"compute_rules": ["abc_compute"],       "chart_type": "abc",        "table_type": "sort"},
    "funnel":         {"compute_rules": ["funnel_compute"],    "chart_type": "funnel",     "table_type": "sort"},
    "overview":       {"compute_rules": [],                    "chart_type": None,         "table_type": None},
    "anomaly":        {"compute_rules": ["anomaly_detect"],    "chart_type": "box",        "table_type": None},
}
```

### 各模块引用此表
- `prompts.py`：AI System Prompt 引用 intent 枚举
- `report_analyzer.py`：Chart Planner 引用映射
- `AnalysisPage.tsx`：前端根据 intent 决定 UI
- `dashboard.py`：Tab 分类引用 intent

---

## Phase 1：AI 洞察输出改造（修改）

**目标**：AI 同时输出 Markdown（给人）+ 结构化 Execution Plan JSON（给程序），不再需要前端正则解析。

### 修改文件
- `src/ai_agent/prompts.py`：`INSIGHTS_SYSTEM_PROMPT` 新增要求

### AI 输出格式变更

**旧格式**（纯 Markdown）：
```markdown
## 分析建议
1. 绘制柱状图（X:地区, Y:销售额）
```

**新格式**（Markdown + JSON）：
```json
{
  "insights": "## 数据概览\n...\n## 分析建议\n...",
  "plans": [
    {
      "business_question": "华东地区销售额最高，各区域差距有多大？",
      "intent": "ranking",
      "metric": "销售额",
      "dimension": "地区",
      "operation": "sum"
    },
    {
      "business_question": "各区域销售额占比如何？",
      "intent": "proportion",
      "metric": "销售额",
      "dimension": "地区",
      "operation": "percent"
    }
  ]
}
```

### Plan 字段定义
| 字段 | 类型 | 说明 | 旧计划 |
|------|------|------|--------|
| `business_question` | string | 人类可读的业务问题 | **新增** |
| `intent` | string | 分析目标（trend/ranking/proportion…） | 保留 |
| `metric` | string | 数值列名 | 保留 |
| `dimension` | string | 分类/时间列名 | 保留 |
| `operation` | string | 计算方式（sum/percent/yoy/mom…） | 保留 |

### 后端修改
- `backend/routers/insights.py`：API 返回从 `{insights: string}` 变为 `{insights: string, plans: [...]}`
- AI 输出 Markdown + JSON 两块，用 `---PLANS---` 分隔符

---

## Phase 2：前端消费改造（删除 + 新增）

**目标**：`handleApplyInsights` 不再用正则/关键词，直接读取 `plans[]`。

### 删除内容
- `AnalysisPage.tsx`：`CHART_KEYWORD_MAP`（约第 401-417 行）
- `AnalysisPage.tsx`：`COMPUTE_KEYWORDS`（约第 420 行）
- `AnalysisPage.tsx`：`handleApplyInsights` 中正则解析整段（约第 398-531 行）

### 新流程（3 步）
```
Step 1：读取 plans[] → 生成 validSuggestions[]
         intent="overview" → 跳过
         其他 intent → 从 Analysis Library 查 chart_type + table_type
         operation 不为 null → needCompute = true

Step 2：对 needCompute=true → 调用 Compute Engine
         同环比 → 专用接口保留

Step 3：验证列名 → 调用 /chart/echart-create 生图 → 跳转 charts Tab
```

### 1 个问题 → 多张图的实现
- **第一步**：AI 的 plans[] 已经是扁平列表，但用户可以自由选择哪些 plan 执行
- **第二步**（后续迭代）：plans[] 加 `parent_question_id`，同一条 business_question 下多个 plan 自动勾选

---

## Phase 3：Compute Engine（替代 AI 写 Python）

**目标**：AI 只选模板名，程序执行固定代码，不再 `exec()` AI 生成的 Python。

### 新建文件
```
src/compute_engine/
    __init__.py
    groupby_builder.py    # groupby + agg（sum/mean/count/max/min）
    pivot_builder.py      # 透视表
    percent_builder.py    # 各类占比、百分比
    yoy_builder.py        # 同比计算
    mom_builder.py        # 环比计算
    rank_builder.py       # 排序 + TOP N
    rolling_builder.py    # 移动平均/累计
    abc_builder.py        # ABC 分类（累计贡献率 80%/15%/5%）
    pareto_builder.py     # 帕累托分析
    standardize_builder.py# 标准化/归一化
    correlation_builder.py# 相关系数
    anomaly_builder.py    # Z-score / IQR 异常检测
    funnel_builder.py     # 漏斗计算
    factory.py            # ComputeFactory: intent → builder → execute
```

### 每个 Builder 接口
```python
class GroupByBuilder:
    def execute(self, df, metric, dimension, aggregate="sum") -> pd.DataFrame:
        # 返回 df（新增计算列或聚合结果）
        ...

class ComputeFactory:
    def execute_plan(self, df, plan: dict) -> (pd.DataFrame, list):
        # plan = {intent, metric, dimension, operation}
        # 从 Analysis Library 查 compute_rules
        # 逐个调用对应 builder
        # 返回 (更新后的 df, 新增列名列表)
```

### 新 API 端点
- `POST /feature/compute`
- 请求：`{session_id, plans: [{intent, metric, dimension, operation}]}`
- 后端：ComputeFactory 逐个执行 → 返回结果

### 保留兼容
- `POST /data/compute` 保留但标记 deprecated
- `POST /data/tonghuanbi` 同环比专用保留

---

## Phase 4：统一数据结构（ChartMeta + AnalysisResult）

**目标**：全系统共享数据结构，分析可视化 → 保存 → 仪表盘 → 报告 都用同一份。

### ChartMeta
```python
@dataclass
class ChartMeta:
    id: str               # 唯一标识
    title: str            # 图表标题
    analysis_type: str    # trend / ranking / proportion / ...
    chart_type: str       # line / bar / pie / map_3d / ...
    x: str                # X 轴列名
    y: str                # Y 轴列名
    option: dict          # ECharts option
    table_data: list      # 表格数据 [{columns, rows}]
    compute_info: dict    # 计算过程记录
    insight: str          # AI 洞察文字
    created_at: str       # 创建时间
```

### AnalysisResult（后端统一返回格式）
```json
{
  "insights": "Markdown 文本",
  "plans": [
    {
      "business_question": "...",
      "intent": "trend",
      "metric": "销售额",
      "dimension": "日期",
      "operation": null
    }
  ],
  "charts": [ ChartMeta, ... ],
  "tables": [ TableMeta, ... ]
}
```

### 修改文件
- `backend/routers/insights.py`：返回 AnalysisResult
- `frontend/src/types/api.ts`：新增对应 TypeScript 类型
- 保存图表逻辑：从只保存 option → 保存完整 ChartMeta

---

## Phase 5：统一可视化渲染（新增）

**目标**：AI 返回表格时也能直接显示，不再只支持 ECharts。

### 新增类型
```typescript
type VisualizationItem = {
  id: string;
  type: "chart" | "table";
  chart?: EChartOption;
  table?: TableData;
  analysis_type: string;
  title: string;
};
```

### 渲染分发
- `type == "chart"` → `<EChartsRenderer />`
- `type == "table"` → `<TableRenderer />`

### 修改文件
- `frontend/src/components/VisualizationRenderer.tsx`（新建）
- `AnalysisPage.tsx`：图表 Tab 渲染改为遍历 VisualizationItem[]

---

## Phase 6：分析可视化 Tab 改造

### 6.1 智能绘图 Tab 重设计

**当前**：左（AI 计算）+ 右（图表）

**V2**：三栏布局
```
┌────────────┬──────────────────┬─────────────┐
│ 执行计划    │ 生成结果（表格）   │ 图表        │
│            │                  │             │
│ ✓ groupby  │ 地区  │ 销售额   │  [ECharts]  │
│ ✓ 排序     │ 华东  │ 5000    │             │
│ ✓ TOP5     │ 华南  │ 4000    │             │
│ ✓ 新增列   │ ...   │ ...     │             │
│            │                  │             │
│            │ [查看] [下载]    │             │
└────────────┴──────────────────┴─────────────┘
```

- **左栏**：展示 AI 执行的每个计算步骤（来自 `compute_info`）
- **中栏**：展示计算结果表格（来自 ChartMeta.table_data）
- **右栏**：ECharts 图表（来自 ChartMeta.option）

---

## Phase 7：仪表盘改造

### 7.1 指挥中心（command 模板）

**V2 六宫格布局**：
```
┌──────────────┬──────────────────────┬──────────────┐
│ KPI 卡片      │ 全国地图（GLMap）     │ AI摘要        │
│              │                      │ （纯文字卡片）  │
├──────────────┼──────────────────────┼──────────────┤
│ TOP5 柱状图   │ 异常预警              │ 最新洞察      │
│ （来自保存图表）│ （纯文字卡片）         │ （纯文字卡片）  │
└──────────────┴──────────────────────┴──────────────┘
```

**改动点**：
- 右上：原数据预览 → **AI摘要**（从 insights 提取核心发现）
- 中下：**异常预警**（从 anomaly intent 的 compute 结果提取）
- 右下：**最新洞察**（最新的 2-3 条洞察建议）
- 左下：原本地计算排行 → 改为来自**用户保存的图表**

### 7.2 数据看板（medical 模板）—— 最大改动

**删除**：
- 三个雷达图（`computeRadarFromData`）
- 三个环形图（Tab 0 右侧）
- 趋势总览（Tab 0 左上单图）
- 4 Tab 导航栏

**V2 固定布局**：
```
┌──────────────────────────────────────────────────┐
│ KPI 数字卡（保留）                                  │
├───────────────┬──────────────────────────────────┤
│ AI摘要         │ 主分析图 ①（来自用户保存的 ChartMeta） │
│ （纯文字）     │（折线 / 柱状 / 地图 / 饼图…）         │
├───────────────┼──────────────────────────────────┤
│ 数据预览       │ 第二分析图 ②                        │
│ （前10行表格）  │                                   │
├───────────────┼──────────────────────────────────┤
│ TOP 排行       │ 第三分析图 ③                        │
│ （柱状图）     │                                   │
└───────────────┴──────────────────────────────────┘
```

**核心原则**：
- 右边三张图**完全不自动生成**，全部从用户保存的 ChartMeta 读取
- 按 `analysis_type` 排列：trend → ranking → proportion / geo / composition...
- 不足 3 张时，有几张显示几张，不自动补雷达图
- 删掉 `MedicalDashboard.tsx` 的 `computeRadarFromData` 和 `computeRingChartsFromData`

### 7.3 分析报告（report 模板）

**删除**：
- 保底三张图（`report_analyzer.py` `plan_charts()` 阶段 A）
- `chartIndex` 硬匹配逻辑

**V2 流程**：
```
报告生成时：
  Section.type（如 "trend"）
      │
      ▼
  从 Analysis Library 查 chart_type → 从用户保存的 ChartMeta 找匹配
      │
      ├── 有匹配 → 正常渲染
      └── 无匹配 → AI 换角度重写该 Section，不输出空白
```

**Prompt 修改**：
- `REPORT_SYSTEM_PROMPT` 新增规则：如果某 Section 没有对应图表，换个分析角度写内容，禁止输出空白

### 7.4 报告渲染改造

**前端 `exportEChartsDashboard.ts`**：
- `buildReportHTML()` 不再用 `section.type` 去猜 `chartIndex`
- Section 新增 `chart_required: bool`，无图时 `chart_required=false`，chartDiv 为空
- 无图 Section 自然收缩，不预留空占位（保留记忆 23531787 规则）
- 图表容器高度保持 420px（保留记忆 66018955 规则）

---

## Phase 8：图表推荐器（新增模块）

**目标**：不只 1:1 硬映射，根据数据特征动态决策 chart_type。

### 新建文件
`src/chart_recommender.py`

### 推荐逻辑
```python
def recommend(intent: str, df: pd.DataFrame, dimension: str) -> str:
    """
    根据 intent + 数据特征决定最终 chart_type
    """
    if intent == "trend":
        # 有时间列 → line；没有 → area；只有1个分类值 → bar
        if has_time_column(df, dimension):
            return "line"
        return "area"

    if intent == "geo":
        # 有省/市列 → map_3d；否则降级为 bar
        if is_geo_column(dimension):
            return "map_3d"
        return "bar"

    # 其他 intent 直接从 Analysis Library 读取默认值
    return ANALYSIS_LIBRARY[intent]["chart_type"]
```

### 与 Analysis Library 的关系
- Analysis Library 存**静态默认映射**
- Chart Recommender 做**运行时动态决策**（数据特征影响最终选择）

---

## 删除清单

| # | 删除目标 | 文件 | 替换为 |
|---|---------|------|--------|
| 1 | `CHART_KEYWORD_MAP` | AnalysisPage.tsx | Analysis Library + plans[].intent |
| 2 | `COMPUTE_KEYWORDS` | AnalysisPage.tsx | plans[].operation |
| 3 | AI 生成 Python（`exec()`） | data.py | Compute Engine |
| 4 | 保底三张图 | report_analyzer.py | ChartMeta 驱动 |
| 5 | 前端正则解析 | AnalysisPage.tsx | 直接读 plans[] |
| 6 | `computeRadarFromData` | MedicalDashboard.tsx | 来自用户保存的图表 |
| 7 | `computeRingChartsFromData` | MedicalDashboard.tsx | 来自用户保存的图表 |
| 8 | 4 Tab 导航栏 | MedicalDashboard.tsx | 固定单页布局 |
| 9 | `chartIndex` 硬匹配 | exportEChartsDashboard.ts | Section.chart_required 驱动 |

---

## 最终数据流

```
数据清洗
    │
    ▼
AI 数据洞察（输出 Markdown + plans[]）
    │
    ▼
┌─── plans[].business_question ──→ 展示给用户（"AI 想回答什么问题"）
│
├─── plans[].intent ──→ 规则引擎（Analysis Library 查 compute_rules + chart_type）
│         │
│         ▼
│   计算引擎（ComputeFactory 按模板计算）
│         │
│         ▼
│   新 DataFrame
│         │
│         ▼
│   ChartMeta + TableMeta（统一数据结构）
│         │
│         ├──→ chart → 图表推荐器（动态调整 chart_type）
│         │         │
│         │         ▼
│         │   ECharts Generator
│         │
│         └──→ table → TableRenderer
│
▼
分析可视化（用户预览 + 保存选定图表）
    │
    ▼
图表仓库（ChartMeta[] + TableMeta[]）
    │
    ├────────────┬──────────────┐
    ▼            ▼              ▼
数据看板      分析报告        指挥中心
（固定布局）（Section → Intent）（六宫格布局）
```

---

## 执行顺序

```
Phase 0（Analysis Library）
      │
      ├──→ Phase 1（AI 输出改造）
      │        │
      │        ▼
      │    Phase 2（前端消费 Plan）
      │        │
      │        ▼
      │    Phase 3（Compute Engine）
      │
      ├──→ Phase 4（统一数据结构）
      │
      ├──→ Phase 5（统一可视化渲染）
      │
      ├──→ Phase 6（分析可视化 Tab 改造）
      │
      ├──→ Phase 7（仪表盘改造）
      │        ├── 7.1 指挥中心
      │        ├── 7.2 数据看板
      │        └── 7.3 分析报告
      │
      └──→ Phase 8（图表推荐器，可并行）
```

- Phase 0 是基础，所有后续 Phase 都依赖它
- Phase 1-3 是连续链（AI → 前端 → 计算引擎）
- Phase 4-5 可并行 Phase 1-3
- Phase 6-7 依赖 Phase 4-5
- Phase 8 可在 Phase 5 之后随时插入

---

## 对比旧计划的关键变更

| 变更项 | 旧计划 | 新计划 |
|--------|--------|--------|
| 配置层 | Phase 1 `intent_chart_map.py` | Phase 0 `analysis_library.py`（增加 compute_rules） |
| AI 输出 | plans 无 `business_question` | plans 新增 `business_question` |
| 规则引擎 | 无独立层 | 直接在 Analysis Library 表中声明 |
| 1 问题 → N 图 | 未提及 | 通过 plans[] 多条目支持，后续加 parent_question_id |
| 图表推荐器 | 无 | Phase 8 新增，运行时动态决策 |
| 统一渲染 | Phase 独立 | Phase 5，保留 |
| 智能绘图 Tab | 未提及 | Phase 6.1 三栏布局 |
| 指挥中心 | 未提及 | Phase 7.1 六宫格 |
| 数据看板 | Phase 6 洞察卡片 | Phase 7.2 完全重设计（固定布局） |
| 分析报告 | Phase 5 report 驱动 | Phase 7.3 增强（ChartMeta 驱动 + AI 换角度） |
| Compute Engine | Phase 4 Feature Engine | Phase 3 Compute Engine（新增 ABC/RFM/Pareto/Funnel 计算） |
