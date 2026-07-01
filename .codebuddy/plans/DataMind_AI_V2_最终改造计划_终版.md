# DataMind AI V2 最终改造计划（终版）

> 经过三轮迭代锁定。核心原则：
> **AI 负责思考（Think），程序负责执行（Compute）。**
> AI 建议 + 程序校验，不走极端。

---

## 架构总览

```
AI 洞察引擎
    │
    ├──→ Markdown（给人看）
    │
    └──→ Analysis Plan（结构化 JSON）
            │
            business_question:     "销售增长是否放缓？"（给人看）
            analysis_goal:         "判断增长速度变化"（辅助理解）
            recommended_analysis:  "growth_analysis"（程序执行）
            suggested_dimension:   "日期"（建议，非强制）
            suggested_metric:      "销售额"（建议，非强制）
            priority:              "high"
            reason:                "销售额是核心指标"（给人看）
            │
            ▼
        Analysis Engine（模板 + 算法）
            │
            ├── 校验：suggested_* 是否存在于 df？
            │     YES → 使用
            │     NO  → 自动寻找合适列
            │
            ├── 校验：can_run(df)？
            │     YES → 执行
            │     NO  → fallback 到兼容的分析方法
            │
            ▼
        Analysis Package（统一输出）
            ├── KPIs
            ├── Tables
            ├── Charts
            ├── Insights
            └── Conclusions
            │
            ├──────────────┐
            ▼              ▼
        数据看板        分析报告
        （读同一份 Package）
```

---

## 一、改造范围

```
数据上传    →  不动
数据清洗    →  不动
分析可视化  →  ★ 重点修改
仪表盘      →  ★ 重点修改（指挥中心 / 数据看板 / 分析报告）
```

---

## 二、新增模块清单

### 2.0 Analysis Template Engine（分析模板引擎）

**新建目录**：`src/analysis_templates/`

```
src/analysis_templates/
    __init__.py
    base.py                # AnalysisTemplate 基类 + AnalysisPackage 数据结构
    growth_analysis.py     # 增长分析（同比/环比/移动平均/拐点）
    ranking_analysis.py    # 排名分析（排序/TOP/累计贡献）
    structure_analysis.py  # 结构分析（占比/分布）
    concentration_analysis.py  # 集中度分析（pareto/hhi/gini/lorenz）
    correlation_analysis.py    # 相关分析（pearson/spearman/kendall）
    anomaly_analysis.py        # 异常分析（z-score/IQR/isolation_forest）
    distribution_analysis.py   # 分布分析（histogram/分箱）
    proportion_analysis.py     # 占比分析（pie/treemap）
```

### 2.0.1 模板两层设计

每个 Analysis 模板可配置多种 Algorithm：

| Analysis | Algorithm | 含义 |
|----------|-----------|------|
| `growth_analysis` | `yoy` / `mom` / `moving_avg` / `exp_smooth` | 不同增长算法 |
| `concentration_analysis` | `pareto` / `hhi` / `gini` / `lorenz` | 不同集中度算法 |
| `correlation_analysis` | `pearson` / `spearman` / `kendall` | 不同相关系数 |
| `anomaly_analysis` | `zscore` / `iqr` / `isolation_forest` | 不同异常检测算法 |

### 2.0.2 AnalysisTemplate 基类

```python
class AnalysisTemplate:
    name: str                           # "增长分析"
    analysis_type: str                  # "growth_analysis"
    
    # 校验
    def can_run(self, df: pd.DataFrame) -> bool:
        """检查数据是否满足此分析的前置条件"""
        ...
    
    # 列推断（兜底）
    def auto_detect_dimension(self, df: pd.DataFrame) -> str:
        """自动寻找合适的维度列"""
        ...
    
    def auto_detect_metric(self, df: pd.DataFrame) -> str:
        """自动寻找合适的指标列"""
        ...
    
    # 执行
    def execute(self, df: pd.DataFrame, 
                dimension: str, metric: str, 
                algorithm: str = None) -> AnalysisPackage:
        """执行分析，返回完整 Package"""
        ...
```

### 2.0.3 AnalysisPackage 数据结构

```python
@dataclass
class AnalysisPackage:
    id: str
    business_question: str          # AI 原始问题
    analysis_type: str              # growth_analysis / ranking_analysis / ...
    algorithm: str                  # pareto / pearson / zscore / ...
    kpis: List[KPIItem]             # KPI 列表
    tables: List[TableData]         # 表格列表
    charts: List[ChartMeta]         # 图表列表（可能多张）
    insights: List[str]             # 洞察文字
    conclusions: List[str]          # 结论
    executed_at: str                # 执行时间
```

---

## 三、修改模块清单

### 3.1 Phase 1：AI 洞察输出改造

**修改文件**：`src/ai_agent/prompts.py`

AI 新增输出 Analysis Plan JSON，格式：

```json
{
  "insights": "## 数据概览\n...\n## 分析建议\n...",
  "plans": [
    {
      "business_question": "销售增长是否放缓？",
      "analysis_goal": "判断增长速度变化",
      "recommended_analysis": "growth_analysis",
      "suggested_dimension": "日期",
      "suggested_metric": "销售额",
      "algorithm": "yoy",
      "priority": "high",
      "reason": "销售额是核心指标，且存在时间维度"
    },
    {
      "business_question": "是否存在二八现象？",
      "analysis_goal": "判断销售集中度",
      "recommended_analysis": "concentration_analysis",
      "suggested_dimension": "产品",
      "suggested_metric": "销售额",
      "algorithm": "pareto",
      "priority": "high",
      "reason": "可用于优化库存和资源分配"
    }
  ]
}
```

**plan 字段定义**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `business_question` | string | ✅ | 给人看的业务问题 |
| `analysis_goal` | string | ✅ | 分析目标简述 |
| `recommended_analysis` | string | ✅ | 分析方法名（growth_analysis/ranking_analysis/...） |
| `suggested_dimension` | string | 建议 | AI 建议的维度列名 |
| `suggested_metric` | string | 建议 | AI 建议的指标列名 |
| `algorithm` | string | 可选 | 具体算法（pareto/pearson/zscore/...），不传则用默认 |
| `priority` | string | ✅ | high / medium / low |
| `reason` | string | ✅ | 给用户看的推荐理由 |

**Prompt 铁律**：
- `recommended_analysis` 只能从枚举中选择
- `suggested_dimension` / `suggested_metric` 必须是数据中的真实列名
- 禁止输出 `chart_type`

---

### 3.2 Phase 2：后端 Analysis Engine

**修改文件**：`backend/routers/insights.py` + 新建 `src/analysis_templates/`

**新增 API**：`POST /analysis/execute`

请求：
```json
{
  "session_id": "...",
  "plans": [
    {
      "business_question": "销售增长是否放缓？",
      "recommended_analysis": "growth_analysis",
      "suggested_dimension": "日期",
      "suggested_metric": "销售额",
      "algorithm": "yoy",
      "priority": "high",
      "reason": "..."
    }
  ]
}
```

后端执行流程：
```
1. 根据 recommended_analysis 加载对应 AnalysisTemplate
2. 校验 suggested_dimension 是否存在于 df
   - 存在 → 使用
   - 不存在 → 调用 auto_detect_dimension()
3. 校验 suggested_metric 同理
4. 调用 template.can_run(df)
   - True → 执行 execute()
   - False → 寻找 fallback 分析（如降级为 ranking_analysis）
5. 返回 AnalysisPackage
```

返回格式：
```json
{
  "packages": [
    {
      "id": "pkg_001",
      "business_question": "销售增长是否放缓？",
      "analysis_type": "growth_analysis",
      "algorithm": "yoy",
      "kpis": [...],
      "tables": [...],
      "charts": [
        {"title": "销售额趋势", "chart_type": "line", "option": {...}},
        {"title": "同比增长率", "chart_type": "bar", "option": {...}}
      ],
      "insights": ["增长速度放缓", "Q3 增速最高"],
      "conclusions": ["整体呈增长趋势但增速下降"]
    }
  ]
}
```

---

### 3.3 Phase 3：前端消费改造

**修改文件**：`frontend/src/pages/AnalysisPage.tsx`

**删除**：
- `CHART_KEYWORD_MAP`
- `COMPUTE_KEYWORDS`
- 正则解析逻辑（约第 398-531 行）

**新增流程**：
```
用户点击「生成洞察」
    ↓
展示：Markdown 洞察 + business_question 列表（带 priority 和 reason）
    ↓
用户勾选想要执行的问题 → 点击「执行分析」
    ↓
前端 POST /analysis/execute，传入勾选的 plans
    ↓
后端返回 packages[]
    ↓
前端展示每个 package：
  - KPI 数字卡
  - 表格（TableRenderer）
  - 图表（EChartsRenderer，可能多张）
  - 洞察文字
    ↓
用户选择保存 package 或其中部分图表到 Dashboard
```

---

### 3.4 Phase 4：统一可视化渲染

**新建文件**：`frontend/src/components/VisualizationRenderer.tsx`

```typescript
type VisualizationItem = {
  id: string;
  type: "chart" | "table" | "kpi" | "insight";
  data: any;
};

// 渲染分发
// type == "chart" → EChartsRenderer
// type == "table" → TableRenderer
// type == "kpi" → KPICard
// type == "insight" → InsightCard
```

---

### 3.5 Phase 5：分析可视化 Tab 改造

保留三个 Tab：统计分析 / 智能绘图 / AI对话

**智能绘图 Tab 改造**（三栏布局）：
```
┌─────────────────┬──────────────────┬─────────────────┐
│ 分析问题列表      │ 执行结果          │ 图表             │
│                  │                  │                 │
│ ✓ 增长是否放缓？ │ ┌─KPI──────────┐ │ [ECharts ①]    │
│   原因：核心指标   │ │总销售额: 1.2M │ │                 │
│                  │ │平均增长: 3.2% │ │ [ECharts ②]    │
│ □ 是否有二八现象？│ └──────────────┘ │                 │
│   原因：优化库存   │ ┌─表格────────┐  │                 │
│                  │ │月份│销售│增长 │  │                 │
│ [执行选中]       │ │1月 │100 │ -  │  │                 │
│                  │ │2月 │120 │20% │  │                 │
│                  │ └──────────────┘ │                 │
└─────────────────┴──────────────────┴─────────────────┘
```

---

### 3.6 Phase 6：仪表盘改造

#### 6.1 数据看板（medical 模板）

**删除**：`computeRadarFromData` / `computeRingChartsFromData` / 4 Tab 导航

**V2 固定布局**：
```
┌──────────────────────────────────────────────────────┐
│ KPI 数字卡                                            │
├───────────────┬──────────────────────────────────────┤
│ AI 洞察摘要    │ 主分析区域                             │
│ （文字卡片）   │ （从保存的 AnalysisPackage 读取        │
│               │   每个 package 一个区块：               │
│               │   ┌─ KPI ─────────────────────────┐  │
│               │   │ 总销售额 1.2M | 增长率 3.2%     │  │
│               │   ├─ Chart + Table ───────────────┤  │
│               │   │ [折线图] | [增长率表]           │  │
│               │   ├─ Insight ─────────────────────┤  │
│               │   │ 增长速度放缓，Q3 增速最高        │  │
│               │   └───────────────────────────────┘  │
│               │                                      │
│               │   ┌─ KPI ─────────────────────────┐  │
│               │   │ TOP3 贡献率 68% | HHI 0.12     │  │
│               │   │ ...                            │  │
│               │   └───────────────────────────────┘  │
└───────────────┴──────────────────────────────────────┘
```

**核心原则**：
- 不再自动生成任何图表
- 所有内容来自用户保存的 AnalysisPackage
- 每个 package 作为一个分析区块，包含 KPI + 图表 + 表格 + 洞察
- 没有 package 时显示引导文字，不显示空白

#### 6.2 指挥中心（command 模板）

**六宫格布局**（同上一版）：
```
┌──────────────┬──────────────────┬──────────────┐
│ KPI           │ 全国地图          │ AI 摘要       │
├──────────────┼──────────────────┼──────────────┤
│ TOP 排行      │ 异常预警          │ 最新洞察      │
│ （柱状图）    │ （文字卡片）       │ （文字卡片）   │
└──────────────┴──────────────────┴──────────────┘
```
数据来源：AnalysisPackage 仓库。

#### 6.3 分析报告（report 模板）

**删除**：保底三张图

**V2 流程**：
```
生成报告时：
  报告 Section（如 trend 类）
      │
      ▼
  从用户保存的 AnalysisPackage 中找 analysis_type 匹配的
      │
      ├── 有匹配 → 渲染 package 中的 KPI + 图表 + 表格 + 洞察
      └── 无匹配 → analysis_type 不适合当前数据
            → AI 换分析角度重写该 Section
            → 不输出空白
```

**优势**：即使缺图，至少还有 KPI + 表格 + 文字内容。

---

## 四、删除清单（最终版）

| # | 删除目标 | 文件 | 原因 |
|---|---------|------|------|
| 1 | `CHART_KEYWORD_MAP` | AnalysisPage.tsx | AI 直接输出 recommended_analysis |
| 2 | `COMPUTE_KEYWORDS` | AnalysisPage.tsx | 计算由 Analysis Template 内置 |
| 3 | AI 生成 Python `exec()` | data.py | Compute Engine 替代 |
| 4 | 保底三张图 | report_analyzer.py | AnalysisPackage 驱动 |
| 5 | 前端正则解析 | AnalysisPage.tsx:398-531 | 直接读 plans[] |
| 6 | `computeRadarFromData` | MedicalDashboard.tsx | 不再自动生成 |
| 7 | `computeRingChartsFromData` | MedicalDashboard.tsx | 不再自动生成 |
| 8 | 4 Tab 导航栏 | MedicalDashboard.tsx | 固定单页 |
| 9 | 关键词匹配知识库 | 不建 | AI 直接输出 method |
| 10 | 图表推荐器模块 | 不建 | 图由 Analysis Template 内置 |
| 11 | `intent_chart_map.py` | 不建 | 被 Analysis Template 替代 |

---

## 五、执行顺序

```
Phase 0: Analysis Template Engine（基础）
    │     - base.py + 6 个模板
    │     - AnalysisPackage 数据结构
    │
    ├──→ Phase 1: AI 输出改造
    │        - prompts.py 新增 Analysis Plan 要求
    │        - insights.py 新增 plans[] 返回
    │
    ├──→ Phase 2: Analysis Engine API
    │        - POST /analysis/execute
    │        - suggested_* 校验 + can_run() + fallback
    │
    ├──→ Phase 3: 前端消费
    │        - 删除 Keyword/Regex
    │        - 新增问题勾选 + 执行流程
    │
    ├──→ Phase 4: 统一渲染
    │        - VisualizationRenderer
    │
    ├──→ Phase 5: 分析可视化 Tab
    │        - 智能绘图三栏布局
    │
    └──→ Phase 6: 仪表盘
             - 数据看板 / 指挥中心 / 分析报告
```

---

## 六、对比旧计划的关键变化

| 变化 | 旧计划 | 终版计划 |
|------|--------|---------|
| AI 输出 | 进化为 `business_question + intent` | `business_question + recommended_analysis + suggested_* + algorithm` |
| 知识库 | intent → chart 映射 | 不建立；AI 直接输出 analysis method 名 |
| 列选择 | AI 全权决定 | AI 建议 + 程序校验 + 兜底自动找 |
| 模板设计 | 1:1（growth 一个模板、pareto 一个模板） | 两层（Analysis → Algorithm） |
| 错误处理 | 无 | `can_run(df)` 校验 + fallback |
| 输出单位 | ChartMeta | AnalysisPackage（KPI+Table+Chart+Insight） |
| 关键词匹配 | 用 | **不用** |
