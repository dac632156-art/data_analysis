# DataMind AI 项目规则（AI 助手必读）

> 此文件是项目规则的硬备份，每次对话时 AI 助手必须遵守。

---

## 一、数据分析报告 Section 框架规则

报告有固定的 section 类型及图表映射，不可增删打乱：

| section.type | chart_type | table_type | 说明 |
|-------------|-----------|------------|------|
| overview | — | — | 数据概览，无图表 |
| kpi | — | — | 关键指标，无图表 |
| trend | line | sort/null | 趋势分析，配折线图 |
| structure | pie/map_3d | summary | 结构分析，配饼图；有地区列时配 3D 地图 |
| top | bar | sort | TOP/集中度分析，配柱状图 |
| anomaly | — | — | 异常分析，无图表 |
| conclusion | — | — | 结论，无图表 |
| suggestions | — | — | 建议，无图表 |
| next_steps | — | — | 后续操作，无图表 |

降级报告固定顺序：overview → kpi → trend → structure → top → anomaly → conclusion → suggestions → next_steps

---

## 二、Section 与图表绑定规则（chartIndex）

- 只有 `sec.chartIndex !== undefined && sec.chartIndex < echarts.length` 时才创建图表容器
- 没有图时 `chartDiv` 是空字符串，不渲染任何占位 DOM
- 禁止预留空的图表占位坑

---

## 三、图表容器高度规则

- ECharts 图表容器高度固定为 420px
- 绝对禁止使用 CSS max-height、overflow:hidden 裁剪图表

---

## 四、KPI 数值显示规则

- 主数字：中文缩写（≥万亿用"万亿"、≥亿用"亿"、≥万用"万"）
- 副数字：完整千分位数字，小字灰色显示

---

## 五、重复列名处理

- 入口已去重：`identify_fields()`、`get_column_info()`、`get_column_info_html()`、`run_full_analysis()`
- 策略：`df.loc[:, ~df.columns.duplicated()]`

---

## 六、仪表盘 Tab 分类规范（★★★★★ 核心）

### 6.1 职责分离

- AI 负责：字段识别、统计分析、洞察生成、图表类型选择、ECharts 配置生成
- 程序负责：Tab 分类、页面布局、KPI 渲染、同环比渲染、图表数量控制、空 Tab 隐藏

AI 不得决定图表属于哪个 Tab。

### 6.2 四个 Tab

| Tab | 允许内容 | 禁止内容 |
|-----|---------|---------|
| 数据总览 | KPI 卡片、同环比汇总表、数据概览信息 | 趋势图、分类图、地图、Top分析 |
| 趋势洞察 | 折线图、面积图、时间散点图、时间热力图、同比、环比 | 分类图、饼图 |
| 分类分析 | 柱状图、横向条形图、饼图、环形图、地图、3D地图、雷达图、词云、Top分析、瀑布图、箱线图 | KPI、趋势图 |
| 明细查询 | 数据表格、AI问答（预留）、异常记录（预留）、筛选器（预留） | 任何 ECharts 图表 |

### 6.3 图表类型 → Tab 映射表

| analysis_type / type | Tab |
|---------------------|-----|
| overview | 数据总览 |
| trend | 趋势洞察 |
| comparison | 分类分析 |
| composition | 分类分析 |
| ranking | 分类分析 |
| distribution | 分类分析 |
| correlation | 分类分析 |
| anomaly | 明细查询 |
| geography | 分类分析 |
| detail | 明细查询 |

### 6.4 图表类型 fallback 映射

| chart type | Tab |
|-----------|-----|
| gauge | 数据总览 |
| line, area | 趋势洞察 |
| bar, horizontal_bar, pie, treemap, radar, sankey, funnel, map, map_3d, wordcloud, sunburst, stacked_bar, grouped_bar, waterfall, box, polar, parallel | 分类分析 |
| scatter, bubble, heatmap | 按 analysis_type：trend→趋势洞察，其他→分类分析。无 analysis_type 时看 X 轴是否时间列 |
| candlestick | 趋势洞察 |
| table | 明细查询 |

### 6.5 AI 图表数据结构

```json
{
  "title": "地区销售额TOP10",
  "type": "horizontal_bar",
  "analysis_type": "comparison",
  "dimension": "地区",
  "metric": "销售额",
  "business_question": "哪个地区贡献最高销售额？",
  "business_conclusion": "华东地区贡献42%的销售额，是本期增长的主要来源。",
  "option": {}
}
```

### 6.6 图表去重规则

- 同 Tab + 同 (analysis_type, dimension, metric) → 只保留优先级最高的
- 优先级：horizontal_bar > bar > pie > treemap > radar > sunburst
- 跨 Tab 不去重（分析意图不同）

### 6.7 图表数量限制

| Tab | 最多图表数 | 优先级 |
|-----|----------|-------|
| 趋势洞察 | 4 | 一级 > 二级 |
| 分类分析 | 6 | 一级 > 二级 > 三级 |
| 明细查询 | 不限 | — |

### 6.8 KPI 和同环比必须从图表列表剥离

```
dashboard 返回:
  overview: { kpis: [...], yoy_table: {...} }
  charts: [...]   // 纯 ECharts 图表，不含 kpi/table
```

### 6.9 图表生成原则

- 一张图 = 一个业务问题 = 一个分析结论
- 禁止同一组数据生成多个表达相同含义的图表
- 优先生成"发生了什么""为什么发生""哪里值得关注"的图
- 禁止生成仅重复已有信息的图表

### 6.10 空 Tab 自动隐藏

### 6.11 AI 解读规范

- 每张图 1~3 条分析
- 禁止"从图中可以看出..."
- 必须输出业务结论

---

## 七、AI 不可做的事

- ❌ 用 CSS 裁剪图表
- ❌ 修改 report section 的类型映射或顺序
- ❌ 在没有 chartIndex 的 section 里强行插入图表
- ❌ 为填补空白而改布局结构
- ❌ 修改 KPI 缩写规则的阈值
- ❌ 决定图表属于哪个 Tab
- ❌ 生成表达相同业务含义的重复图表
