---
name: fix-yaxis-label-color
overview: 为 src/echart_generator.py 的 11 处 xAxis/yAxis 补 axisLabel.color=#94A3B8，修复报告 HTML 深色背景下 y 轴数字不可见的问题
todos:
  - id: patch-line-axis
    content: 在 src/echart_generator.py line chart 的 xAxis/yAxis 补 axisLabel.color="#94A3B8"
    status: pending
  - id: patch-area-axis
    content: 在 area chart 的 xAxis/yAxis 补 axisLabel.color
    status: pending
    dependencies:
      - patch-line-axis
  - id: patch-histogram-axis
    content: 在 histogram chart 的 xAxis 追加 color、yAxis 新增 axisLabel
    status: pending
    dependencies:
      - patch-area-axis
  - id: patch-horizontal-bar-axis
    content: 在 horizontal_bar chart 的 xAxis 追加 color、yAxis 新增 axisLabel
    status: pending
    dependencies:
      - patch-histogram-axis
  - id: patch-waterfall-axis
    content: 在 waterfall chart 的 xAxis/yAxis 补 axisLabel.color
    status: pending
    dependencies:
      - patch-horizontal-bar-axis
  - id: patch-scatter-axis
    content: 在 scatter chart 的 xAxis/yAxis 补 axisLabel.color
    status: pending
    dependencies:
      - patch-waterfall-axis
  - id: verify-lint-and-runtime
    content: 跑 read_lints + 调一次 create_echart 验证 option 含 axisLabel.color
    status: pending
    dependencies:
      - patch-scatter-axis
---

## Product Overview

修复 AI 分析报告与仪表盘里所有 ECharts 图表的坐标轴标签（x/y 轴刻度文字、轴标题 name）颜色缺失问题。在深色背景下，ECharts 默认的黑色轴标不可见，导致用户无法读出 y 轴数值（趋势图）和 x 轴分类（TOP 图），完全看不懂图所表达的内容。

## 核心 Features

- 修复 line（折线/趋势图）、area、scatter、bar（柱状/TOP 图）、histogram、heatmap、horizontal_bar、waterfall 等所有带 xAxis/yAxis 的图表类型，axisLabel 显式指定深色背景下可读的浅色文字
- 颜色统一为 `#94A3B8`（与项目 GALAXY 设计系统 `text_secondary` 一致），保证前/后端、报告/看板视觉一致
- 修复覆盖 11 处 xAxis/yAxis 块，5 种 chart 函数；不影响 pie/wordCloud/treemap/sankey（无坐标轴）

## Tech Stack

- 后端 Python 图表生成：`src/echart_generator.py`（ECharts option 构造）
- 设计系统 token：`GALAXY.text_secondary = #94A3B8`（已在文件内定义）
- 范围：仅 `src/echart_generator.py` 一个文件，11 处 axisLabel 补丁

## Implementation Approach

### 关键决策：为什么必须改后端而不是改前端/HTML 模板

1. ECharts 的 `axisLabel.color` **不会继承**自 `textStyle.color`——这是 ECharts 的设计。`DARK_THEME.textStyle.color` 已设了 `#94A3B8` 但对 axisLabel 无效。
2. 报告 HTML 是后端返回的 `chart.option` 序列化后塞进 `chart.setOption(option, { notMerge: true })`；前端 `enhanceOptionForInteraction` 不修改 axisLabel。
3. 改后端是 SSOT：分析页/看板/报告/导出 HTML **四处**全部一次性修复。
4. 不动 `DARK_THEME` 结构、不动报告 HTML 模板（用户之前拒绝改 `exportEChartsDashboard.ts` 风格）、不动 `BigScreen/*` 与 `GLMapView.tsx`（独立美学）。

### 修复范围（11 处）

- **行 240-241** line chart xAxis：补 `axisLabel: { color: "#94A3B8" }`
- **行 242** line chart yAxis：补 `axisLabel: { color: "#94A3B8" }`
- **行 290** area chart xAxis：补 `axisLabel: { color: "#94A3B8" }`
- **行 291** area chart yAxis：补 `axisLabel: { color: "#94A3B8" }`
- **行 396-400** histogram xAxis：已有 axisLabel，**追加** `color: "#94A3B8"`
- **行 401-404** histogram yAxis：补 `axisLabel: { color: "#94A3B8" }`
- **行 492** horizontal_bar xAxis：已有 axisLabel，**追加** `color: "#94A3B8"`
- **行 494** horizontal_bar yAxis：补 `axisLabel: { color: "#94A3B8" }`
- **行 607** waterfall xAxis：补 `axisLabel: { color: "#94A3B8" }`
- **行 609** waterfall yAxis：补 `axisLabel: { color: "#94A3B8" }`
- **行 641** scatter xAxis：补 `axisLabel: { color: "#94A3B8" }`
- **行 642** scatter yAxis：补 `axisLabel: { color: "#94A3B8" }`

### 实施细节（重要约束）

- axisLabel 中已有的字段（`rotate`、`fontSize`）必须**保留**，只补 `color`。
- 行 398（histogram xAxis）和行 492（horizontal_bar xAxis）已有 `axisLabel` dict（结构是单行 + `axisLine` 错位），需精确 patch。
- 行 401-404 yAxis `name: "频次"` 也要有可读颜色——`name` 颜色继承自 axisLabel.color，所以同一个补丁即可。
- 不引入新颜色 token，直接写 hex `#94A3B8`（与 GALAXY 一致，但保持简单不引入跨文件常量引用，避免循环依赖/可读性退化）。
- 不动 `axisLine.color`（`rgba(255,255,255,0.08)` 是有意为之的"细线"美学）。

## Performance & Reliability

- 无性能影响：纯 JSON 字段补全。
- 风险点：报告里旧 saved_packages 的 chart.option **没有**新 color 字段（因为 option 是在保存时快照的）。修复需用户**重新分析一次数据 + 重新保存**才能让新生成图带上 color。如果用户不想重做，可在 `makeEChartsScript` 的 `chart.setOption` 前端插入一个统一注入 axisLabel.color 的补丁——但这会改动 `exportEChartsDashboard.ts`（用户拒绝改动范围）。**取舍**：本次只修后端生成逻辑，告知用户需重保存一次以让报告呈现新样式。

## 验证步骤

1. lint 0 错误（`read_lints`）
2. 在测试数据上跑一次 line/bar 生成，验证返回 option 中 xAxis/yAxis 含 `axisLabel.color = "#94A3B8"`
3. 重新执行分析并保存到仪表盘，再生成 AI 报告，确认 y 轴数字可见
4. 看板/分析页/报告三处都应显示可读 y 轴数值

## Architecture Design

单文件 SSOT 修改，影响最小。所有 chart 函数共用同一 `GALAXY.text_secondary` 颜色（隐式约定），符合现有代码风格（DARK_THEME 已隐式使用相同值）。

## Directory Structure

```
src/
└── echart_generator.py  # [MODIFY] 11 处 xAxis/yAxis 补 axisLabel.color="#94A3B8"
```