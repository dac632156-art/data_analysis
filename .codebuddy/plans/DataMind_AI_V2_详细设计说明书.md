# DataMind AI V2 详细设计说明书

> **定稿日期**：2026-07-01
> **状态**：所有 P0/P1 问题已拍板，后续开发严格按此文档执行。

---

## 一、系统架构图（最终版）

```
                        数据上传 + 清洗（不动）
                              │
                              ▼
                    ┌─────────────────────┐
                    │   AI 洞察引擎         │
                    │  (prompts.py)        │
                    │                      │
                    │  输出 1：Markdown    │
                    │  输出 2：Intent[]    │
                    └────────┬────────────┘
                             │
                    ┌────────▼────────────┐
                    │   Planner            │
                    │   (规则引擎)          │
                    │                      │
                    │  intent → analysis  │
                    │  intent → algorithm │
                    │  intent → dim/metric│
                    └────────┬────────────┘
                             │
                    ┌────────▼────────────┐
                    │   Analysis Engine    │
                    │   (模板执行)          │
                    │                      │
                    │  can_run() 校验      │
                    │  compute → table    │
                    │  compute → kpi      │
                    │  compute → insight  │
                    │  compute → ChartData│
                    └────────┬────────────┘
                             │
                    ┌────────▼────────────┐
                    │   ChartRenderer      │
                    │   (echart_generator) │
                    │                      │
                    │  ChartData → Option │
                    └────────┬────────────┘
                             │
                    ┌────────▼────────────┐
                    │   AnalysisPackage    │
                    │                      │
                    │  KPIs               │
                    │  Tables             │
                    │  Charts（含option）  │
                    │  Insights           │
                    │  Conclusions        │
                    └────────┬────────────┘
                             │
                    ┌────────▼────────────┐
                    │   Session 暂存       │
                    │  (临时 package)      │
                    └────────┬────────────┘
                             │
                    POST /analysis/save
                             │
                             ▼
                    SessionManager 存储
                   (saved_packages)
                             │
              ┌──────────────┴──────────────┐
              │                             │
    ┌─────────▼─────────┐     ┌─────────────▼───────────┐
    │   数据看板          │     │   分析报告               │
    │   (MedicalDashboard)│     │   (report 模板)          │
    │                    │     │                         │
    │   读 packages[]    │     │   Section 按 analysis    │
    │   每个 package     │     │   匹配 package           │
    │   一个分析区块     │     │   - 有 → 渲染           │
    │                    │     │   - 无 → 隐藏 Section   │
    └────────────────────┘     └─────────────────────────┘
```

---

## 二、核心原则

1. **AI 只负责理解业务**：输出 business_question，不输出任何技术决策
2. **Planner 负责确定 analysis_method**：评分制匹配 → 结合 ColumnClassifier 和 TemplateSpec.REQUIRED_SCHEMA 推导 algorithm、dimension、metric
3. **Analysis Engine 负责执行**：固定模板完成计算 → 图表 → 表格 → KPI → 洞察
4. **直接隐藏，不重写**：分析报告中无匹配 package 的 Section 直接隐藏，不调 AI 重写

---

## 三、命名体系统一（P0-3）

全系统只使用以下 analysis 名称：

| 统一名称 | 显示标签 | 报告 Section 标签 | V1状态 | 说明 |
|---------|---------|------------------|--------|------|
| `growth_analysis` | 增长分析 | 趋势分析 | ✅ 实现 | 趋势、增长率、同比、环比 |
| `ranking_analysis` | 排名分析 | TOP 分析 | ✅ 实现 | 排序、TOP N |
| `structure_analysis` | 结构分析 | 结构分析 | ✅ 实现 | 占比、分布 |
| `concentration_analysis` | 集中度分析 | 集中度 | ✅ 实现 | Pareto、HHI、Gini |
| `correlation_analysis` | 相关分析 | 相关分析 | ✅ 实现 | Pearson、Spearman |
| `anomaly_analysis` | 异常分析 | 异常分析 | ✅ 实现 | Z-Score、IQR |
| `distribution_analysis` | 分布分析 | 分布分析 | ✅ 实现 | Histogram、分箱 |
| `proportion_analysis` | 占比分析 | 占比分析 | ✅ 实现 | Pie、Treemap |
| `comparison_analysis` | 对比分析 | 对比分析 | 🔲 占位（fallback→ranking） | 分组差异、雷达图 |
| `decomposition_analysis` | 贡献度分析 | 贡献度分析 | 🔲 占位（fallback→ranking） | 瀑布图、贡献度 |

**旧名称全部弃用**：`trend`、`top`、`share`、`geo`、`composition`。
（`structure` 作为 `structure_analysis` 的词根保留，全局搜索时需精确匹配）

**Applies to**：
- `prompts.py`：AI Prompt 中的枚举
- `report_analyzer.py`：`plan_charts()` 中的 analysis_type
- `exportEChartsDashboard.ts`：Section type 枚举
- `MedicalDashboard.tsx`：Tab 分类
- `dashboard.py`：`_CHART_TAB_MAP`

---

## 四、接口设计（P0-2）

### 接口 1：POST /insights/generate（修改）

**职责**：AI 读取数据 → 输出 Markdown 洞察 + Analysis Intent 列表

**请求**（不变）：
```json
{
  "session_id": "...",
  "api_key": "...",
  "base_url": "...",
  "model": "..."
}
```

**返回**（V2 新格式）：
```json
{
  "insights": "## 数据概览\n...\n## 分析建议\n...",
  "intents": [
    {
      "business_question": "销售增长是否放缓？",
      "analysis_goal": "判断增长速度变化",
      "priority": "high",
      "reason": "销售额是核心指标"
    },
    {
      "business_question": "哪些地区贡献最高？",
      "analysis_goal": "地区排名",
      "priority": "high",
      "reason": "优化区域资源"
    }
  ]
}
```

**AI 输出要求（Prompt 铁律）**：
- 使用 Structured Output（JSON schema），不用分隔符
- `intents[]` 中的 `business_question` / `analysis_goal` / `reason` 由 AI 自由发挥
- **不输出** `analysis_method` / `algorithm` / `dimension` / `metric` / `chart_type`
- `priority` 取值：`"high"` | `"medium"` | `"low"`

---

### 接口 2：POST /analysis/run（新增）

**职责**：接收 AI 输出的 intent → Planner 翻译 → Analysis Engine 执行 → 返回 Package

**请求**：
```json
{
  "session_id": "...",
  "intents": [
    {
      "business_question": "销售增长是否放缓？",
      "analysis_goal": "判断增长速度变化",
      "priority": "high",
      "reason": "销售额是核心指标"
    }
  ]
}
```

**后端处理流程**：
```
对每个 intent：
  1. Planner.plan(intent, df)
     → analysis_method: "growth_analysis"
     → algorithm: "yoy"（默认）
     → dimension: ColumnClassifier 自动推断
     → metric: ColumnClassifier 自动推断

  2. AnalysisTemplate.can_run(df)
     → True → execute()
     → False → fallback 到 spec.FALLBACK 指定模板，递归直到找到可运行模板或返回 Unsupported

  3. AnalysisTemplate.execute(df, dimension, metric, algorithm)
     → AnalysisPackage
```

**返回**：
```json
{
  "packages": [
    {
      "id": "pkg_001",
      "business_question": "销售增长是否放缓？",
      "analysis_type": "growth_analysis",
      "algorithm": "yoy",
      "dimension": "日期",
      "metric": "销售额",
      "kpis": [
        {"label": "总销售额", "value": "1,245,000", "change": "+3.2%"},
        {"label": "平均增长率", "value": "2.8%", "change": null},
        {"label": "最大增长月", "value": "3月", "change": "+8.5%"}
      ],
      "tables": [
        {
          "title": "增长率明细",
          "columns": ["月份", "销售额", "环比增长", "同比增长"],
          "rows": [
            ["1月", 100000, null, null],
            ["2月", 120000, "+20%", null]
          ]
        }
      ],
      "charts": [
        {"slot":"trend",      "chart_type": "line", "title": "销售额趋势", "option": {...}},
        {"slot":"growth_rate","chart_type": "bar",  "title": "增长率变化", "option": {...}},
        {"slot":"cumulative",  "chart_type": "area", "title": "累计销售额", "option": {...}}
      ],
      "insights": [
        "销售额整体呈上升趋势",
        "3月增速最高，达8.5%",
        "Q2 增速有放缓迹象"
      ],
      "conclusions": [
        "增长趋势良好但增速下降"
      ],
      "can_run": true,
      "fallback_from": null
    }
  ]
}
```

**错误处理**：
- 如果所有 intent 都无法执行任何分析 → 返回 `{packages: [], message: "当前数据不支持所选分析"}`
- 单个 intent fallback 后仍无法执行 → 返回 UnsupportedAnalysisPackage：
```json
{
  "id": "pkg_unsupported_001",
  "business_question": "销售增长是否放缓？",
  "status": "unsupported",
  "reason": "当前数据缺少时间列和数值列",
  "suggestions": ["建议上传包含日期和销售额列的数据"],
  "can_run": false
}
```
前端收到后显示 ⚠ 提示卡片，不静默跳过。

---

### 接口 3：POST /analysis/save（修改自旧 /chart/save）

**请求**：
```json
{
  "session_id": "...",
  "package_ids": ["pkg_001", "pkg_002"]
}
```

**返回**：
```json
{
  "saved_count": 2,
  "package_ids": ["pkg_001", "pkg_002"]
}
```

存储方式：SessionManager 内存，key = `"saved_packages"`，value = `List[AnalysisPackage]`。

---

## 五、AI Prompt 设计（P1-5, P1-6）

### Structured Output JSON Schema

```json
{
  "type": "object",
  "properties": {
    "insights": {"type": "string"},
    "intents": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "business_question": {"type": "string"},
          "analysis_goal": {"type": "string"},
          "priority": {"type": "string", "enum": ["high", "medium", "low"]},
          "reason": {"type": "string"}
        },
        "required": ["business_question", "analysis_goal", "priority", "reason"]
      }
    }
  },
  "required": ["insights", "intents"]
}
```

### INSIGHTS_SYSTEM_PROMPT 补充规则

```text
你可以提出的分析方向包括：
- 增长趋势分析
- 排名和对比分析
- 结构和占比分析
- 集中度和分布分析
- 相关关系分析
- 异常值检测

你的 intents[] 必须：
- 每条是一个明确的业务问题
- business_question 用中文，15字以内
- analysis_goal 一句话概括分析目标
- priority 根据业务重要性选择 high/medium/low
- reason 说明为什么这个问题值得分析
- 每条 intent 独立，不相互引用
- 基于数据真实特征，不编造

禁止输出的内容：
- analysis_method / algorithm / dimension / metric / chart_type
- 任何技术实现细节
- 任何图表类型名称（如"折线图""柱状图"）
```

---

## 六、Planner 设计（新增模块）⭐

### 文件
`src/planner.py`

### 职责
接收 AI 的 `business_question` → 翻译为 `analysis_method` + `algorithm` + `dimension` + `metric`

### 核心逻辑

**设计原则**：不用顺序匹配（先到先得），改用**评分制**。
一个 business_question 可以命中多个分析方向的关键词，最终取最高分。

```python
class Planner:
    
    # 关键词 → (analysis_method, 权重) 映射（唯一事实来源）
    # 权重设计：更具体的词权重更高（如"帕累托"比"集中"更明确）
    KEYWORD_SCORES = [
        # growth_analysis
        (r"增长|增速",                "growth_analysis", 5),
        (r"放缓|下降|上升|趋势|走势|变化","growth_analysis", 3),
        
        # ranking_analysis
        (r"最高|最低|排行|排名|TOP|top|靠前|靠后", "ranking_analysis", 5),
        (r"第一|最大|最小",                      "ranking_analysis", 3),
        
        # proportion_analysis
        (r"占比|饼图|比例|份额|百分比",          "proportion_analysis", 5),
        
        # concentration_analysis
        (r"二八|帕累托|pareto|hhi|基尼|gini",  "concentration_analysis", 5),
        (r"集中度|集中|少数",                   "concentration_analysis", 3),
        
        # correlation_analysis
        (r"相关|关联|关系|影响|伴随|相关系",     "correlation_analysis", 4),
        
        # anomaly_analysis
        (r"异常|离群|突变|怪异|异常值|outlier", "anomaly_analysis", 5),
        (r"波动",                              "anomaly_analysis", 3),
        
        # distribution_analysis
        (r"直方图|频率|区间|分箱",              "distribution_analysis", 5),
        (r"分布|分散",                          "distribution_analysis", 3),
        
        # structure_analysis（兜底）
        (r"构成|结构|组成",                     "structure_analysis", 4),
        
        # V2 预留 Intent（V1 无模板，fallback 到 ranking_analysis）
        (r"对比|差异|比较|区别|vs",             "comparison_analysis", 4),
        (r"贡献|贡献度|贡献率|驱动|推动|拉动",   "decomposition_analysis", 4),
    ]
    
    DEFAULT_ALGORITHMS = {
        "growth_analysis": "yoy",
        "concentration_analysis": "pareto",
        "correlation_analysis": "pearson",
        "anomaly_analysis": "zscore",
    }
    
    def plan(self, intent: dict, df: pd.DataFrame) -> dict:
        question = intent["business_question"]
        
        # Step 1: 评分制匹配 → analysis_method
        analysis_method = self._match_with_score(question)
        
        # Step 2: 默认 algorithm
        algorithm = self.DEFAULT_ALGORITHMS.get(analysis_method)
        
        # Step 3: 根据模板的 REQUIRED_SCHEMA 推断 dimension / metric
        dimension, metric = self._select_columns(df, analysis_method)
        
        return {
            "analysis_method": analysis_method,
            "algorithm": algorithm,
            "dimension": dimension,
            "metric": metric,
        }
    
    def _match_with_score(self, question: str) -> str:
        """评分制匹配：所有命中关键词的 analysis 计入分数，返回最高分"""
        scores = {}
        for pattern, method, weight in self.KEYWORD_SCORES:
            if re.search(pattern, question):
                scores[method] = scores.get(method, 0) + weight
        if scores:
            return max(scores, key=scores.get)
        return "ranking_analysis"  # 默认兜底
    
    def _select_columns(self, df, analysis_method):
        """根据模板 REQUIRED_SCHEMA 推断列（调用 ColumnClassifier）。
        如果模板不存在（占位 intent），返回默认列，让 Engine 的 can_run+fallback 处理。"""
        from src.column_classifier import ColumnClassifier
        try:
            # 查模板 → 按 REQUIRED_SCHEMA 选列
            ...
        except TemplateNotFound:
            # 占位 intent → 返回默认列
            return self._default_columns(df)
    
    def _default_columns(self, df):
        """默认：第一个分类列 + 第一个数值列"""
        ...
```

**评分制示例**：
```
"销售额占比分布"
  → proportion_analysis: 5 分（"占比"）
  → distribution_analysis: 3 分（"分布"）
  → structure_analysis:  未命中
  → 结果：proportion_analysis ✅

"哪些产品销售增长最快"
  → ranking_analysis: 3 分（"最"字）
  → growth_analysis:  5 分（"增长"）
  → 结果：growth_analysis ✅
```

**与 Analysis Engine 的关系**：
- Planner 只管翻译，不管执行
- Planner 输出的 `dimension` / `metric` 传给 Analysis Engine 执行
- 如果 Planner 推断的列在 df 中不存在 → Analysis Engine 的 `can_run()` 返回 False → fallback

---

## 七、Analysis Engine 设计（P1-1, P1-3, P1-4）

### 目录结构

```
src/analysis_templates/
    __init__.py
    base.py                  # AnalysisTemplate 基类
    growth_analysis.py       # 增长分析
    ranking_analysis.py      # 排名分析
    structure_analysis.py    # 结构分析
    concentration_analysis.py # 集中度分析
    correlation_analysis.py  # 相关分析
    anomaly_analysis.py      # 异常分析
    distribution_analysis.py # 分布分析
    proportion_analysis.py   # 占比分析
```

### 第一版 8 个模板（P1-1）

后续版本增加：forecast / retention / churn / abc / rfm / funnel。

### 所有模板的 REQUIRED_SCHEMA（必补）

| 模板 | dimension_type | metric_type | min_dimension | min_metric | MIN_ROWS | MIN_DISTINCT | DEFAULT_ALGORITHM | FALLBACK |
|------|---------------|-------------|--------------|------------|----------|-------------|-------------------|----------|
| `growth_analysis` | time | numeric | 1 | 1 | 3 | 3 | yoy | ranking_analysis |
| `ranking_analysis` | category | numeric | 1 | 1 | 2 | 2 | — | proportion_analysis |
| `structure_analysis` | category | numeric | 1 | 1 | 2 | 1 | — | proportion_analysis |
| `concentration_analysis` | category | numeric | 1 | 1 | 3 | 3 | pareto | ranking_analysis |
| `distribution_analysis` | none | numeric≥1 | 0 | 1 | 10 | — | — | proportion_analysis |
| `correlation_analysis` | none | numeric≥2 | 0 | 2 | 5 | — | pearson | ranking_analysis |
| `anomaly_analysis` | optional | numeric | 0 | 1 | 10 | — | zscore | distribution_analysis |
| `proportion_analysis` | category | numeric | 1 | 1 | 1 | 1 | — | —（最后兜底） |
| `comparison_analysis` | category | numeric | 2 | 1 | 2 | 2 | — | ranking_analysis（占位） |
| `decomposition_analysis` | category | numeric | 1 | 1 | 2 | 2 | — | ranking_analysis（占位） |

### 每个模板的固定 OUTPUT（必补）

| 模板 | Charts（固定数量） | Tables（固定数量） | KPIs |
|------|-------------------|-------------------|------|
| `growth_analysis` | ①折线趋势 ②增长率柱状 ③累计面积（3张） | ①增长率明细 ②累计值（2张） | 总销售额/平均增长率/最大增长月/最低增长月 |
| `ranking_analysis` | ①横向柱状 TOP10（1张） | ①排名明细表（1张） | TOP1值/TOP3占比/TOP5占比 |
| `structure_analysis` | ①饼图 ②Treemap（2张） | ①汇总表（1张） | 最大分类占比/分类数 |
| `concentration_analysis` | ①排序柱状 ②累计折线 Pareto（2张） | ①Pareto明细表（1张） | TOP20贡献率/HHI |
| `distribution_analysis` | ①直方图 ②箱线图（2张） | ①分箱统计表（1张） | 均值/中位数/标准差/偏度 |
| `correlation_analysis` | ①散点图 ②热力图（2张） | ①相关系数矩阵（1张） | Pearson/Spearman/P-value |
| `anomaly_analysis` | ①箱线图 ②异常标记散点（2张） | ①异常值明细表（1张） | 异常数量/异常率 |
| `proportion_analysis` | ①饼图（1张） | ①汇总表（1张） | 最大占比/分类数 |

### 统一模板格式

```python
@dataclass
class TemplateSpec:
    """每个模板必须声明以下全部字段"""
    analysis_type: str           # "growth_analysis"
    display_name: str            # "增长分析"
    
    REQUIRED_SCHEMA: dict        # 输入要求（dimension_type / metric_type / min_*）
    MIN_ROWS: int
    MIN_DISTINCT_VALUES: int
    
    DEFAULT_ALGORITHM: str       # 默认算法
    FALLBACK: str                # can_run 失败时降级到哪个模板
    
    OUTPUT_CHARTS: list          # 固定输出的图表类型及数量
    OUTPUT_TABLES: list          # 固定输出的表格类型及数量
    OUTPUT_KPIS: list            # 固定输出的 KPI 标签

class AnalysisTemplate(ABC):
    spec: TemplateSpec
    
    def can_run(self, df: pd.DataFrame) -> bool:
        """基于 spec.REQUIRED_SCHEMA 自动校验"""
        required = self.spec.REQUIRED_SCHEMA
        
        # 1. 检查 dimension_type
        if required["dimension_type"] == "time":
            if not self._has_time_column(df):
                return False
        elif required["dimension_type"] == "category":
            if not self._has_category_column(df):
                return False
        
        # 2. 检查 metric_type (min_metric 个 numeric 列)
        numeric_cols = self._get_numeric_columns(df)
        if len(numeric_cols) < required.get("min_metric", 1):
            return False
        
        # 3. 检查行数和 distinct 值
        if len(df) < self.spec.MIN_ROWS:
            return False
        
        return True
    
    # --- 以下委托 ColumnClassifier ---
    def _has_time_column(self, df) -> bool:
        """委托 ColumnClassifier 判断是否存在时间列"""
        ...
    
    def _has_category_column(self, df) -> bool:
        """委托 ColumnClassifier 判断是否存在分类列"""
        ...
    
    def _get_numeric_columns(self, df) -> list:
        """委托 ColumnClassifier 获取所有数值列"""
        ...
    
    @abstractmethod
    def execute(self, df, dimension, metric, algorithm) -> AnalysisPackage:
        ...
```

### 示例：growth_analysis

```python
class GrowthAnalysis(AnalysisTemplate):
    spec = TemplateSpec(
        analysis_type="growth_analysis",
        display_name="增长分析",
        REQUIRED_SCHEMA={
            "dimension_type": "time",
            "metric_type": "numeric",
            "min_dimension": 1,
            "min_metric": 1,
        },
        MIN_ROWS=3,
        MIN_DISTINCT_VALUES=3,
        DEFAULT_ALGORITHM="yoy",
        FALLBACK="ranking_analysis",
        OUTPUT_CHARTS=["line", "bar", "area"],         # 3张
        OUTPUT_TABLES=["growth_table", "cumsum_table"], # 2张
        OUTPUT_KPIS=["total", "avg_growth", "max_month", "min_month"],
    )
    
    def execute(self, df, dimension, metric, algorithm="yoy"):
        # 按 spec.OUTPUT_* 严格输出，不增不减
        ...
```

### 统一数据对象：AnalysisPackage（全系统唯一）

**设计原则**：整个项目只认一种数据对象。分析可视化、数据看板、分析报告、指挥中心全部读取同一份 `AnalysisPackage`。

```python
@dataclass
class AnalysisPackage:
    """全系统统一数据对象，所有模块围绕它渲染"""
    
    # === 标识 ===
    id: str                          # "pkg_001"
    
    # === 分析元信息 ===
    analysis_type: str               # "growth_analysis"
    business_question: str           # "销售增长是否放缓？"
    algorithm: str                   # "yoy"
    dimension: str                   # "日期"
    metric: str                      # "销售额"
    
    # === 计算产出 ===
    kpis: List[KPIItem]              # KPI 列表
    tables: List[TableData]          # 表格列表
    charts: List[ChartItem]          # 图表列表（已生成的 ECharts option）
    insights: List[str]              # 洞察文字
    conclusions: List[str]           # 结论
    
    # === 元数据 ===
    can_run: bool                    # 是否成功执行
    fallback_from: str | None        # 从哪个模板降级而来
    saved_at: str | None             # 保存时间
    data_profile: dict               # {time_cols: [...], category_cols: [...], numeric_cols: [...]}

@dataclass
class KPIItem:
    label: str      # "总销售额"
    value: str      # "1,245,000"
    change: str     # "+3.2%" 或 null
    kpi_type: str   # "sum" | "avg" | "count" | "rate" | "change"

@dataclass
class TableData:
    title: str      # "增长率明细"
    table_type: str # "summary" | "ranking" | "cross" | "growth" | "correlation" | "detail" | "exception"
    columns: list   # ["月份", "销售额", "环比增长"]
    rows: list      # [["1月", 100000, null], ...]

@dataclass
class ChartItem:
    slot: str       # "trend" | "growth_rate" | "cumulative" | ...
    chart_type: str # "line" | "bar" | "pie" | "area" | ...
    title: str      # "销售额趋势"
    role: str       # "primary" | "secondary" | "detail"
    option: dict    # ECharts option（ChartRenderer 生成的完整配置）
```

**消费方对照**：

| 模块 | 读 AnalysisPackage 的哪些字段 |
|------|------------------------------|
| 分析可视化（智能绘图 Tab） | kpis + tables + charts（逐个渲染） |
| 数据看板（medical） | business_question + kpis + charts + tables + insights（每个 package 一个分析区块） |
| 分析报告（report） | Section 按 analysis_type 匹配 package → 渲染 kpis + tables + charts + insights |
| 指挥中心（command） | 从所有 packages 聚合提取 kpis + insights 到六宫格各卡片 |
| 存储（SessionManager） | 完整序列化 / 反序列化 |

**扩展方式**：新增分析模板（RFM、ABC、漏斗等）只需新增一个继承 `AnalysisTemplate` 的类，其 `execute()` 返回标准 `AnalysisPackage`，所有消费方无需改动。

### fallback 机制

```
growth_analysis.can_run(df) == False
    ↓
降级为 ranking_analysis（按 FALLBACK 字段）
    ↓
ranking_analysis.can_run(df) == False
    ↓
降级为 proportion_analysis（按 FALLBACK 字段）
    ↓
proportion_analysis.can_run(df) == False
    ↓
返回 UnsupportedAnalysisPackage：
  {
    "status": "unsupported",
    "business_question": "销售增长是否放缓？",
    "reason": "当前数据缺少数值列和时间列",
    "suggestions": ["建议上传包含销售额和日期列的数据"]
  }
```

Dashboard 收到 `UnsupportedAnalysisPackage` 时显示 ⚠ 提示卡片，不静默跳过。

---

### 7.5 ChartRenderer 层（新增）

**设计原则**：AnalysisTemplate 永远不负责 ECharts。模板只输出 ChartData，由 ChartRenderer 统一生成 option。

```
AnalysisTemplate.execute()  →  ChartData（chart_type + x + y + data）
        │
        ▼
ChartRenderer.render()      →  调用 echart_generator.create_echart()
        │
        ▼
ECharts option              →  塞入 AnalysisPackage.charts[n].option
```

**ChartData 格式**（模板输出）：
```python
@dataclass
class ChartData:
    slot: str         # "trend" | "growth_rate" | "cumulative" | ...
    chart_type: str   # "line" | "bar" | "pie" | "area" | ...
    title: str        # 图表标题
    x: str            # X 轴列名
    y: str            # Y 轴列名
    data: list        # [{x: ..., y: ...}, ...]
```

**ChartRenderer**（复用现有 echart_generator.py）：
```python
class ChartRenderer:
    def render(self, chart_data: ChartData, theme: str = "dark") -> dict:
        """调用 echart_generator.create_echart() 生成 ECharts option"""
        return create_echart(
            df=pd.DataFrame(chart_data.data),
            chart_type=chart_data.chart_type,
            x=chart_data.x,
            y=chart_data.y,
            title=chart_data.title,
            theme=theme,
        )
```

**好处**：
- 换主题/颜色/ECharts版本，只改 Renderer，模板不动
- Dashboard 深色、Report A4 浅色、CommandCenter 蓝色——同一份 ChartData 三种渲染
- Package 保存的 option 是快照（保存时渲染一次）；Dashboard 展示时可选择重新渲染

---

## 八、存储与生命周期设计（P0-1）

### Package 生命周期

```text
POST /analysis/run
      │
      ▼
生成 AnalysisPackage（仅此一次，不重复生成）
      │
      ├──→ 缓存到 SessionManager["analysis_packages"]  ← 用于后续保存
      │
      └──→ 返回完整 Package JSON 给前端  ← 用于立即展示
                │
                ▼
        分析页面立即渲染（无需二次请求）
                │
                ▼
        用户点击「保存」
                │
                ▼
        POST /analysis/save {package_ids: [...]}
                │
                ▼
        从 Session["analysis_packages"] 读取 → 复制到 Session["saved_packages"]
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
数据看板      指挥中心      分析报告
```

**性能**：`Session.put()` 是纳秒级操作，不影响响应时间。Package 只有一份，存在 Session 和返回前端的 JSON 是同一份数据的两种形式。

**不需要 `GET /analysis/package/{id}` 接口**——前端在 `/analysis/run` 的响应中已经拿到了完整 Package。

**SessionManager 新增两个字段**：

```python
# 临时结果（/analysis/run 后暂存，会话结束消失）
session_data["analysis_packages"] = {
    "pkg_001": { ... },  # 完整 Package
    "pkg_002": { ... },
}

# 用户主动保存的结果（跨请求持久）
session_data["saved_packages"] = [
    { ... },  # 完整 Package
]
```

**生命周期规则**：
- `analysis_packages`：每次 `/analysis/run` 覆盖写入，会话关闭即消失
- `saved_packages`：用户点「保存」后追加，保留到 session 过期
- 用户关闭网页 → 临时结果消失，已保存的结果保留

### saved_packages 数据结构

```python
session_data["saved_packages"] = [
    {
        "id": "pkg_001",
        "business_question": "销售增长是否放缓？",
        "analysis_type": "growth_analysis",
        "algorithm": "yoy",
        "dimension": "日期",
        "metric": "销售额",
        "kpis": [...],
        "tables": [...],
        "charts": [...],
        "insights": [...],
        "conclusions": [...],
        "saved_at": "2026-07-01T14:30:00"
    }
]
```

### 与旧图表保存的关系

**直接废弃 `saved_charts`**，不做双读兼容。
- 项目处于开发阶段，无需兼容旧数据
- `saved_packages` 是图表保存的唯一入口
- Chart 只是 Package 的 `charts[]` 字段，不单独保存

---

## 九、Dashboard 改造确认

### 数据看板（P3-17, P3-18）

- 删 `computeRadarFromData` / `computeRingChartsFromData`
- 删 4 Tab 导航，固定单页
- 读 `saved_packages[]`
- 每个 package 一个分析区块（KPI + 图表 + 表格 + 洞察）
- **默认显示最近 5 个**，点击「查看更多」展开全部
- **不自动生成任何图表**

### 指挥中心

- 六宫格布局
- 各卡片从 `saved_packages[]` 聚合提取（非一对一）
- 地图：从 `saved_packages[]` 中查找 dimension 列名匹配地理关键词（省/市/地区/区域/省份/城市）的 package，取其中图表渲染为地图。无匹配时隐藏地图区域（P3-19）

### 分析报告

- Section 按 `analysis_type` 匹配 `saved_packages[]`
- 有匹配 → 渲染 package 内容
- **无匹配 → 直接隐藏 Section**，不调 AI 重写（P3-20）

---

## 十、前端改造确认

### 分析页

- 删 `CHART_KEYWORD_MAP` / `COMPUTE_KEYWORDS` / 正则解析
- 洞察返回后展示 `intents[]` 列表
- 用户勾选 → 点击「执行分析」→ 调 `POST /analysis/run`
- 返回 packages[] → 跳转智能绘图 Tab 展示

### 智能绘图 Tab

三栏布局：
- 左栏：intent 列表（勾选状态）
- 中栏：执行结果（KPI + Table）
- 右栏：Charts（来自 package.charts[]）

### 统一渲染

- `VisualizationRenderer` 组件
- 支持 chart / table / kpi / insight 四种 type

---

## 十一、实施阶段

| 阶段 | 内容 | 依赖 |
|------|------|------|
| S0 | 提取 `src/column_classifier.py`（公共列分类模块） | 无 |
| S1 | 命名体系统一（全系统改 analysis_type） | S0 |
| S2 | 新建 `src/planner.py`（评分制意图识别） | S0, S1 |
| S3 | 新建 `src/analysis_templates/base.py`（TemplateSpec + 基类）+ 第1个模板 | S1 |
| S4 | 改造 `POST /insights/generate`（结构化输出 + intents[]） | S1 |
| S5 | 新增 `src/chart_renderer.py`（ChartData → Option，封装 echart_generator） | 无 |
| S6 | 新增 `POST /analysis/run`（Planner + Engine + ChartRenderer） | S2, S3, S5 |
| S7 | 新增 `POST /analysis/save`（从 Session 读取 packages 并保存） | S6 |
| S8 | 前端消费改造（删 Keyword + 新流程） | S4, S6, S7 |
| S9 | 补全其余 7 个模板（含每个模板的 TemplateSpec + ChartData 输出） | S3, S5 |
| S10 | Dashboard 改造（看板 + 指挥中心 + 报告） | S7, S8 |
| S11 | UI 精调（多 package 展示/折叠/三栏联动 + UnsupportedAnalysisPackage ⚠ 提示） | S10 |
