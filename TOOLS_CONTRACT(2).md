# 七种工具接口契约（tools_registry 对接约定）

> 用途：本文件是 `tools_registry.py` 与七种底层工具封装之间的**接口契约**。
> 由智能体侧（ReAct 循环）定义需求，底层封装实现方（朋友）据此实现，双方对齐后不再返工。
> 状态：⏳ `tools_registry.py` 未建；七种工具底层封装未定稿。本契约为对接前置约定。
>
> 约定原则：
> - 所有工具统一返回结构 `ToolResult`（见下），ReAct 循环只认 `ToolResult`，不关心内部实现。
> - 工具对传入 df **只读**，禁止原地修改 / 删除 / 覆盖原始数据（对应 AGENT_SYSTEM_PROMPT 铁律 8）。
> - 工具名必须与 `AGENT_SYSTEM_PROMPT` 中引用的名字**完全一致**（profile_data / run_python / run_template / run_analysis / generate_chart / generate_report / build_dashboard）。

---

## 统一返回结构 ToolResult

```python
@dataclass
class ToolResult:
    ok: bool                     # 执行是否成功
    data: Any = None             # 成功时的产物（图表/报告/结论/摘要，结构见各工具）
    error: str | None = None     # 失败时的报错信息
    missing_columns: list = field(default_factory=list)   # 缺列时列出所缺标准列名
    skipped_models: list = field(default_factory=list)    # run_template（业务模型分析）被跳过的模型及其缺列原因
    message: str | None = None   # 面向用户的提示（如清洗建议、下一步建议）
    # —— 以下 3 个字段为契约外、仅供 clean_data 弹窗所需，保留不删 ——
    available_alternatives: list = field(default_factory=list)  # 4 种可选填充方法 {method,label,description}
    needs_orientation: bool = False  # 是否需要追问（数据/取向类）
    orientation_hint: str = ""       # 追问提示语
```

> 工具集合说明：`clean_data` 是上述 7 种契约工具**之外额外保留**的工具（清洗弹窗逻辑需要），不改名、不删除，仅在此注明。它同样返回 `ToolResult`，且会用到 `available_alternatives / needs_orientation / orientation_hint` 三个契约外字段。

> ⚠️ 契约缺口提示：业务模型分析（`run_template`）会遍历注册模型、对缺列模型**静默跳过**，缺失会导致 agent 无法按铁律反问。
> 实现方必须补充：被跳过模型 → 记录 `skipped_models`（每项 `{model: str, missing_columns: List[str]}`），并在缺列时填全局 `missing_columns`（去重）。
> 注意：缺口**只在 `run_template`（业务模型分析）**——`run_analysis`（通用统计分析）按列自动算基础统计、不遍历模型、无此缺口。

---

## 1. profile_data —— 数据侦察与质量审查

- **语义**：首轮强制调用。拿到字段摘要、类型、缺失率、异常值、规模。
- **入参**：
  - `df: pd.DataFrame`
  - `sample: bool = False`（可选，是否返回小样预览）
- **返回** `ToolResult`：
  - `ok=True` 时 `data` 含：
    - `columns`: 各列名
    - `dtypes`: 各列类型
    - `row_count`, `col_count`
    - `missing_rate`: dict[列名, 缺失率]
    - `anomalies`: 异常值摘要（如超出 3σ 的字段）
    - `numeric_cols` / `category_cols` / `time_cols`：分类后的列清单（供后续选图/选模型用）
  - 若发现高缺失/异常，`message` 给出清洗建议选项（对应铁律 1 前置清洗拦截）。
- **注意**：只读，不修改 df。

## 2. run_python —— 自由写码分析（只读沙箱）

- **语义**：执行用户/agent 生成的 pandas 分析代码，向量化优先。
- **入参**：
  - `code: str`（Python 代码字符串，仅允许 pandas/numpy 等白名单库）
  - `df: pd.DataFrame`（当前数据集，只读传入）
- **返回** `ToolResult`：
  - `ok=True` 时 `data` 含执行结果（df / 标量 / 图表数据）。
  - `ok=False` 时 `error` 含完整 traceback，供 agent 自我纠错（铁律 2）。
- **约束**：绝对只读，禁止 `df.to_csv`/`df.to_file`/删除文件；禁止原地覆盖全局 df。

## 3. run_template —— 业务模型分析（模板）

- **语义**：调用已注册分析模板（AnalysisModel 体系），遍历模型、按列名命中自动计算。
- **入参**：
  - `intents: list[str] | None`（非空时仅跑命中的模型，避免无关模型假阳性；空时跑全部能跑的模型）
  - `df: pd.DataFrame`
- **返回** `ToolResult`：
  - `ok=True` 时 `data` 为 `List[AnalysisPackage]`。
  - **契约缺口落点（此处）**：凡 `can_run(df)=False` 的模型（缺列）→ 记录 `skipped_models: [{model, missing_columns}]`，并把所有所缺列去重填入 `missing_columns`；无跳过则为空列表。
  - 缺列时 `message` 给下一步建议（如先清洗 / 用 run_python）。
- **现状**：底层 `analysis_engine/engine.py:run_analysis` 已存在，工具层 `run_template` 已完成模型遍历 + 缺口回填。

## 4. run_analysis —— 通用统计分析（列名匹配驱动）

- **语义**：通用基础统计——自动识别数值列，对每列算总和/均值/中位数等，不遍历业务模型、无模型跳过。
- **入参**：
  - `df: pd.DataFrame`
- **返回** `ToolResult`：
  - `ok=True` 时 `data` 为 `List[AnalysisPackage]`（基础统计结果）。
  - 无 `skipped_models` / 无缺列跳过（通用统计不绑定业务模型 required_columns）。
- **现状**：`analysis_engine` 之外的基础统计已实现，无模型遍历故不涉及契约缺口。

## 5. generate_chart —— 图表生成

- **语义**：基于已分析数据生成单张图表（轻量产物）。
- **入参**：
  - `chart_type: str`（bar/line/pie/scatter/...）
  - `data`: 图表数据（ChartData 或等价结构）
  - `title: str`, `x`, `y` 等
- **返回** `ToolResult`：
  - `ok=True` 时 `data` 含 `ChartItem`（slot / chart_type / option / raw_data），供前端渲染。
- **注意**：agent 必须显式调用本工具出图，严禁在文字里用 markdown/代码模拟图表（铁律 3）。

## 6. generate_report —— 报告生成

- **语义**：基于本次会话已产生的图表与结论汇总，生成"文字+图表"正规文档。
- **入参**：
  - `packages: List[AnalysisPackage]`（本次会话已累积的分析产物）
  - `charts: List[ChartItem]`（已生成的图表）
  - `business_question: str`（用户业务问题，用于聚焦）
- **返回** `ToolResult`：
  - `ok=True` 时 `data` 为报告文档（结构化文本 + 内嵌图表引用）。
- **约束**：**基于已有产物撰写，禁止重新调用分析类工具重跑**（铁律 3 报告内容来源约束）。
- **现状**：`agent.py:generate_report` / `generate_report_from_packages` 已存在，需封装为工具接 ToolResult。
- **触发**：用户明确说"报告/可视化报告/分析文档/汇报材料/结论汇总/正式文档/写一份…文档/生成文档" → 直接调；轻量产物累积 ≥3 视角 → 反问用户是否生成（不直接出）。

## 7. build_dashboard —— 大屏生成

- **语义**：将图组装配为一屏多看板。
- **入参**：
  - `charts: List[ChartItem]`（服务于同一业务问题的关联图组）
  - `business_question: str`
- **返回** `ToolResult`：
  - `ok=True` 时 `data` 为大屏配置（布局 + 槽位 + 装配结果）。
- **约束**：
  - 仅当用户明确说"大屏/dashboard/看板/数据驾驶舱/监控大屏/可视化大屏/可视化看板"触发（铁律 3）。
  - 须先过【丰富度门槛】（图表覆盖 ≥4 种视角）才具备资格；未达标走渐进式深挖。
  - 排版/配色交由本工具，agent 不指定骨架（铁律 5）。
- **现状**：`dashboard/` 下有 layout_engine / widget_generator 等，需封装为工具接 ToolResult。

---

## tools_registry.py 对接要求（给实现方/自己）

- 提供 `get_tool(name: str) -> callable` 与 `list_tools() -> list[str]`。
- 每个工具签名统一为 `tool(**kwargs) -> ToolResult`。
- 工具名集合必须 == {profile_data, run_python, run_template, run_analysis, generate_chart, generate_report, build_dashboard}。
- ReAct 循环通过 `list_tools()` 把工具清单注入 LLM function-calling schema；通过 `get_tool(name)` 执行。
- 所有工具返回统一经 `ToolResult` 序列化后回填 LLM，缺失字段填默认值（空 list / None）。
