---
name: AI分析报告改为深空暗色主题
overview: "将 DataMind AI 分析报告的 HTML 背景从白色改为与网站一致的深空暗色（body #020617、卡片 #0F172A、文字 #e2e8f0、次要文字 #94A3B8、强调星光蓝 #38BDF8），并连带修复图表坐标轴标签颜色，确保深色背景下文字与图表均清晰可读。报告图表轴标默认黑色，改深底后会变黑字黑底消失，故需后端 axisLabel 修复 + 渲染脚本保险注入两者配合。"
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
      - "#94a3b8"
      - "#f1f5f9"
    functional:
      - "#34D399"
      - "#FBBF24"
      - "#FB7185"
todos:
  - id: patch-axis-backend
    content: 后端 echart_generator.py 给 11 处 xAxis/yAxis 补 axisLabel.color="#94A3B8"
    status: pending
  - id: report-dark-css
    content: 前端 exportEChartsDashboard.ts 将 buildReportHTML 样式块深空暗色化并加打印回退
    status: pending
    dependencies:
      - patch-axis-backend
  - id: inject-axis-script
    content: 前端 exportEChartsDashboard.ts 的 initOneChart 注入轴标保险色兼容旧包
    status: pending
    dependencies:
      - patch-axis-backend
  - id: verify-report
    content: read_lints 验证并重新生成 AI 报告核对深底与浅色轴标
    status: pending
    dependencies:
      - report-dark-css
      - inject-axis-script
---

## 用户需求

将 AI 分析报告（report 模板 / `buildReportHTML`）的整体视觉从「白底文档风」改为「深空暗色风」，与网站（Galaxy AI Analytics）深空背景保持一致，使报告在屏幕浏览时与看板/分析页视觉统一。

## 产品概述

AI 分析报告目前是 A4 打印文档风格：纯白背景 `#ffffff`、深灰文字 `#333`、浅灰卡片与封面。用户希望报告背景改为网页深空暗色（主背景 `#020617`），整体配色翻转为深色玻璃质感，与前端 Dashboard 风格统一。

## 核心特性

- 报告背景由白底改为深空暗色 `#020617`，文字/标题/封面/指标卡/表格/目录/页脚/洞察标签全量翻转为深色玻璃风格
- 因报告图表采用透明背景透出页面底色，且轴标文字默认黑色，改深底后必须同步保证坐标轴标签（x/y 刻度、轴标题）在深色背景下清晰可见（浅色 `#94A3B8`）
- 打印时自动回退为浅色背景以节省墨水
- 银河紫 `#8B5CF6` 仅用于封面标题辉光/AI 强调，不进入图表数据系列

## 技术栈

- 前端：TypeScript（报告 HTML 由 `exportEChartsDashboard.ts` 以字符串模板生成，含内联 style + `<style>` class 块），图表用 ECharts
- 后端：Python `src/echart_generator.py`（ECharts option 的 SSOT）
- 设计系统：Galaxy AI Analytics（主背景 `#020617`、卡片 `#0F172A`、内容 `#F8FAFC`、星光蓝 `#38BDF8`、银河紫 `#8B5CF6`、文字次要 `#94A3B8`）

## 实现方案

### 关键决策：深底与轴标强耦合，必须两套一起改

1. 报告图表 `option.backgroundColor='transparent'`（行 454），轴标颜色来自后端 `echart_generator.py`，目前 axisLabel 无显式 color → ECharts 默认黑色。白底可见，深底「黑字黑底」消失。故「改深底」必然连带「修轴标」。
2. 后端修 axisLabel.color 是 SSOT：分析页 / 看板 / 报告 / 导出 HTML 四处一次性修复，且符合现有 `DARK_THEME.textStyle.color` 的隐式约定。
3. 前端 `makeEChartsScript` 额外注入轴标保险色，使「旧的、未重分析的 saved_packages」无需重新生成即可正确显示浅色轴标，规避用户重做成本。
4. 仅改 `buildReportHTML` 的 `<style>` 块（报告元素全用 class，无散落 inline 颜色），不动同文件已深色的 `COMMON_CSS`/`REPORT_THEME`/`buildGridLayout`（仪表盘导出），不动 `DARK_THEME` 结构、不动 `BigScreen/*` 与 `GLMapView.tsx`。

### 修改范围

- **后端 `src/echart_generator.py`**：line / area / histogram / horizontal_bar / waterfall / scatter 共 11 处 xAxis/yAxis 补 `axisLabel.color="#94A3B8"`（已有 `axisLabel` 的（histogram、horizontal_bar xAxis）仅追加 color，保留 `rotate`/`fontSize`；yAxis 的 `name` 颜色随 axisLabel 继承）。
- **前端 `exportEChartsDashboard.ts` 二处**：
- `buildReportHTML` 的 `<style>` 块（行 1724-1802）全量深空暗色化，并加 `@media print` 回退浅色。
- `makeEChartsScript` → `initOneChart`（行 443-466）在 `option.backgroundColor='transparent'` 后注入轴标保险色。

## 实施要点（防回归）

- 只改 `buildReportHTML` 内联 `<style>` 与脚本，绝不触碰仪表盘导出主题。
- 图表容器高度保持硬编码 `420px`（记忆 66018955 严禁用 `max-height`/`overflow:hidden` 裁剪 ECharts canvas）。
- 银河紫 `#8B5CF6` 仅用于封面标题辉光/AI 强调，不进图表 series（记忆 93259908）。
- 打印回退：`@media print` 将 body 背景置 `#ffffff`、文字置 `#333`、卡片/表格回浅色，避免深色打印费墨；屏幕态仍为深空。
- 纯 CSS + JSON 字段补全，无性能影响；注入函数 O(1) 每图，开销可忽略。

## 架构设计

单文件 SSOT（后端轴标）+ 单文件前端（报告主题 + 脚本注入），两文件改动互不影响现有模块边界，符合现有分层（option 生成归后端、HTML 渲染归前端工具层）。

## 目录结构

```
src/
└── echart_generator.py            # [MODIFY] 11 处 xAxis/yAxis 补 axisLabel.color="#94A3B8"（含已有 axisLabel 仅追 color）
frontend/src/utils/
└── exportEChartsDashboard.ts      # [MODIFY] ① buildReportHTML <style> 块深空暗色化 + @media print 回退浅色
                                    #         ② makeEChartsScript.initOneChart 注入轴标保险色（兼容旧 saved_packages）
```

## 关键代码结构

```typescript
// exportEChartsDashboard.ts · makeEChartsScript.initOneChart 内注入（行 454 后）
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

采用与网站「Galaxy AI Analytics」一致的深空暗色体系（Glassmorphism）。报告整体背景为深空蓝黑 `#020617`，章节卡片与封面采用半透明深色玻璃质感（`#0F172A` + 细边框），文字以月光白 `#e2e8f0` 与次要灰 `#94a3b8` 为主，强调色使用星光蓝 `#38BDF8`（数据）与银河紫 `#8B5CF6`（AI 标题辉光）。标题下边框、卡片边框带极轻的星光蓝辉光，营造高级、沉稳、专业的分析文档气质。

## 页面（单文档连续页）区块设计

- **封面块 cover-page**：居中大标题（银河紫辉光），副标题与元信息（日期/数据行数）以次要灰呈现，背景为深空→深蓝渐变玻璃卡，圆角描边。
- **目录块 toc**：深色玻璃卡，章节列表以星光蓝小圆点引导，悬停高亮。
- **KPI 指标卡 metrics-row**：一排深色玻璃卡（`#0F172A` 底 + 星光蓝细边），大号数值用品牌色/状态色，标签用次要灰；状态色（绿/橙/红）在深底上更醒目。
- **章节块 section + 图表 chart-container**：深空背景，标题 `#f1f5f9` 带星光蓝下边框；分析正文月光白；图表容器透明背景透出深空，坐标抽标签浅灰 `#94A3B8` 清晰可读；高亮框/警告框改为深色低饱和底 + 状态色描边。
- **页脚 footer**：次要灰小字，顶部细分割线，与深空背景融合。

## 响应式

报告为 A4 固定版式（`@page A4`），屏幕浏览时 body 最大宽度约 1100px 居中；打印态经 `@media print` 回退浅色以省墨，版式不变。