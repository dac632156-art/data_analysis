# AI 数据分析 Agent V2 改造计划

## 核心原则

> **程序负责确定性（Compute），AI负责不确定性（Think）。**

---

## Phase 1: Analysis Intent 枚举设计 + 统一映射表

**目标**：建立一个全系统共享的 Intent 定义层，前端/后端/AI Prompt 都引用同一份映射。

### 新建文件
- `src/intent_chart_map.py` — Intent 枚举 + Intent → Chart/Table 映射

### Intent 枚举
```python
class AnalysisIntent:
    TREND = "trend"           # 趋势分析 → line 折线图
    RANK = "rank"             # 排名/对比 → bar 柱状图
    SHARE = "share"           # 占比/比例 → pie 饼图
    GEO = "geo"               # 地理分布 → map_3d 3D地图
    DISTRIBUTION = "distribution"  # 分布 → histogram 直方图
    CORRELATION = "correlation"    # 相关性 → scatter 散点图
    COMPOSITION = "composition"     # 交叉构成 → stacked_bar 堆叠
    ANOMALY = "anomaly"       # 异常检测 → box 箱线图 / hover text
    OVERVIEW = "overview"     # 概览 → 无图
```

### Intent → Chart 映射
```python
INTENT_CHART_MAP = {
    "trend":       {"chart_type": "line",    "table_type": "sort"},
    "rank":        {"chart_type": "bar",     "table_type": "sort"},
    "share":       {"chart_type": "pie",     "table_type": "summary"},
    "geo":         {"chart_type": "map_3d",  "table_type": "summary"},
    "distribution":{"chart_type": "histogram", "table_type": None},
    "correlation": {"chart_type": "scatter", "table_type": "correlation"},
    "composition": {"chart_type": "stacked_bar", "table_type": "cross"},
    "anomaly":     {"chart_type": "box",     "table_type": None},
    "overview":    {"chart_type": None,      "table_type": None},
}
```

### 关联修改
- `prompts.py` INSIGHTS_SYSTEM_PROMPT：引用统一枚举
- `prompts.py` REPORT_SYSTEM_PROMPT：引用统一枚举
- `report_analyzer.py` plan_charts()：引用统一映射表
- `AnalysisPage.tsx`：删除 CHART_KEYWORD_MAP，改为读取后端 Intent
- `dashboard.py` _CHART_TAB_MAP：改为按 Intent 分类

---

## Phase 2: AI Insights 输出新增 Analysis Plan (JSON)

**目标**：AI 同时输出 Markdown（给人看）和结构化 Analysis Plan（给程序），不再需要正则解析。

### 后端修改
- `INSIGHTS_SYSTEM_PROMPT`（prompts.py 第 54-65 行）：新增必须输出 JSON plans 的要求
- `INSIGHTS_USER_PROMPT_TEMPLATE`（prompts.py 第 67-103 行）：新增 plans 示例格式
- API 返回格式从 `{insights: string}` 改为 `{insights: string, plans: [...]}`

### 新增返回格式
```json
{
    "insights": "## 数据概览\n...\n## 分析建议\n...",
    "plans": [
        {
            "intent": "trend",
            "metric": "销售额",
            "dimension": "日期",
            "operation": null,
            "description": "销售额随时间趋势分析"
        },
        {
            "intent": "share",
            "metric": "销售额",
            "dimension": "产品类别",
            "operation": "占比",
            "description": "各产品类别销售额占比"
        }
    ]
}
```

### Plan 字段定义
```python
{
    "intent": "trend|rank|share|geo|distribution|correlation|composition|anomaly|overview",
    "metric": "数值列名",
    "dimension": "分类列名或时间列名",
    "operation": "同比|环比|占比|排名|累计|移动平均|null",
    "description": "人类可读的一句话描述"
}
```

### 后端处理
- `backend/routers/insights.py`：api_generate_insights() 新增解析 plans 字段
- AI 输出先用 Markdown + JSON 两块，中间用 `---PLANS---` 分隔符，代码分别提取

---

## Phase 3: 前端删除 Keyword 解析，改为直接消费 Analysis Plan

**目标**：`handleApplyInsights` 不再用正则、关键词映射，直接读取 `plans[]` 驱动计算和生图。

### 删除内容
- `AnalysisPage.tsx`：`CHART_KEYWORD_MAP`（第 401-417 行）
- `AnalysisPage.tsx`：`COMPUTE_KEYWORDS`（第 420 行）
- `AnalysisPage.tsx`：`handleApplyInsights` 中 Step 1 的整段正则解析逻辑（第 398-531 行）

### 新流程（handleApplyInsights 改为 3 步）
```
Step 1: 读取 plans[] → 生成 validSuggestions[]
         intent "overview" → 跳过
         intent "trend"/"rank"/"share"/"geo"/... → 从 intent_chart_map 查 chart_type + table_type
         operation 不为 null → needCompute = true

Step 2: 对 needCompute=true 的 → 调用 Feature Engine（不再调用 AI compute）
         同环比 → 专用接口 /data/tonghuanbi

Step 3: 验证列名 → 调用 /chart/echart-create 生图 → 跳转 charts Tab
```

### 新增 API 调用
- `POST /feature/compute`（Phase 4 建立）替代 `POST /data/compute`
- 请求：`{session_id, plan: {intent, metric, dimension, operation}}`
- 返回：`{new_columns, message}`

---

## Phase 4: 新建 Feature Engine 替代 AI 写 Python

**目标**：AI 不再生成 Python 代码，只指定 operation，程序执行确定性的数据计算。

### 新建目录
```
src/feature_engine/
    __init__.py
    trend_builder.py     # 趋势计算：同比、环比、移动平均
    top_builder.py       # 排名计算：排序、TOP N、rank
    share_builder.py     # 占比计算：各类占比、百分比
    map_builder.py       # 地理计算：地区汇总
    anomaly_builder.py   # 异常计算：Z-score、IQR
    histogram_builder.py # 分布计算：分箱
    factory.py           # FeatureFactory: intent → builder + execute
```

### 每个 Builder 接口
```python
class TrendBuilder:
    def execute(self, df, metric, dimension, operation="同比") -> pd.DataFrame:
        # 返回 df（新增计算列）
        ...

class FeatureFactory:
    def execute_operation(self, df, intent, metric, dimension, operation=None) -> (pd.DataFrame, list):
        # 根据 intent 找到对应 builder，执行 operation
        # 返回 (更新后的 df, 新增列名列表)
```

### 新 API 端点
- `POST /feature/compute`
- 请求：`{session_id, plans: [{intent, metric, dimension, operation}]}`
- 后端：FeatureFactory 逐个执行 → 更新 session df → 返回结果

### 保留兼容
- `POST /data/compute` 暂时保留但标记 deprecated
- 同环比专用接口 `POST /data/tonghuanbi` 保留

---

## Phase 5: 报告流程改造 — Report 驱动 Chart Planner

**目标**：AI 输出的报告 Section 是唯一事实来源，Chart Planner 根据 Section 自动生成图表，不再先规划图再写报告。

### 改造前（当前）
```
pandas 规划图 → 生成图 → AI 写报告（图先于报告）
```
### 改造后（目标）
```
pandas 统计 → AI 写报告 → Chart Planner 读取 sections → 生成图（报告先于图）
```

### 修改文件
- `report_analyzer.py`：`plan_charts()` 不再在阶段2执行，移到阶段5之后
- `src/ai_agent/agent.py`：`generate_report()` 流程调整为：
  ```
  阶段1: 字段识别
  阶段2: 统计分析（原阶段3，去掉图表规划）
  阶段3: AI 生成报告 JSON（原阶段4-5）
  阶段4: Chart Planner 根据 sections 生成图表 ← 新增
  ```

### Chart Planner 输入
```json
// AI 报告中的 section
{
    "type": "trend",
    "title": "趋势分析",
    "enable": true,
    "chart_required": true,
    "metric": "销售额",
    "dimension": "日期"
}
```

### Chart Planner 输出
```json
{
    "type": "line",
    "x": "日期",
    "y": "销售额",
    "title": "销售额趋势分析",
    "analysis_type": "trend"
}
```

### Section 结构新增字段
```python
{
    "type": "trend",
    "enable": True,           # 该 section 是否生效（AI 可设为 false 跳过）
    "chart_required": True,   # 前端根据此字段渲染图表容器
    "metric": "销售额",       # 关联的数值列
    "dimension": "日期",      # 关联的维度列
}
```

### 前端修改
- `exportEChartsDashboard.ts`：`buildReportHTML()` 不再用 section.type 去猜 chartIndex
- 改为：section 自带 `chart_required` + ReportSection 新增 `chartIndex` 由 Chart Planner 填入
- 无图 section 的 `chart_required=false`，chartDiv 为空

---

## Phase 6: Dashboard 重构 — 洞察卡片替代重复雷达图

**目标**：数据看板（medical 模板）的三个重复雷达图替换为有意义的 AI 洞察卡片。

### 修改文件
- `MedicalDashboard.tsx`：`TabOverview` 中多维对比区域
- `ComputeRadarFromData` 删除或保留但不再默认渲染

### 新增组件
- 不在数据总览 Tab 渲染 3 个雷达图
- 改为渲染 **AI 洞察卡片**（从 insights/plans 中提取）：
  - 关键发现卡片（2-3 条 top-line insights）
  - 趋势信号卡片（上升/下降指示）
  - 风险预警卡片（异常指标）

### Dashboard 职责纯化
- Dashboard **只负责展示**，不参与任何 AI 计算或数据计算
- 数据来源来源：已保存图表（analysis page save） + KPI 接口
- 洞察卡片数据来源：缓存的分析报告 Plan/Insights

---

## 删除清单（逐步执行）

| 序号 | 删除目标 | 所在文件 | 替换为 |
|------|---------|---------|--------|
| ① | `CHART_KEYWORD_MAP` | AnalysisPage.tsx:401-417 | intent_chart_map.py |
| ② | `COMPUTE_KEYWORDS` | AnalysisPage.tsx:420 | plans[].operation |
| ③ | AI 生成 Python 代码 | data.py compute 端点 | Feature Engine |
| ④ | 保底三张图 | report_analyzer.py plan_charts A1-A3 | Chart Planner 读 sections |
| ⑤ | `getEChartsAiLayout` | client.ts（已删除） | — |
| ⑥ | 前端 regex 解析逻辑 | AnalysisPage.tsx:377-531 | 直接读 plans[] |

---

## 执行顺序（共 6 个 Phase）

```
Phase 1 ────┐
            ├──→ Phase 2 ──→ Phase 3 ──→ Phase 4
            │                              │
            └──────────────────────────────┤
                                           │
                                    Phase 5 ──→ Phase 6
```

- **Phase 1**（Intent 枚举）是整个改造的基础，所有后续模块都引用它
- **Phase 2-4**（AI 输出 Plan → 前端消费 → Feature Engine）是一条连续的链，必须按序
- **Phase 5**（报告改造）可并行于 Phase 2-4，但依赖 Phase 1 的映射表
- **Phase 6**（Dashboard）独立于其他，可最后做也可穿插
