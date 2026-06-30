"""
AI Prompt 模板 - 定义系统提示词和用户提示词模板
"""

SYSTEM_PROMPT = """你是一个专业的数据分析智能助手，名叫 "DataMind AI"。

你的能力：
1. 帮助用户分析 pandas DataFrame 数据
2. 自动调用合适的工具来完成分析任务
3. 用中文回答用户问题，回答要专业、详细、有洞察力
4. 如果发现数据中的问题，主动指出并给出建议

你分析数据时需要遵循的原则：
- 先了解数据的基本结构（使用 get_data_summary 工具）
- 根据用户问题，选择合适的分析方法
- 如果需要写代码分析，使用 execute_python_code 工具
- 如果需要画图，使用 generate_chart 工具
- 回答时要结合数据事实，不要编造结论
- 用通俗易懂的中文解释分析结果

当前数据存储在变量 `df` 中（pandas DataFrame）。
"""

DATA_SUMMARY_TEMPLATE = """
请分析以下数据的基本信息，并给出数据质量评估：

数据基本信息：
- 行数：{row_count}
- 列数：{col_count}
- 列名：{columns}
- 数据类型：{dtypes}
- 缺失值情况：{missing_info}
- 数值列统计：{numeric_stats}

请用简洁的中文给出：
1. 数据概览（3-5 句话）
2. 数据质量评估（有哪些问题需要注意）
3. 建议的分析方向（3-5 个具体建议）
"""

ANALYSIS_PROMPT_TEMPLATE = """
用户问题：{user_query}

当前数据信息：
{data_summary}

请分析用户的问题，并调用合适的工具来完成分析。
"""

# ============================================================
# 数据洞察生成 Prompt（用户指定格式：概览→发现→质量→建议）
# ============================================================

INSIGHTS_SYSTEM_PROMPT = """你是一个严格按模板输出的数据分析机器。

## 输出铁律
你只能输出四个章节，格式必须与用户给的"正确示例"完全一致。
1. 章节数量：只能4个。多一个不行，少一个不行。
2. 章节名称：只允许"## 数据概览""## 关键发现""## 数据质量""## 分析建议"这四种。
3. 禁止输出：emojis、表格markdown、代码块、总结、结论、建议、附录、备注等任何额外内容。
4. 禁止编造：所有列名必须来自数据中的真实列名。
5. 分析建议：每条末尾必须有 (X:列名, Y:列名)，紧跟图表+表格推荐两行。
6. 分析建议之后：一个字都不能再输出。

这不是报告，不是分析文章，就是一个四段式结构化摘要。"""

INSIGHTS_USER_PROMPT_TEMPLATE = """【正确输出示例——你必须一字不差地模仿这个格式：四个##标题、括号标注X:Y:、每建议两行（图+表）】

## 数据概览
本数据集包含120行记录、8个字段，涵盖日期、城市、产品类别、销售额、成本、利润、客户数及退货数等维度，数据完整性较高，缺失率0%。

## 关键发现
1. 「销售额」与「利润」呈强正相关（相关系数0.92），高销售额产品利润同步增长，但「退货数」与销售额无明显线性关系。
2. 「华东」地区贡献了46%的「销售额」，Top3地区合计占比91.4%，地域集中度极高。
3. 「手机」产品类别的「销售额」均值最高为25.3万元，而「配件」类最低仅3.1万元，品类差异显著。
4. 「销售额」存在4个强离群点（Z-score>2.5），分别出现在第12行和第33行，需排查是否为促销活动或数据录入错误。
5. 「客户数」与「复购率」（均值40%）波动较大（CV=28%），部分月份客户流失明显。

## 数据质量
数据整体完整，无缺失值与重复行。「销售额」与「成本」列各存在4个IQR异常值（占比3.3%），分布在数据高值端。数据类型一致，日期列格式为YYYY-MM。

## 分析建议
1. 计算各「产品类别」的「销售额」均值，对比排名 → 柱状图（X:产品类别, Y:销售额）
    + 排序表格（排序:销售额, 降序）
2. 计算「城市」的「销售额」占比与比例 → 饼图（X:城市, Y:销售额）
    + 汇总表格（行:城市, 列:销售额）
3. 分析「销售额」的分布与频次 → 直方图（X:销售额, Y:）
4. 计算「销售额」的同比（与去年同月对比）→ 折线图（X:日期, Y:销售额同比）
    + 排序表格（排序:同比变化%, 降序）
5. 计算「销售额」的环比（与上月对比）→ 折线图（X:日期, Y:销售额环比）
    + 排序表格（排序:环比变化%, 降序）
6. 绘制「城市」的「销售额」地图与地区分布 → 3D地图（X:城市, Y:销售额）
    + 汇总表格（行:城市, 列:销售额）


===== 现在请对以下真实数据，完全模仿上面示例的格式输出。不可自创章节、不可加emoji、分析建议后不可再写任何内容。=====

{data_summary}

===== 再次强调 =====
1. 输出必须从"## 数据概览"开始，到"## 分析建议"的最后一条表格推荐结束。
2. "分析建议"后面不能再出现任何文字。
3. 每条建议必须是"图表行 + 表格行"两行，括号内标注 (X:列名, Y:列名)。"""

# ============================================================
# 数据分析报告生成 Prompt（五阶段分析流水线 阶段4-5）
# ============================================================

REPORT_SYSTEM_PROMPT = """你是一名资深数据分析师（Senior Data Analyst）。

你的任务是根据下方提供的精确统计数据，生成一份专业的数据分析报告。

一、图表生成原则（★★★ 最重要 ★★★）：
1. 一张图 = 一个业务问题 = 一个分析结论。每张图必须回答一个明确的业务问题
2. 禁止同一组数据生成多个表达相同含义的图表（如地区销售额做柱状图+横向柱状图+饼图，三者选一）
3. 优先生成"发生了什么""为什么发生""哪里值得关注"的图
4. 禁止生成仅重复已有信息的图表
5. 每个 insight 对象必须包含 analysis_type 字段（见下方枚举）

二、analysis_type 枚举（每个 chart 必填）：
┌────────────────┬──────────────────────────────────┐
│ analysis_type  │ 含义                             │
├────────────────┼──────────────────────────────────┤
│ overview       │ 总览/概览                        │
│ trend          │ 趋势/时间变化                    │
│ comparison     │ 分类比较（谁更高/谁更低）         │
│ composition    │ 构成占比（各部分占多少）          │
│ ranking        │ 排名（TopN/BottomN）             │
│ distribution   │ 分布/频次                        │
│ correlation    │ 相关性（A与B的关系）              │
│ anomaly        │ 异常检测                         │
│ geography      │ 地域/空间分布                    │
│ detail         │ 明细/详情                        │
└────────────────┴──────────────────────────────────┘

三、洞察分析原则：
1. 所有结论必须来源于下方提供的统计数据，不得凭空编造
2. 禁止简单复述数字 ─ 必须解释数字背后的业务现象
3. 禁止描述图表样式（如"从图中可以看出折线向上"） ─ 应描述业务结论
4. 使用专业但通俗的语言 ─ 让管理者在 3 分钟内看懂
5. 增长率格式：🔺 +18.56%（上升）、🔻 -12.34%（下降）、➖ 0.00%（持平）
6. 所有百分比保留 2 位小数
7. 每项分析至少给出 1-3 条结构化洞察
8. 每条洞察必须标注 insight_label（趋势洞察/结构洞察/集中度洞察/异常洞察/风险洞察）

四、Section 类型映射表（★必须严格遵守★）：
┌──────────────┬────────────┬──────────────┬─────────────┐
│ section.type │ chart_type │ table_type   │ analysis_type│
├──────────────┼────────────┼──────────────┼─────────────┤
│ trend        │ line       │ sort/null    │ trend       │
│ structure    │ pie        │ summary      │ composition │
│ top          │ bar        │ sort         │ ranking     │
│ overview     │ null       │ null         │ overview    │
│ kpi          │ null       │ null         │ overview    │
│ anomaly      │ null       │ null         │ anomaly     │
│ conclusion   │ null       │ null         │ —           │
│ suggestions  │ null       │ null         │ —           │
└──────────────┴────────────┴──────────────┴─────────────┘

补充规则：
- 规则9: 趋势/走势类 → line 折线图（analysis_type=trend）
- 规则10: 同比/环比类 → line 折线图 + sort 排序表格（analysis_type=trend）
- 规则11: 对比/排名类 → bar 柱状图 + sort 排序表格（analysis_type=ranking）
- 规则12: 占比/比例类 → pie 饼图 + summary 汇总表格（analysis_type=composition）
- 规则13: 地区分布类 → map_3d 3D地图 + summary 汇总表格（analysis_type=geography）
  ★ 如果数据同时有「地点」和「省份」两列，地图 X 轴必须用「省份」列！
- 规则14: 交叉分析类 → stacked_bar 堆叠柱状图 + cross 交叉表格（analysis_type=comparison）
- 规则15: 相关性类 → scatter 散点图 + correlation 相关系数表格（analysis_type=correlation）
- 规则16: 分布类 → histogram 直方图（analysis_type=distribution）

每个 insight 对象必须包含：chart_title、chart_type、table_type、rule_id、insight_label、analysis_type、analysis。

五、后续操作建议（★必填★）：
在报告末尾生成 type="next_steps" 的 section，包含 action_items：
3-5 条可执行建议，必须包含具体对象+阈值/动作"""

REPORT_USER_PROMPT_TEMPLATE = """请基于以下统计数据生成一份完整的数据分析报告。

## 一、数据概况
{data_overview}

## 二、字段识别结果
- 时间维度：{time_dimension}
- 数值指标：{metrics}
- 分类维度：{dimensions}

## 三、基础统计
{basic_stats}

## 四、趋势分析
{trend_analysis}

## 五、同环比分析
{yoy_mom}

## 六、Top / Bottom 分析
{top_analysis}

## 七、结构分析
{structure_analysis}

## 八、异常分析
{anomaly_analysis}

## 九、已推荐图表
{planned_charts}

---

请严格按照以下 JSON 格式输出报告（不要输出任何其他内容）。

★ 每个 insight 对象必须包含以下 8 个字段，缺一不可：
  - chart_title: 对应的图表标题
  - chart_type: 图表类型（必须匹配映射表）
  - table_type: 表格类型（null/sort/summary/cross/correlation）
  - rule_id: 规则编号（如 "规则9"）
  - insight_label: 洞察类型标签（趋势洞察/结构洞察/集中度洞察/异常洞察/风险洞察）
  - analysis_type: 分析类型枚举值（overview/trend/comparison/composition/ranking/distribution/correlation/anomaly/geography/detail）
  - dimension: 分析的维度（如"地区""产品类别"）
  - metric: 分析的指标（如"销售额""利润"）
  - business_question: 这张图回答什么业务问题（如"哪个地区贡献最高销售额？"）
  - business_conclusion: 业务结论（禁止"从图中可以看出"，必须输出具体结论）
  - analysis: 分析文本（解释现象，不是描述图表）

  ★ 禁止重复表达：同一个 (analysis_type, dimension, metric) 组合只能出现一次。

```json
{{
  "sections": [
    {{
      "type": "overview",
      "title": "数据概览",
      "content": "2-3句话概括数据规模、时间范围、字段构成"
    }},
    {{
      "type": "kpi",
      "title": "核心指标",
      "insights": [
        {{
          "chart_title": "核心指标总览",
          "chart_type": null,
          "table_type": null,
          "rule_id": "规则10",
          "insight_label": "趋势洞察",
          "analysis_type": "overview",
          "dimension": null,
          "metric": "销售额",
          "business_question": "核心指标的整体表现如何？",
          "business_conclusion": "销售额达298.9万亿，同比增长18.56%，整体趋势良好。",
          "analysis": "指标1的描述与同比/环比"
        }}
      ]
    }},
    {{
      "type": "trend",
      "title": "趋势分析",
      "insights": [
        {{
          "chart_title": "销售额趋势分析",
          "chart_type": "line",
          "table_type": "sort",
          "rule_id": "规则9",
          "insight_label": "趋势洞察",
          "analysis_type": "trend",
          "dimension": "日期",
          "metric": "销售额",
          "business_question": "销售额随时间如何变化？是否持续增长？",
          "business_conclusion": "销售额在3月达到峰值后略有回落，整体呈平稳上升趋势。",
          "analysis": "趋势洞察（解释业务现象）"
        }}
      ]
    }},
    {{
      "type": "structure",
      "title": "结构分析",
      "insights": [
        {{
          "chart_title": "各地区销售额占比分布",
          "chart_type": "pie",
          "table_type": "summary",
          "rule_id": "规则12",
          "insight_label": "结构洞察",
          "analysis_type": "composition",
          "dimension": "地区",
          "metric": "销售额",
          "business_question": "各地区销售额占比如何分布？是否存在过度依赖？",
          "business_conclusion": "华东地区贡献42%销售额，Top3地区合计占91.4%，地域集中度高。",
          "analysis": "结构/集中度洞察"
        }}
      ]
    }},
    {{
      "type": "top",
      "title": "TOP / 集中度分析",
      "insights": [
        {{
          "chart_title": "各省份销售金额排名",
          "chart_type": "bar",
          "table_type": "sort",
          "rule_id": "规则11",
          "insight_label": "集中度洞察",
          "analysis_type": "ranking",
          "dimension": "省份",
          "metric": "销售额",
          "business_question": "哪些省份贡献最高销售额？存在一超多强格局吗？",
          "business_conclusion": "上海以793万元居首，是末位的14.98倍，Top5省份占总额89.7%。",
          "analysis": "Top 产品或维度分析"
        }}
      ]
    }},
    {{
      "type": "anomaly",
      "title": "异常分析",
      "insights": [
        {{
          "chart_title": null,
          "chart_type": null,
          "table_type": null,
          "rule_id": null,
          "insight_label": "异常洞察",
          "analysis_type": "anomaly",
          "dimension": null,
          "metric": null,
          "business_question": null,
          "business_conclusion": null,
          "analysis": "异常指标与维度"
        }}
      ]
    }},
    {{
      "type": "conclusion",
      "title": "核心结论",
      "insights": [
        {{
          "chart_title": null,
          "chart_type": null,
          "table_type": null,
          "rule_id": null,
          "insight_label": null,
          "analysis_type": "overview",
          "dimension": null,
          "metric": null,
          "business_question": null,
          "business_conclusion": "关键发现1",
          "analysis": "关键发现1"
        }}
      ]
    }},
    {{
      "type": "suggestions",
      "title": "业务建议",
      "insights": [
        {{
          "chart_title": null,
          "chart_type": null,
          "table_type": null,
          "rule_id": null,
          "insight_label": null,
          "analysis_type": "detail",
          "dimension": null,
          "metric": null,
          "business_question": null,
          "business_conclusion": null,
          "analysis": "建议1"
        }}
      ]
    }},
    {{
      "type": "next_steps",
      "title": "下一步操作建议",
      "action_items": [
        {{
          "priority": 1,
          "action": "重点监控Top3城市的日销售额波动，设置环比下跌超过15%的预警"
        }}
      ]
    }}
  ]
}}
```

★ 注意：
- next_steps section 是必填的，必须放在所有其他 section 之后
- action_items 至少 3 条，每条必须包含具体的监控对象、指标和阈值
- 如果数据中有地区列（含"省/市/区/地区/区域/城市"等关键词），必须生成一个 type="structure" 的 section，
  其中 insight 对象的 chart_type="map_3d"、rule_id="规则13"、table_type="summary"、insight_label="结构洞察"
- 如果有 ≥2 个分类维度交叉，生成 type="structure" section，chart_type="stacked_bar"、rule_id="规则14"、table_type="cross"
- 如果有 ≥2 个数值指标，生成 type="trend" section，chart_type="scatter"、rule_id="规则15"、table_type="correlation"
- 所有字符串型 insight 必须改为对象格式（11 个字段缺一不可：chart_title, chart_type, table_type, rule_id, insight_label, analysis_type, dimension, metric, business_question, business_conclusion, analysis）
- 洞察数量控制在 2-5 条每节
- 必须使用提供的统计数据，禁止编造数字"""
