# DataMind 数据分析报告 + 可视化大屏 双流架构重建 PRD

> 版本：v0.2（重建版）
> 日期：2026-08-04
> 状态：前两个决策已拍板；方向从"改造现有 router"升级为"删除旧视图、从零重建"。「大屏 LLM 指哪个」问题已作废。

## 0. 方向说明（重要变更）

用户决定：**删除当前项目中的可视化大屏与分析报告，从零重建**。因此本文档不再沿用"改造 dashboard.py / report.py"的视角，而是以"新建两个视图 + 拆分两个独立 LLM"为基线。

- 保留的资产（不删）：`AnalysisPackage` 生成管线（12 个分析模型）、`ReportBuilder` 的 prompt 组装逻辑与 token 安全剥离做法（`_safe_chart_data`）、底层 LLM 调用与 SessionManager 异步机制。
- 删除并重建的资产（旧视图）：前端大屏页、前端报告页、后端大屏接口、后端报告接口——重建时按本 PRD 的双流架构重写。
- 硬设计约束：**生成可视化大屏的 LLM 与生成数据分析报告的 LLM 是两个独立的 LLM**，重做时即需拆清职责（不再贴着现有 naming/generate_insights 区分）。

## 1. 背景与现状

### 1.1 保留的数据基座（代码确认，重建后仍生效）
- 后端每个分析模型（cohort / rfm / sku_seg / geo_seg / activity_seg / category_seg / churn_seg / CLV / churn_rule / funnel / user_profile / association_rules，共 12 个）跑完 → 生成 `AnalysisPackage`，含：`kpis`(指标卡片)、`insights`(数据洞察)、`conclusions`(分析结论)、`recommendations`(建议)、`findings`(业务发现)、`charts`(已渲染 echarts option)、`chart_data`(图表元数据)。
- **图表信息剥离（token 安全，沿用）**：`ReportBuilder._safe_chart_data` 只给图表 `slot/type/title/x/y/data_count`，**不传 data 明细数组**——天然规避 token 爆炸 + 防幻觉；LLM 分析图表靠 package 内已算好的 `insights/conclusions/findings` 文字。

### 1.2 三个待解决痛点（重建要解决）
1. **无分类标签**：backend 全量搜 `layout_size | classification | simple | complex` = **0 命中**。无法做"简单图放大屏、复杂图放报告"的展示分发。
2. **报告输出结构不对**：`ReportBuilder.SECTION_ORDER` 是一维 section 列表（趋势/排名/结构…），不是用户要的"复杂图区 / 大屏图延伸区 / 全局总结"三块。
3. **套话透传**：`ReportBuilder._extract_package` 把 `findings / recommendations` 原样透传；聚类模型（kmeans.py:777、user_profile.py:264）的 findings 是模板套话（"可针对该群体制定差异化运营策略"），会原样进 prompt，若 LLM 不处理就透传给用户。RFM 因手写业务规则质量最高。

## 2. 目标架构（重建版）

### 2.1 核心数据流
```
原始数据 → 清洗 → 12 个分析模型 → AnalysisPackage（全量：图表 option + 文字结论）
                                         │
                                   缓存（绑 Task_ID）
                                         │
                           ┌─────────────┴──────────────┐
                      分类层 (triage)              报告 LLM（吃全量）
                  tier + layout_size                  三块 JSON
                           │                              │
              大屏视图 (前端+大屏LLM)            报告视图 (前端+报告LLM)
            simple 图 + layout_size          复杂图+解读 / 大屏图纯文字 / 全局总结
```

### 2.2 两个独立 LLM（重建硬约束）
- **报告 LLM**：职责 = 读全量 package → 输出结构化三块报告（复杂图解读 / 大屏图纯文字延伸 / 全局总结）。输入全量、输出三块 JSON。
- **大屏 LLM**：职责 = 为可视化大屏产出大屏专属内容（如图表标题/命名、大屏叙事文案等）。**与报告 LLM 是两套独立调用、独立 prompt、独立职责**，重做时即明确拆分。
- **分析阶段共享 LLM**（可选保留）：`generate_insights` 类产出，作为大屏与报告的共享上游文字原料，存在 package 内。
- **新增分类层**：规则 + LLM 兜底（见 4.1），独立于上述两个视图 LLM。

> 说明：旧方案中"大屏 LLM 指 naming 还是 generate_insights"的边界讨论**已作废**——本次为重建，两个 LLM 的职责在重建时直接按上述定义拆分，不依赖旧代码区分。

## 3. 已拍板决策
| 项 | 决策 |
|---|---|
| 分类打标方式 | 规则 + LLM 兜底（确定性阈值粗分 + LLM 调边界 case） |
| 报告三块格式 | JSON（好解析、好降级） |
| 视图重建策略 | 删除旧大屏/报告视图，新建双流视图 |
| 两个 LLM 关系 | 大屏 LLM 与报告 LLM 独立拆分（硬约束） |

## 4. 后端重建清单

### 4.1 新增分类层（triage）
- **输入**：全量 package 的 `chart_data`（仅元数据 slot/type/title/x/y/data_count，不取 data 明细 —— `_safe_chart_data` 已实现剥离）。
- **规则粗分**（确定性阈值，举例）：
  - 桑基图 / 力导向图 `nodes > 50` 或 跨维度 `> 3` → `complex`
  - 饼 / 柱 / 线 单系列、类别数 `< 10` → `simple`
- **LLM 兜底**：对规则置信度低的边界 case 微调 `tier`；`simple` 时给定 `layout_size` 枚举（`third` / `half` / `full`）。
- **输出**：`{chart_id, tier, layout_size}` 列表，存缓存绑 Task_ID，大屏视图与报告视图共用。
- **评测**：见第 6 节（分类准确率 ≥ 95%）。

### 4.2 重建大屏接口 + 大屏 LLM
- 从缓存取 `tier=simple` 图的**完整 option/data** + `layout_size`。
- 剔除 `complex` 图、剔除所有长段分析文本 → 极简、高性能。
- 大屏 LLM：独立调用，为大屏视图产出专属内容（命名/叙事等），与报告 LLM 隔离。

### 4.3 重建报告接口 + 报告 LLM + ReportBuilder 重构
报告 LLM 输出**结构化 JSON 三块**：
```json
{
  "complex_charts": [
    {"chart_id": "...", "render_ref": "缓存图表数据引用", "llm_interpretation": "深度解读..."}
  ],
  "dashboard_charts_text": [
    {"chart_id": "...", "text_interpretation": "纯文字延伸（前端不渲染图）"}
  ],
  "global_summary": {
    "problem": "发现业务问题...",
    "solution": "提出解决方案...",
    "expected_result": "应用后预期结果..."
  }
}
```
- **套话 grounding 改写**：system prompt 明确要求——"对模板化 / 套话式 `recommendation` / `finding`，结合本簇**真实画像数字**（已在 prompt 的 kpis/findings 内）改写为具体可执行建议；**禁止原样复述空话，禁止编造 package 外数字**"。
- **解析与降级**：JSON schema 校验；单图解读失败不拖垮整份报告（部分降级）；解析失败重试。

### 4.4 异步编排与缓存
- 沿用现有 SessionManager / 异步机制；分类层、报告 LLM、大屏 LLM 在 Task 完成后跑；前端轮询拉取。
- 缓存：Redis（不可用时退回本地 / 文件）；`Task_ID` 设 TTL 防内存爆；并发锁防重复计算。

## 5. 前端重建清单
- **大屏页**：按 `layout_size` 排版 simple 图（third / half / full）。
- **报告页**：三块渲染 —— 复杂图渲染 + 文字 / 大屏图纯文字（可配静态缩略图给上下文）/ 全局总结 Markdown。
- **路由**：独立路由 + 共享 Task_ID（推荐）；同屏分栏为备选（大屏侧用只读快照降性能开销）。

## 6. 离线评测（两次部署）
- **测试集**：用户"全能模型验证测试集"（7205 行 × 28 列，命中 12 模型）。
- **评测项**：
  1. 分类准确率：人工标注每张图 expected simple/complex，对比分类层输出，建议 ≥ 95%。
  2. 摘要忠实度：`global_summary` 中数字 100% 命中缓存 KPI，无编造（可加二次校验：生成数值与缓存比对，超阈值标红 / 重写）。
- **流程**：离线评测合格 → 线上部署（共两次部署）。

## 7. 诚实边界（简历 / 面试）
- 套话改写 = **LLM 基于真实数据"生成"建议**，非后端"算出的确定性结论"。
- ❌ 简历 / 面试禁说"系统自动生成了高质量的差异化运营策略"。
- ✅ 准确措辞："LLM 基于聚类画像与业务规则，将模板化结论改写为可读运营建议，并强制 grounding 防幻觉"。
- 聚类 findings 在代码里是**模板套话**（kmeans / user_profile），面试被问"聚类分析怎么做的"要能老实说"聚类用 KMeans，业务建议是规则模板 / LLM 改写，非深度定制"。

## 8. 待确认项
1. 报告延伸区是否配静态缩略图 —— 影响前端工作量。
2. 大屏 LLM 重建后的具体职责范围（仅命名 / 含大屏叙事文案 / 其他）—— 影响 prompt 与接口设计。
3. 前端大屏与报告的形态（独立路由 / 同屏分栏）—— 见 5 节。
