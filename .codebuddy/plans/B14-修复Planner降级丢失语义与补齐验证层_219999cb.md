---
name: B14-修复Planner降级丢失语义与补齐验证层
overview: 5 项修复：① fallback 保留 dim/metric（根治"线上vs线下"变成"日期排行"）；② Planner 语义实体→列映射（"地区"→GEO列，"利润"→PROFIT列）；③ Schema Validator 验证列存在性；④ can_run 支持派生指标检查；⑤ AnalysisPackage 增加 fallback_reason 字段。
todos:
  - id: fix-fallback-dim-met
    content: "[P0] 修复 analysis.py 的 _fallback_or_unsupported 签名增加 dim/met 参数，_execute_with_fallback 调用处补传，fallback 时使用原始列而非 None,None"
    status: completed
  - id: add-entity-mapping
    content: "[P1] planner.py 增加 ENTITY_MAP 语义实体映射表 + _extract_entity 方法 + _pick_dimension/_pick_metric 扩展接收 entity_type；column_classifier.py 新增 match_by_keywords 方法"
    status: completed
  - id: add-schema-validator
    content: "[P1] planner.py 的 plan() 增加 _validate_columns 步骤，验证 dimension/metric 列在 df 中存在且类型正确，失败则返回 status=unsupported"
    status: completed
    dependencies:
      - add-entity-mapping
  - id: extend-can-run-derived
    content: "[P1] base.py 的 TemplateSpec 增加 DERIVED_REQUIREMENTS 字段，can_run() 扩展检查派生分析所需基础列组合"
    status: completed
  - id: add-fallback-reason
    content: "[P1] base.py 的 AnalysisPackage 增加 fallback_reason 字段；analysis.py 的 _execute_with_fallback 和 _fallback_or_unsupported 中设置降级原因"
    status: completed
    dependencies:
      - fix-fallback-dim-met
  - id: verify-all-scenarios
    content: 使用 [skill:quality-assurance-sop] 验证三个关键场景：fallback 后 dim/metric 保持不变、语义实体匹配地域列、无对应列返回 Unsupported
    status: completed
    dependencies:
      - fix-fallback-dim-met
      - add-entity-mapping
      - add-schema-validator
      - add-fallback-reason
---

## 用户需求（5项全部必须做）

### P0：修复 fallback 丢失 dim/metric

`analysis.py:129-134` 的 `_fallback_or_unsupported` 传 `None, None` 导致排名分析模板自己重选列，"渠道利润"降级后变成"日期TOP10"。Planer 已选好的 dim/met 必须保留传递，只替换分析模板，不替换列。

### P1：Planner 语义实体到列映射

不能用字符串匹配（`if "地区" in columns`）。ColumnClassifier 已有 GEO_KEYWORDS/DIMENSION_KEYWORDS 关键字体系。必须从 business_question 提取实体词判定实体类型（geo/product/channel/customer/time/metric），再用对应的关键字集去 df 列名中优先匹配。例如"地区"→实体=GEO→GEO_KEYWORDS命中"省份"列。

### P1：Schema Validator 列存在性验证

Planner 选定 dim/metric 后必须验证这些列在 df 中真实存在。不存在则返回 Unsupported 状态，不可静默降级为默认列。

### P1：can_run() 派生分析能力检查

复购率不是直接列，需要"客户ID+订单日期+订单号"字段组合才能计算。当前 can_run() 只检查 REQUIRED_SCHEMA 的列类型，需扩展 TemplateSpec 和 can_run() 支持"派生指标所需基础字段组合"的检查。

### P1：AnalysisPackage 增加 fallback_reason

在降级链中记录降级原因，前端可显式告知用户"已自动使用排名分析替代对比分析"，避免用户误解为什么问题变了。

## 技术方案

### 改动1：fallback 保留 dim/metric（P0 — analysis.py）

**目标**：`_fallback_or_unsupported` 不再丢弃已选好的列。

**改动点**：

- `_fallback_or_unsupported(df, method, question, depth)` 签名增加 `dim=None, met=None`
- 第132行 `_execute_with_fallback(df, "ranking_analysis", None, None, None, ...)` 改为传入 `dim, met`
- `_execute_with_fallback` 第109行调用处补传 `dim, met` 参数
- 同时设置 `fallback_reason`（见改动5）

### 改动2：Planner 语义实体映射（P1 — planner.py）

**目标**：从 question 提取实体类型，用 ColumnClassifier 关键字匹配实际列名。

**实现方式**：

1. 在 `Planner` 类中定义实体词到列类型的映射表：

```python
ENTITY_MAP = {
    "geo": {"words": ["地区","省份","省","城市","市","区","县","区域"], "col_type": "geo"},
    "product": {"words": ["产品","商品","品类","品牌","型号"], "col_type": "category"},
    "channel": {"words": ["渠道","来源","线上","线下","终端","门店"], "col_type": "category"},
    "customer": {"words": ["客户","用户","会员","消费者"], "col_type": "category"},
    "time": {"words": ["日期","时间","月份","年份","季度","周"], "col_type": "time"},
    "metric_sales": {"words": ["销售额","收入","营收","销售","金额"], "col_type": "metric"},
    "metric_profit": {"words": ["利润","净利","毛利"], "col_type": "metric"},
}
```

2. 新增 `_extract_entity(question)` 方法，扫描实体词返回实体类型列表

3. 修改 `_pick_dimension(df, prefer, entity_type=None)` — 当 entity_type 指定时，用对应关键字集优先匹配：

- entity_type="geo" → 用 GEO_KEYWORDS 筛列
- entity_type="product"/"channel"/"customer" → 用 DIMENSION_KEYWORDS 子集筛列
- entity_type="time" → 用 TIME_KEYWORDS 筛列

4. 修改 `_pick_metric(df, entity_type=None)` — 当 entity_type 为 metric_sales/metric_profit 时，用 METRIC_KEYWORDS 子集优先选指标列

5. 修改 `_select_columns(df, method, question)` — 接收 question，先提取实体，再传给 pick 方法

6. ColumnClassifier 新增方法 `match_by_keywords(df, keywords)` → 返回匹配的列名列表

### 改动3：Schema Validator（P1 — planner.py）

**目标**：验证 Planer 选出的 dim/metric 真实存在于 df.columns。

在 `plan()` 方法的 `_select_columns` 返回后增加验证：

```python
valid, reason = self._validate_columns(df, dimension, metric, analysis_method)
if not valid:
    return {"status": "unsupported", "reason": reason, ...}
```

- 检查 `dimension` 是否在 `df.columns`（dimension 可能为 None 如 distribution_analysis）
- 检查 `metric` 是否在 `df.columns`
- 检查 metric 列是否为数值类型
- 不通过时 `plan()` 返回含 `status: "unsupported"` 的字典，路由层据此直接调用 `_unsupported()`

### 改动4：can_run() 派生分析检查（P1 — base.py）

**目标**：TemplateSpec 增加派生字段要求，can_run() 检查基础字段组合。

1. `TemplateSpec` 新增字段：

```python
DERIVED_REQUIREMENTS: dict = field(default_factory=dict)
# 示例: {"retention_analysis": {"required_columns": ["客户ID","订单日期","订单号"]}}
```

2. `can_run()` 扩展：在现有检查后追加派生要求检查

```python
if self.spec.DERIVED_REQUIREMENTS:
    req = self.spec.DERIVED_REQUIREMENTS.get(self.spec.analysis_type, {})
    required_cols = req.get("required_columns", [])
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        return False
```

3. 此改动为未来模板（如 retention_analysis）预留基础设施，当前无需修改现有模板的 can_run() 行为

### 改动5：fallback_reason（P1 — base.py + analysis.py）

1. `AnalysisPackage` 新增字段：`fallback_reason: str | None = None`

2. 设置点（analysis.py）：

- `_execute_with_fallback` 中 can_run 失败降级时：`pkg.fallback_reason = f"当前数据不满足{method}的运行条件，已自动降级为{fallback_method}"` 
- `_fallback_or_unsupported` 中：设置 `fallback_reason = f"分析方法'{method}'尚未实现，已使用排名分析替代"`
- `_unsupported` 中保持 reason 在 insights 中不变

3. 前端 `VisualizationRenderer.tsx` 的 UnsupportedBlock 已经显示 `fallback_from`，无需额外修改。前端后续可按需在正常 pkg 上也展示 fallback_reason 提示条。

### 架构影响

四个文件改动，改动集中在：

- `analysis.py`：3处（_fallback_or_unsupported 签名+内部+调用点，fallback_reason 赋值）
- `planner.py`：5处（ENTITY_MAP、_extract_entity、_pick_dimension/pick_metric 扩展、plan() 列验证）
- `column_classifier.py`：1处（新增 match_by_keywords 方法）
- `base.py`：3处（AnalysisPackage 加字段、TemplateSpec 加字段、can_run 扩展）

无新文件，无新依赖，沿袭现有 ColumnClassifier 关键字体系。

## Agent Extensions

### Skill

- **quality-assurance-sop**
- 用途：修改完成后用 TestClient 验证三个场景：(1) P0 — "线上vs线下哪个更赚钱?"不再变成"日期TOP10" (2) P1 — "哪个地区贡献最高?"能匹配到地域列 (3) P1 — 无对应列时返回 Unsupported 而非硬降级
- 预期结果：三个场景全部通过，fallback_reason 字段非空，dim/metric 在降级后保持不变