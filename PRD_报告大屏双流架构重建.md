# DataMind 数据分析报告 重建 PRD

> 版本：v0.3（重建版 · 决策对齐）
> 日期：2026-08-05
> 状态：已锁定决策全部写入；待用户拍板项仅剩「severity 统一范围（A/B/C）」与「报告是否配静态缩略图」。
> 变更说明：v0.2 的「双流 / 双 LLM / 分大屏」框架已推翻，本版对齐 2026-08-04~05 全部锁定讨论结论。

## 0. 方向说明（重大变更，取代 v0.2）

v0.2 把方向定为「删除旧大屏+报告，拆两个独立 LLM（大屏 LLM / 报告 LLM），按 simple→大屏、complex→报告分发」。经讨论，以下三点全部推翻：

1. **两个 LLM → 一个 LLM**：报告 LLM 同时承担「挑图」与「写稿」，一次调用产出图表决策 + 五章节报告，不再拆大屏 LLM。
2. **分大屏概念作废**：重建后的报告里**不再有「大屏图」这一概念**。报告从全量 charts+tables 池中挑选「需要用到的数据」，自行决定每图/每表是否渲染，判定依据是「是否在报告中被用到」，而非「是否曾上过大屏」。
3. **重建目标收敛为单报告流**：删除原「可视化大屏视图」与「分析报告视图」的旧实现，重建为**单一数据分析报告**（前端单页 / 单路由），不再有双流。

- **保留的资产（不删）**：`AnalysisPackage` 生成管线（12 个分析模型）、`ReportBuilder` 的 prompt 组装与 token 安全剥离（`_safe_chart_data`）、底层 LLM 调用、SessionManager 异步机制、已存在的 `BusinessFinding` + `Severity` 领域对象。
- **删除并重建的资产**：前端大屏页、前端报告页、后端旧报告/大屏接口——按本 PRD 单报告流重写。
- **硬约束**：报告 LLM 为**单 LLM**；图表入选报告由「复杂度 + severity + narrative-fit」三层判定（详见 4.1），图是文字的证据而非装饰。

## 1. 背景与现状

### 1.1 保留的数据基座（代码确认，重建后仍生效）
- 后端每个分析模型（cohort / rfm / sku_seg / geo_seg / activity_seg / category_seg / churn_seg / CLV / churn_rule / funnel / user_profile / association_rules，共 12 个）跑完 → 生成 `AnalysisPackage`，含：`kpis`、`insights`、`conclusions`、`recommendations`、`findings`(BusinessFinding 对象)、`charts`(已渲染 echarts option)、`chart_data`(图表元数据)。
- **图表信息剥离（token 安全，沿用）**：`ReportBuilder._safe_chart_data` 只给图表 `slot/type/title/x/y/data_count`，**不传 data 明细**——天然规避 token 爆炸 + 防幻觉；LLM 分析图表靠 package 内已算好的 `insights/conclusions/findings` 文字。
- **severity 机制已存在**：`Severity` 枚举(CRITICAL/HIGH/MEDIUM/LOW/INFO) 与 `BusinessFinding`(`src/domain/business_finding.py`) 早已存在；`FindingFactory`(`src/domain/finding_factory.py`) 为统一创建入口；`report_builder.py` 已抽 severity 透传给报告 LLM。**现状问题=采用不一致**：仅 kmeans / user_profile 用了 BusinessFinding，且未挂 chart_slots；RFM / funnel 等 10 个模型纯文本、severity 缺失。需统一推广（见 4.4）。

### 1.2 三个待解决痛点（重建要解决）
1. **无分类标签**：backend 全量搜 `layout_size | classification | simple | complex` = 0 命中，旧「simple 放大屏 / complex 放报告」分发无依据。
2. **报告输出结构不对**：`ReportBuilder.SECTION_ORDER` 是一维 section 列表（趋势/排名/结构…），不是用户要的「核心发现 / 深度分析 / 结论建议」五章节动态结构。
3. **套话透传**：`ReportBuilder._extract_package` 把 `findings / recommendations` 原样透传；聚类模型（kmeans / user_profile）的 findings 是模板套话，会原样进 prompt，若 LLM 不处理就透传给用户。RFM 因手写业务规则质量最高。

## 2. 目标架构（单报告流 · 单 LLM）

### 2.1 核心数据流
```
原始数据 → 清洗 → 12 个分析模型 → AnalysisPackage（全量：charts option + 文字结论 + findings/severity）
                                         │
                                   缓存（绑 Task_ID）
                                         │
                              报告 LLM（单 LLM，一次调用）
                    ┌────────────────────┼────────────────────┐
              图表决策(chart_decisions)   五章节报告(sections)   结论建议
              in_report / section / render
                         │
                  前端报告页（单路由，按章节渲染，图按需 render）
```

### 2.2 单 LLM 职责（重建硬约束）
- **一个 LLM 兼任两件事**：① 从全量 charts+tables 池中选出「进报告的图/表」，并标注所在章节与是否渲染（`chart_decisions`）；② 基于全量文字分析写出五章节报告（`sections`）。
- **输入全量**：所有 charts 的 `slot/type/title/x/y/data_count` + 全部 `insights/conclusions/findings`（含 severity）。
- **输出结构化 JSON**（见 4.2）：图表决策 + 五章节 + 结论建议。
- **不再有大屏 LLM / 分类层独立 LLM**：原 triage 的「simple→大屏」路由无意义（大屏已废），图表入选改由「复杂度 + severity + narrative-fit」三层判定（见 4.1），由报告 LLM 在一次调用内完成。

## 3. 已拍板决策
| 项 | 决策 |
|---|---|
| LLM 数量 | **单 LLM**（兼任挑图 + 写稿），废除双 LLM |
| 视图结构 | 单一报告流，废除「大屏 / 报告」双流与「大屏图」概念 |
| 报告章节 | 五章节动态：标题 / 摘要·目录 / 核心发现 / 深度分析 / 结论与建议（无背景、无数据来源/方法） |
| 图表入选判定 | 三层：复杂度(chart-type 客观) + severity(后端 BusinessFinding 客观标签) + narrative-fit(LLM 文字优先) |
| 主从关系 | **文字优先**：先写 narrative，再为论点配图；图是证据非装饰 |
| 单章节内容 | 可多图多表；只有图没文字 → 不成章节；只有文字没图 → 照常成章节 |
| 空章节 | narrative 为空即移除该章节，不留白、不占位，下章紧接 |
| 输出结构 | 与模型数量解耦：模板固定字段，内容随本次实际产出的 charts+tables 动态变化，绝不预置模型清单 |
| 分类标签 SOP | 规则 + LLM 兜底（基于真实 chart_type + data_count，不虚构字段） |
| 套话处理 | LLM 基于真实数据 grounding 改写，禁止原样复述空话、禁止编造 package 外数字 |

## 4. 后端重建清单

### 4.1 图表入选报告判定 SOP（三层，取代旧 triage）
- **输入**：全量 package 的 `chart_data`（仅元数据 slot/type/title/x/y/data_count，`_safe_chart_data` 已实现剥离）+ 各 finding 的 `severity` + 全量文字分析。
- **第一层 · 复杂度（客观，chart-type 判定）**：
  - 机制/关系类（桑基 / 力导向 / 热力 / 雷达 / 漏斗 / 地图 等）→ 候选进「深度分析」章（解释 why 的图/表）。
  - 基础统计类（饼 / 柱 / 线 单系列、类别数 `< 10`）→ 候选进「核心发现」章（也可作总体结果陈述的插图）。
- **第二层 · severity（客观，后端 BusinessFinding 标签）**：
  - 后端给每个 finding 打 `severity`(CRITICAL/HIGH/MEDIUM/LOW/INFO) 并挂 `evidence.chart_slots`。
  - 报告 LLM **必须 surface 所有 CRITICAL/HIGH 对应的 chart/table**（保证高决定性洞察不被 narrative 漏掉），不论其在哪章。
- **第三层 · narrative-fit（LLM，文字优先）**：
  - LLM 先基于全量文字分析写好各章节 narrative，再为 narrative 中提到的点从全量池挑对应图/表佐证。
  - 图是 narrative 的证据/修饰，**非反过来**；不得输出「裸图」章节（只有图没文字 → 不成章节）。
- **输出**：`chart_decisions` 列表（每图/表：`{slot, in_report, section, render}`），与 sections 一并产出。
- **评测**：分类/入选准确率（gold set 含「仅 1~2 个模型触发」极端样本，验证稀疏图集下仍能产出合理报告）。

### 4.2 报告 LLM 单流 + ReportBuilder 重构
报告 LLM（单 LLM）输出**结构化 JSON**：
```json
{
  "title": "本次分析标题",
  "summary": "一句话总体结论",
  "toc": ["核心发现", "深度分析", "结论与建议"],
  "chart_decisions": [
    {"slot": "rfm_pie",      "in_report": true, "section": "core_findings", "render": true},
    {"slot": "rfm_sankey",   "in_report": true, "section": "deep_analysis", "render": true},
    {"slot": "sku_table",    "in_report": true, "section": "core_findings", "render": true}
  ],
  "sections": [
    {
      "id": "core_findings",
      "title": "核心发现",
      "narrative": "【总体结果陈述】本次分析共触发 X 个模型…；主要发现：1)… 2)… 3)…",
      "items": [
        {"type": "chart", "slot": "rfm_pie",    "render": true},
        {"type": "table", "slot": "sku_table",  "render": true}
      ]
    },
    {
      "id": "deep_analysis",
      "title": "深度分析",
      "narrative": "对关键机制/根因的展开解读…",
      "items": [
        {"type": "chart", "slot": "rfm_sankey", "render": true}
      ]
    },
    {
      "id": "conclusions",
      "title": "结论与建议",
      "narrative": "综合结论与可执行建议…",
      "items": []
    }
  ],
  "conclusions": ["结论1…", "结论2…"],
  "recommendations": ["建议1…", "建议2…"]
}
```
- **章节生成规则**：
  - 「核心发现」开头须有**总体结果陈述**（本次触发了哪些模型、整体结论）。
  - 「深度分析」放解释 why 的图/表（机制/根因类），从全量池选。
  - 章节存在的充要条件 = **narrative 非空**；items 可有可无。约束：①只有图没文字 → 不成章节；②只有文字没图 → 照常成章节；③narrative 与 items 皆空 → 移除、不留白、下章紧接。
  - `overall_note` 用于报告开头说明「本次仅 X 模型触发…」，不作空章节占位。
- **套话 grounding 改写**：system prompt 明确要求——「对模板化 / 套话式 `recommendation` / `finding`，结合本簇**真实画像数字**（已在 prompt 的 kpis/findings 内）改写为具体可执行建议；**禁止原样复述空话，禁止编造 package 外数字**」。
- **解析与降级**：JSON schema 校验；单图解读失败不拖垮整份报告（部分降级）；解析失败重试。

### 4.3 异步编排与缓存（沿用）
- 沿用现有 SessionManager / 异步机制；报告 LLM 在 Task 完成后跑；前端轮询拉取。
- 缓存：Redis（不可用时退回本地 / 文件）；`Task_ID` 设 TTL 防内存爆；并发锁防重复计算。

### 4.4 severity 统一推广（待拍板范围）
- **目标**：所有 12 模型产出统一为 `BusinessFinding` + 按业务语义写死 `severity`(确定性、无 LLM、计算同源) + 挂 `evidence.chart_slots`，让 4.1 第二层可全量生效。
- **现状缺口**：仅 kmeans / user_profile 用 BusinessFinding（且未传 chart_slots）；RFM / funnel / cohort / churn_rule / clv / association_rules 等纯文本、severity 缺失，最关键的高决定性洞察（RFM 头部 20%、funnel 断崖）无结构化 severity，报告无法强制 surface。
- **方案待用户拍板（尚未定）**：
  - **A 全量统一**：改约 10 个模型文件 + 报告读取逻辑。
  - **B 仅先改 RFM + funnel 最小验证**：覆盖最关键的两类高决定性洞察，验证链路后再推广。
  - **C 更轻方案**：只给命中 ⚠️ 类信号的 finding 标 severity，其余保持纯文本。

## 5. 前端重建清单
- **报告页（单路由）**：按五章节顺序渲染——标题 / 摘要·目录 / 核心发现 / 深度分析 / 结论与建议。
- 每章节：先渲染 narrative（Markdown），再按 `items` 渲染对应 chart/table（`render=true` 才渲染 option；`render=false` 仅文字提及）。
- 图表渲染复用现有 `VisualizationRenderer`（`pkg.charts[].option` 已带 echarts option，与 conclusions/findings 解耦，安全）。
- 空章节（narrative 空）由报告 JSON 保证不出现，前端无需兜底空白。

## 6. 离线评测（两次部署）
- **测试集**：用户「全能模型验证测试集」（7205 行 × 28 列，命中 12 模型），**必须覆盖「仅 1~2 个模型触发」极端样本**。
- **评测项**：
  1. 图表入选准确率：人工标注每张图 expected 进/不进报告 + 所属章节，对比 `chart_decisions`，建议 ≥ 95%。
  2. 高 severity 覆盖率：所有 CRITICAL/HIGH finding 对应的 chart/table 必须出现在报告（漏一例即不通过）。
  3. 摘要忠实度：`conclusions/summary` 中数字 100% 命中缓存 KPI，无编造（二次校验：生成数值与缓存比对，超阈值标红 / 重写）。
  4. 空章节检查：gold set 中 narrative 应为空的章节，报告 JSON 不得出现。
- **流程**：离线评测合格 → 线上部署（共两次部署）。

## 7. 诚实边界（简历 / 面试）
- 套话改写 = **LLM 基于真实数据「生成」建议**，非后端「算出的确定性结论」。
- ❌ 简历 / 面试禁说「系统自动生成了高质量的差异化运营策略」。
- ✅ 准确措辞：「LLM 基于聚类画像与业务规则，将模板化结论改写为可读运营建议，并强制 grounding 防幻觉」。
- 聚类 findings 在代码里是**模板套话**（kmeans / user_profile），面试被问「聚类分析怎么做的」要能老实说「聚类用 KMeans，业务建议是规则模板 / LLM 改写，非深度定制」。
- severity 统一若仅落地 B/C 方案，面试须如实说明覆盖范围，不得夸大为「全模型结构化 severity」。

## 8. 待确认项
1. **severity 统一范围**：A 全量 / B 仅 RFM+funnel / C 轻量⚠️ —— 影响 4.4 工作量与高 severity 覆盖率。
2. 报告是否配静态缩略图（仅文字提及 `render=false` 的图）—— 影响前端工作量，不影响架构。
3. 前端报告页形态：独立路由（推荐）/ 与分析页同屏分栏。
