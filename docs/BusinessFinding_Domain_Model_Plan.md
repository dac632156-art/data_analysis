# BusinessFinding 领域模型引入计划书

## 一、背景与问题

### 1.1 传统分析系统的局限性

在传统的数据分析系统中，分析结果通常以自然语言字符串的形式保存和传递：

`
findings = [
    "华东同比下降12%",
    "TOP3贡献91%",
    "复购率27%"
]
`

这种设计存在四个核心问题：

**① 语义不可解析**：字符串中"华东""下降12%""TOP3""复购率"各自承载不同的业务语义，但系统无法程序化地识别出"华东"是一个实体（entity）、"-12%"是变化率（change_pct）、"TOP3"是一个排名发现（ranking）。

**② 证据无法关联**："华东下降12%"这个发现来自于哪张趋势图（chart）？从哪个明细表（table）可以验证？对应的 KPI 是"平均同比下降率"吗？字符串无法回答这些问题，导致 Professional Report 无法自动插图和引用。

**③ 难以跨分析推理**：当有 10 个不同分析类型（增长、排名、复购、异常……）的 findings 时，字符串无法支持跨分析关联推理。例如"复购率低" + "华东下降" → "华东客户流失导致复购率低"——这种因果关系只能靠人脑串联，系统无法自动完成。

**④ 不可扩展**：新增一种分析指标（如 CLV、RFM），意味着新模板、新字符串、新消费方——每一环都要修改。缺乏统一的数据契约。

### 1.2 项目定位

DataMind AI V3 是面向企业管理层的数据分析平台，核心目标不仅是"生成图表"，更是"产出可执行洞察"。

最终架构：

`
Business Calculator     （业务计算引擎）
        ↓
Analysis Template       （分析模板）
        ↓
BusinessFinding         （统一业务发现）  ← 本文档核心
        ↓
AnalysisPackage         （分析结果包）
        ↓
Business Reasoning      （业务推理管道）
        ↓
ReasoningResult         （推理结果）
        ↓
Professional Report     （专业分析报告）
`

因此，必须将分析结论从"文本"升级为"业务事实（Business Fact）"，建立全系统统一的领域模型。

---

## 二、领域模型设计

### 2.1 BusinessFinding 定义

**BusinessFinding（业务发现）** 是本项目唯一的分析结果领域模型。每一个 BusinessFinding 代表一条经过计算验证的业务事实。

它不是简单的 dataclass，而是封装业务行为的**领域对象**（Domain Object），同时具备数据承载和行为封装两种能力。

### 2.2 数据结构

BusinessFinding 采用三层架构：

`
┌──────────────────────────────────────────────┐
│  标识层（Identity）                           │
│  · id             唯一标识（UUID）            │
│  · analysis_type  分析类型（growth_analysis）  │
│  · category       发现分类（FindingCategory）  │
├──────────────────────────────────────────────┤
│  事实层（Facts）                              │
│  · title          简短标题："华东同比下降12%"  │
│  · description    详细描述（2-3句业务语言）     │
│  · metric         指标："销售额"               │
│  · dimension      维度：时间/分类列名           │
│  · entity         业务实体："华东" / "产品A"   │
│  · value          核心数值：-12.0              │
│  · unit           单位："%" / "元" / "次"      │
│  · direction      方向：up / down / flat       │
│  · change_pct     变化率：相对于基准的百分比     │
├──────────────────────────────────────────────┤
│  解释层（Interpretation）                     │
│  · severity        严重程度（critical~info）    │
│  · confidence      置信度（0.0-1.0）           │
│  · business_meaning  业务含义                  │
│  · business_impact   业务影响                  │
│  · recommendation    可执行建议                │
│  · evidence          证据引用（EvidenceRef）    │
└──────────────────────────────────────────────┘
`

### 2.3 枚举体系

| 枚举 | 作用 | 取值范围 |
|------|------|---------|
| FindingCategory | 发现分类（对应 YAML 的 intent） | growth, ranking, comparison, concentration, distribution, correlation, anomaly, retention, structure, proportion, geo, risk, opportunity, insight, summary |
| Direction | 趋势方向 | up, down, flat, unknown |
| Severity | 严重程度 | critical, high, medium, low, info |

### 2.4 证据引用（EvidenceRef）

EvidenceRef 是轻量级值对象，不持有图表/表格/KPI 对象本身，只保存引用标识：

`python
EvidenceRef(
    chart_slots=("trend", "growth_rate"),      # ChartData.slot
    table_titles=("增长率明细",),                # TableData.title
    kpi_labels=("平均同比增长率",)               # KPIItem.label
)
`

消费方（如 Professional Report）通过引用标识在 AnalysisPackage 中查找对应对象，实现自动插图和引用。

### 2.5 行为方法

BusinessFinding 采用 **frozen（不可变）** 设计，保证数据一致性。修改通过 eplace() 创建新实例。

| 方法 | 用途 |
|------|------|
| 	o_prompt() | 输出适合 LLM 理解的结构化文本 |
| 	o_report() | 输出 Professional Report 可引用的结构化数据（含 evidence） |
| 	o_dashboard() | 输出 Dashboard 精简摘要 |
| 	o_dict() | 完整序列化 |
| merge(findings) | 合并多个同类 Finding（多增长分析 → 一个综合 Growth Finding） |
| link_evidence(slots, titles, labels) | 建立 Finding → Chart/Table/KPI 的证据引用 |

---

## 三、创建工厂（FindingFactory）

为保证字段完整性和数据一致性，所有 Template 不直接实例化 BusinessFinding，而是通过统一的 **FindingFactory** 创建。

Factory 提供语义化的创建方法，每个方法对应一种业务发现类型：

| 工厂方法 | 创建什么 | 自动设置的默认值 |
|---------|---------|-----------------|
| actory.growth() | 增长发现 | category=GROWTH, unit="%", direction=DOWN/UP |
| actory.ranking() | 排名发现 | category=RANKING |
| actory.concentration() | 集中度发现 | category=CONCENTRATION |
| actory.anomaly() | 异常发现 | category=ANOMALY, severity=HIGH, confidence=0.85 |
| actory.retention() | 复购发现 | category=RETENTION, metric="复购率" |
| actory.comparison() | 对比发现 | category=COMPARISON |
| actory.correlation() | 相关发现 | category=CORRELATION |
| actory.risk() | 风险发现 | category=RISK, severity=HIGH |
| actory.opportunity() | 机会发现 | category=OPPORTUNITY |
| actory.summary() | 摘要发现 | category=SUMMARY, severity=INFO |

---

## 四、模块职责重新划分

引入 Domain Model 后，各模块职责更加清晰：

| 模块 | 输入 | 输出 | 职责 |
|------|------|------|------|
| **Business Calculator** | DataFrame | BusinessMetrics | 纯业务计算：YoY/MoM/HHI/CR5/复购率等 |
| **Analysis Template** | BusinessMetrics | List[BusinessFinding] | 将计算结果转化为业务事实，通过 Factory 创建 |
| **AnalysisPackage** | List[BusinessFinding] + KPI + Table + Chart | 统一分析结果包 | 聚合所有分析产出，提供统一消费接口 |
| **Reasoning Pipeline** | List[AnalysisPackage] | ReasoningResult | 跨分析推理：根因分析、因果链、故事线 |
| **Professional Report** | ReasoningResult + AnalysisPackage | 报告文档 | 基于 EvidenceRef 自动插图/引用/KPI |
| **Dashboard** | AnalysisPackage | 可视化 UI | 调用 to_dashboard() 获取摘要 |

---

## 五、Template 示例

以 GrowthAnalysis 为例，展示 Template 如何使用 Domain Model：

`python
def build_findings(self, df, dimension, metric, algorithm, kpis, chart_data):
    """V3 Domain Model：使用 FindingFactory 创建业务发现"""
    m = self._cache.get("metrics")
    f = self.factory  # FindingFactory("growth_analysis")
    findings = []

    avg_growth = m.growth_rate_avg
    trend_dir = Direction.UP if avg_growth > 0 else Direction.DOWN

    # 事实 1：整体趋势
    findings.append(f.growth(
        entity="全量", metric=metric, value=avg_growth, unit="%",
        direction=trend_dir, confidence=0.95,
        business_meaning=f"{metric}呈{'上升' if avg_growth > 0 else '下降'}趋势",
        business_impact=f"预期下一周期增长率约为{avg_growth:+.1f}%"
    ))

    # 事实 2：峰值
    findings.append(f.ranking(entity="2024-06", metric=metric, value=1250000, rank=1))

    # 事实 3：趋势拐点检测
    if m.trend_change_points:
        findings.append(f.anomaly(
            entity="2024-Q3", title="检测到2个趋势拐点",
            severity=Severity.MEDIUM,
            business_meaning="趋势方向发生变化，需关注原因"
        ))

    # 事实 4：风险评估
    if avg_growth < -5:
        findings.append(f.risk("指标持续下滑，需警惕",
            recommendation="排查下滑原因，制定应对方案"))

    return findings
`

关键设计：
- 不再返回 List[str]，只返回 List[BusinessFinding]
- 不再手动构建 EvidenceLink——证据链接由基类 execute() 自动完成
- uild_insights() / uild_conclusion() 由基类从 findings 自动派生（向后兼容）

---

## 六、数据流全景

`
┌────────────────────────────────────────────────────────────────────┐
│                        DataMind AI V3 数据流                       │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  User Question: "华东销售怎么样？"                                  │
│       ↓                                                            │
│  Planner → AnalysisLibrary.lookup("增长趋势")                       │
│       ↓                                                            │
│  GrowthAnalysis.execute(df, "日期", "销售额", "yoy")                │
│       ↓                                                            │
│  ┌──────────────────────────────────────┐                          │
│  │ GrowthCalculator.execute()           │  ← Business Calculator   │
│  │ → BusinessMetrics                    │                          │
│  │   · yoy: [-12%, 3%, 8%, ...]        │                          │
│  │   · moving_avg: [...]               │                          │
│  │   · cumulative: [...]               │                          │
│  └──────────────────────────────────────┘                          │
│       ↓                                                            │
│  ┌──────────────────────────────────────┐                          │
│  │ Template.build_findings()            │  ← Factory 创建          │
│  │ → [BusinessFinding, ...]             │                          │
│  │   Finding 1: 全量销售额 yoy -3.2%    │                          │
│  │   Finding 2: 华东增长最慢 (-12%)     │                          │
│  │   Finding 3: 3个趋势拐点             │                          │
│  │   Finding 4: 风险-需关注华东下滑      │                          │
│  └──────────────────────────────────────┘                          │
│       ↓                                                            │
│  ┌──────────────────────────────────────┐                          │
│  │ AnalysisPackage                      │  ← 聚合层                │
│  │ · findings    (Domain)               │                          │
│  │ · kpis        (UI)                  │                          │
│  │ · charts      (UI)                  │                          │
│  │ · tables      (UI)                  │                          │
│  │ · insights    (兼容，自动派生)        │                          │
│  └──────────────────────────────────────┘                          │
│       ↓                                                            │
│  ┌───────────┐  ┌───────────┐  ┌───────────────┐                  │
│  │ Dashboard │  │ Report    │  │ Reasoning     │                  │
│  │ to_dash-  │  │ to_report │  │ Engine        │                  │
│  │ board()   │  │ ()        │  │ to_prompt()   │                  │
│  └───────────┘  └───────────┘  └───────────────┘                  │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
`

---

## 七、价值总结

### 7.1 解决了什么

| 问题 | 解决方案 |
|------|---------|
| 字符串无法程序化理解 | BusinessFinding 字段明确标识 entity / metric / value / direction |
| 证据无法关联 | EvidenceRef 建立 Finding → Chart/Table/KPI 的三向引用 |
| 跨分析推理困难 | 统一 Domain Model + merge() 支持多 finding 合并和跨分析关联 |
| 不可扩展 | 新增分析类型只需新增 Factory 方法，所有下游模块自动兼容 |

### 7.2 对后续模块的价值

| 下游模块 | 如何消费 BusinessFinding |
|---------|------------------------|
| **Reasoning Engine** | 调用 	o_prompt() 获取结构化文本嵌入 LLM Prompt；通过 category/severity 字段过滤和排序 |
| **Professional Report** | 调用 	o_report() 获取完整数据；通过 evidence 的引用标识自动查找对应图表/KPI 进行插图 |
| **Dashboard** | 调用 	o_dashboard() 获取精简摘要；按 severity 渲染严重程度标签 |
| **API** | 调用 	o_dict() 完整序列化为 JSON 返回前端 |

### 7.3 与项目架构的关系

BusinessFinding 是整个 DataMind V3 的核心数据契约。它向上承接 Business Calculator 的计算结果和 Analysis Template 的业务组织，向下提供给 Reasoning Engine、Report、Dashboard 统一的消费接口。

通过引入领域模型，本项目实现了分析结果的**完全结构化**，为后续业务推理、专业报告生成以及智能 Agent 能力提供了统一的数据基础。