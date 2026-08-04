# DataMind 数据分析报告 + 可视化大屏 双流架构改造 PRD

> 版本：v0.1（草案）
> 日期：2026-08-04
> 状态：前两个决策已拍板，第三个边界标注待最终确认

## 1. 背景与现状

### 1.1 现状（代码确认）
- 后端每个分析模型（cohort / rfm / sku_seg / geo_seg / activity_seg / category_seg / churn_seg / CLV / churn_rule / funnel / user_profile / association_rules，共 12 个）跑完 → 生成 `AnalysisPackage`，含：`kpis`(指标卡片)、`insights`(数据洞察)、`conclusions`(分析结论)、`recommendations`(建议)、`findings`(业务发现)、`charts`(已渲染 echarts option)、`chart_data`(图表元数据)。
- **报告 LLM**：`agent.generate_report_from_packages` + `ReportBuilder`，输入 = 全量 package，只组织语言写报告，不重算、不碰 DataFrame。
- **大屏**：`dashboard.py` 直接下发 package 的 `charts` option 渲染，**当前渲染所有图**，侧边仅 `/dashboard/schema/naming`（dashboard.py:571–593）用一次 LLM 起标题。
- **分析阶段 LLM**：`generate_insights`（agent.py:176）产出 insights 文字，存进 package，**大屏（图表旁文字）与报告（分析素材）共用**——属于共享上游，非大屏专属。

### 1.2 三个待解决痛点（用户痛点）
1. **无分类标签**：backend 全量搜 `layout_size | classification | simple | complex` = **0 命中**。无法做"简单图放大屏、复杂图放报告"的展示分发。
2. **报告输出结构不对**：`ReportBuilder.SECTION_ORDER` 是一维 section 列表（趋势/排名/结构…），不是用户要的"复杂图区 / 大屏图延伸区 / 全局总结"三块。
3. **套话透传**：`ReportBuilder._extract_package` 把 `findings / recommendations` 原样透传（report_builder.py:159–163, 307–348）；聚类模型（kmeans.py:777、user_profile.py:264）的 findings 是模板套话（"可针对该群体制定差异化运营策略"），会原样进 prompt，若 LLM 不处理就透传给用户。RFM 因手写业务规则质量最高。

## 2. 目标架构

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
                  大屏接口 (/dashboard)            报告接口 (/report)
            simple 图 + layout_size          复杂图+解读 / 大屏图纯文字 / 全局总结
```

### 2.2 两个独立 LLM（边界）
- **报告 LLM**（写报告）：`generate_report_from_packages`，吃全量 package。
- **大屏 LLM**（可视化大屏）：推断 = `naming`（dashboard.py:571–593，大屏专属起标题）。
- **分析阶段共享 LLM**：`generate_insights`（agent.py:176），产 insights 被大屏 + 报告共用，非"大屏专属"，归类为共享上游。
- **新增分类层**：规则 + LLM 兜底（见 4.1），独立于上述两个 LLM。

> ⚠️ **待最终确认**：用户所说"大屏 LLM"是否即命名（naming）。若指 `generate_insights`，则"两个 LLM 分开"需重新表述为"报告 LLM 独立于分析阶段 insights LLM"，架构图边界相应调整。**此事不影响改造清单**，仅影响 PRD 架构图描述。

## 3. 已拍板决策
| 项 | 决策 |
|---|---|
| 分类打标方式 | 规则 + LLM 兜底（确定性阈值粗分 + LLM 调边界 case） |
| 报告三块格式 | JSON（好解析、好降级） |
| 大屏 LLM 边界 | 推断 = naming，待最终确认 |

## 4. 后端改造清单

### 4.1 新增分类层（triage）
- **输入**：全量 package 的 `chart_data`（仅元数据 slot/type/title/x/y/data_count，不取 data 明细 —— `_safe_chart_data` 已实现剥离）。
- **规则粗分**（确定性阈值，举例）：
  - 桑基图 / 力导向图 `nodes > 50` 或 跨维度 `> 3` → `complex`
  - 饼 / 柱 / 线 单系列、类别数 `< 10` → `simple`
- **LLM 兜底**：对规则置信度低的边界 case 微调 `tier`；`simple` 时给定 `layout_size` 枚举（`third` / `half` / `full`）。
- **输出**：`{chart_id, tier, layout_size}` 列表，存缓存绑 Task_ID，大屏接口与报告接口共用。
- **评测**：见第 6 节（分类准确率 ≥ 95%）。

### 4.2 改造 dashboard 接口
- 从缓存取 `tier=simple` 图的**完整 option/data** + `layout_size`。
- 剔除 `complex` 图、剔除所有长段分析文本。
- 返回：核心 KPI + simple 图（data + layout_size）。极简、高性能。

### 4.3 改造 report 接口 + ReportBuilder + agent prompt
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
- 沿用现有 SessionManager / 异步机制；分类层、报告 LLM 在 Task 完成后跑；前端轮询拉取。
- 缓存：Redis（不可用时退回本地 / 文件）；`Task_ID` 设 TTL 防内存爆；并发锁防重复计算。

## 5. 前端改造清单
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
1. 大屏 LLM 边界（naming vs generate_insights）—— 影响架构图描述。
2. 报告延伸区是否配静态缩略图 —— 影响前端工作量。
