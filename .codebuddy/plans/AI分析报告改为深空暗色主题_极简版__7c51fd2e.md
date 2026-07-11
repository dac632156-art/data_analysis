---
name: AI分析报告改为深空暗色主题（极简版）
overview: 将 DataMind AI 分析报告的 HTML 背景由白底改为与网站一致的深空暗色（#020617），仅改 buildReportHTML 的 <style> 块，不动后端 echart_generator.py（经核查网页与报告共用同一份 option 与同一套 echarts.init/setOption 管线，换背景不会破坏轴标）。加一道无害的轴标保险色注入（同文件，仅作用于报告图表，兼容旧包），确保报告从白底变深底后轴标不退化；纯前端、零后端改动。
design:
  architecture:
    framework: html
  styleKeywords:
    - Deep Space
    - Glassmorphism
    - Dark Theme
    - Starlight Blue Accent
    - Subtle Glow
    - Elegant
  fontSystem:
    fontFamily: PingFang SC
    heading:
      size: 26px
      weight: 700
    subheading:
      size: 16px
      weight: 600
    body:
      size: 14px
      weight: 400
  colorSystem:
    primary:
      - "#38BDF8"
      - "#8B5CF6"
    background:
      - "#020617"
      - "#0F172A"
    text:
      - "#e2e8f0"
      - "#94A3B8"
      - "#f1f5f9"
    functional:
      - "#34D399"
      - "#FBBF24"
      - "#FB7185"
todos:
  - id: dark-report-style
    content: 将 exportEChartsDashboard.ts 中 buildReportHTML 样式块深空暗色化并加打印回退
    status: completed
  - id: inject-axis-label
    content: 在 initOneChart 注入轴标保险色兼容旧报告包
    status: completed
  - id: verify-report
    content: read_lints 验证并重新生成 AI 报告核对深底与浅色轴标
    status: completed
    dependencies:
      - dark-report-style
      - inject-axis-label
---

## 用户需求

将 AI 分析报告（report 模板 / `buildReportHTML`）的整体视觉从「白底文档风」改为与网站一致的「深空暗色风」，使报告在屏幕浏览时与看板/分析页视觉统一。

## 产品概述

AI 分析报告目前是 A4 打印文档风格：纯白背景 `#ffffff`、深灰文字 `#333`、浅灰卡片与封面。用户希望报告背景改为网页深空暗色（主背景 `#020617`），整体配色翻转为深色玻璃质感（Galaxy AI Analytics 体系），与前端 Dashboard 风格统一。

## 核心特性

- 报告背景由白底改为深空暗色 `#020617`，文字/标题/封面/指标卡/表格/目录/页脚/洞察标签全量翻转为深色玻璃风格
- 深底下图表坐标轴标签（x/y 刻度、轴标题）必须清晰可读（浅色 `#94A3B8`），保证报告整体可读
- 打印时自动回退为浅色背景以节省墨水（不影响屏幕深空态）
- 银河紫 `#8B5CF6` 仅用于封面标题辉光/AI 强调，不进入图表数据系列

## 技术栈

- 前端 TypeScript：报告 HTML 由 `frontend/src/utils/exportEChartsDashboard.ts` 以字符串模板生成，全部样式集中在 `<style>` 块
- 图表渲染：ECharts，报告内图表由 `makeEChartsScript.initOneChart` 经 `echarts.init(el)` + `setOption(option)` 渲染
- 纯 CSS 变更 + 轻量 JS 注入，无新增依赖、无后端改动

## 实现方案

### 关键决策：仅改前端、无需改后端（正面回应用户"强耦合"质疑）

1. **网页与报告渲染管线完全一致**：`EChartView.tsx:615` 与报告端 `initOneChart`（exportEChartsDashboard.ts:452）均使用 `echarts.init(el, undefined, ...)`（无 theme），且共用同一份后端 `echart_generator.py` 生成的 option。报告改深底后，轴标表现与网页同款，不会引入新的不可读问题。因此"改深底必须联动改后端 axisLabel"的断言不成立。
2. **轴标保险注入（纯前端同文件）**：在 `option.backgroundColor='transparent'`（行 454）后，对 xAxis/yAxis 补充 `axisLabel.color='#94A3B8'`（原 option 已含则不覆盖）。保证报告在深底下轴标必定可读，且兼容旧 saved_packages，零回归风险，不触碰后端。
3. **仅动 `buildReportHTML`**：所有报告元素均用 class 定义，无散落 inline 颜色，只改其 `<style>` 块；不动同文件已深色的 `COMMON_CSS`/`REPORT_THEME`/`buildGridLayout`（仪表盘导出），不动 `DARK_THEME` 结构、不动 `BigScreen/*` 与 `GLMapView.tsx`。

### 性能与可靠性

- 纯 CSS 变更无性能影响；注入函数为每图 O(1)，开销可忽略
- 不影响其他模板（grid/medical/command 使用独立主题），改动互不影响现有模块边界
- 防回归：图表容器高度保持硬编码 420px（严禁 max-height/overflow:hidden 裁剪 ECharts canvas）

## 实施要点

- 只改 `buildReportHTML` 内联 `<style>` 与 `initOneChart`，绝不触碰仪表盘导出主题
- 银河紫 `#8B5CF6` 仅用于封面标题辉光/AI 强调，不进图表 series
- 打印回退：`@media print` 将 body 背景置 `#ffffff`、文字置 `#333`、卡片/表格回浅色，省墨；屏幕态仍为深空

## 架构设计

单文件前端改动：报告 HTML 生成（buildReportHTML 样式块）+ 图表渲染脚本（initOneChart 注入）。与现有分层一致（option 由后端生成、HTML/渲染由前端工具层负责），不破坏模块边界。

## 目录结构

```
frontend/src/utils/
└── exportEChartsDashboard.ts  # [MODIFY] ①buildReportHTML <style> 块深空暗色化 + @media print 回退浅色
                                    #         ②initOneChart 注入轴标保险色（兼容旧 saved_packages，零回归）
```

## 关键代码结构

```typescript
// exportEChartsDashboard.ts · makeEChartsScript.initOneChart 内（行 454 后）
function ensureAxisLabelColor(axis: any) {
  if (!axis) return;
  if (Array.isArray(axis)) { axis.forEach(ensureAxisLabelColor); return; }
  axis.axisLabel = axis.axisLabel || {};
  if (!axis.axisLabel.color) axis.axisLabel.color = '#94A3B8';
}
if (option.xAxis) ensureAxisLabelColor(option.xAxis);
if (option.yAxis) ensureAxisLabelColor(option.yAxis);
```

## 设计风格

采用与网站「Galaxy AI Analytics」一致的深空暗色体系（Glassmorphism）。报告整体背景为深空蓝黑 `#020617`，章节卡片与封面采用半透明深色玻璃质感（`#0F172A` + 细边框），文字以月光白 `#e2e8f0` 与次要灰 `#94A3B8` 为主，强调色使用星光蓝 `#38BDF8`（数据）与银河紫 `#8B5CF6`（封面标题辉光）。标题下边框、卡片边框带极轻的星光蓝辉光，营造高级、沉稳、专业的分析文档气质。

## 页面（单文档连续页）区块设计

- **封面块 cover-page**：居中大标题（银河紫辉光），副标题与元信息（日期/数据行数）以次要灰呈现，背景为深空→深蓝渐变玻璃卡，圆角描边。
- **目录块 toc**：深色玻璃卡，章节列表以星光蓝小圆点引导，悬停高亮。
- **KPI 指标卡 metrics-row**：一排深色玻璃卡（`#0F172A` 底 + 星光蓝细边），大号数值用品牌色/状态色，标签用次要灰；状态色（绿/橙/红）在深底上更醒目。
- **章节块 section + 图表 chart-container**：深空背景，标题 `#f1f5f9` 带星光蓝下边框；分析正文月光白；图表容器透明背景透出深空，坐标轴标签浅灰 `#94A3B8` 清晰可读；高亮框/警告框改为深色低饱和底 + 状态色描边。
- **页脚 footer**：次要灰小字，顶部细分割线，与深空背景融合。

## 响应式

报告为 A4 固定版式（`@page A4`），屏幕浏览时 body 最大宽度约 1100px 居中；打印态经 `@media print` 回退浅色以省墨，版式不变。