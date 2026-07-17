---
title: ECharts是什么
aliases: [ECharts是什么, ECharts, Apache ECharts, 前端图表, 数据可视化库]
tags: [tech/frontend, viz]
created: 2026-07-17
---

# ECharts 是什么

> 一句话：**ECharts 是一个用 JavaScript 把数据画成图表的开源库**（折线 / 柱 / 饼 / 地图 / 词云 / 散点…），它用「一份配置对象」来描述「图长什么样」，你改配置，它就重画。本项目所有图表都靠它渲染。

## 一、它从哪来、是什么

- **出身**：百度开源，现由 **Apache 软件基金会** 维护（全称 Apache ECharts）。
- **本质**：一个跑在浏览器里的 **JS 图表渲染引擎**，底层用 HTML5 Canvas（或 SVG）画图。
- **定位**：和 React（拼界面）、Axios（发请求）平级，是「**把数字变成图**」那一层的工具。

> 类比：如果数据是「原材料」，React 是「货架/店面」，那 ECharts 就是「把原材料做成可视成品的机器」。

## 二、核心机制：option + setOption

ECharts 是**声明式**的——你不用命令它「先画线、再画点」，而是写一份描述「我要什么图」的对象，交给它：

```js
// 1. 找到页面上的 <div> 容器
const chart = echarts.init(document.getElementById('main'));

// 2. 写一份「配置对象 option」描述图表
const option = {
  title:   { text: '销售趋势' },
  tooltip: { trigger: 'axis' },
  xAxis:   { type: 'category', data: ['1月','2月','3月'] },
  yAxis:   { type: 'value' },
  series:  [{ type: 'line', data: [120, 200, 150] }]  // ← 图的类型和数据在这
};

// 3. 把配置「喂」给图表，它就画出来了
chart.setOption(option);
```

- **series.type**：决定画什么图——`line` 折线、`bar` 柱、`pie` 饼、`map` 地图、`scatter` 散点、`wordCloud`（需插件）词云。
- **改数据 = 改 option 再 setOption 一次**，图就自动更新，不用手动擦掉重画。
- **响应式**：窗口变了调 `chart.resize()`，图跟着变大小。

## 三、它能画什么（本项目用到的）

| 图表 | series.type | 本项目用途 |
|---|---|---|
| 折线图 | `line` | 趋势分析（trend） |
| 柱状图 | `bar` | TOP/排名（top） |
| 饼图 | `pie` | 结构占比（structure） |
| 地图 | `map`（需注册 GeoJSON） | 地理分布（含 3D `map_3d` 走 echarts-gl） |
| 词云 | `wordCloud`（需 echarts-wordcloud 插件） | 关键词热度（wordcloud） |
| 散点 / 热力 | `scatter` / `heatmap` | 相关 / 异常分析 |

> 本项目实际用的是 **ECharts 6**，并额外挂了两个插件：**echarts-gl**（画三维地图 `map_3d`）、**echarts-wordcloud**（画词云）。

## 四、本项目怎么用 ECharts（前后端分工）

和「React 拼界面」不同，ECharts 是**命令式 API**（要 `init` / `setOption` / `dispose` 自己管生命周期）。本项目的做法是**后端生成配置、前端只管渲染**：

```
后端 src/echart_generator.py
   → 计算数据 + 拼出 option 这个 JSON 对象
   → 通过 API 把 option 传给前端

前端 EChartView.tsx（一个 React 组件）
   → 挂在 <div> 容器上
   → echarts.init() 初始化
   → setOption(后端给的 option) 画出来
   → 监听窗口 resize + 卸载时 dispose() 释放
```

- **数据色板**：图表系列颜色走项目的 VDS 调色板（星光蓝 ramp），由 `echart_generator.py` 里的 `BLUE_PALETTE` / `WARM_COLORS` 与前端 `Palette.ts` 点对点对齐。
- **为什么这么分**：分析计算（Python 擅长）放后端，渲染（浏览器擅长）放前端，option 作为两边通用的「契约」，谁都能改。

## 五、和 React 的关系（为什么要封装组件）

React 是声明式（你描述 UI 长啥样，它管更新），ECharts 是命令式（你手动调 API）。两者不能直接混：

> 所以本项目把 ECharts 包进了 `EChartView.tsx` 这个 React 组件——**组件挂载时 init、option 变化时 setOption、窗口变化 resize、组件卸载 dispose**，把命令式 API 藏起来，让页面里能像用普通 React 组件一样用图表。

## 六、本项目踩过的几个坑（记忆点）

- **词云颜色**：`echarts-wordcloud` 2.1.0 的 `series.textStyle.color = function` 方案**无效**（zrender 拿到函数当无效填充 → 全部回退黑色）。正解是**给每个 data item 直接附静态 `textStyle.color`**。详见知识库词云修复记忆。
- **地图空白**：`map` 类型必须先 `echarts.registerMap('china', geoJson)` 注册 GeoJSON，本项目把阿里云 `china.json` 下载到 `frontend/public/china.json` 本地化，避免跨域加载失败。
- **容器被 CSS 截断**：EChartView 的容器高度只能用 ECharts 自己的 `resize()` 或改 JS 里的初始高度，**绝不能**用 CSS 的 `max-height / overflow:hidden` 裁剪——否则 canvas 物理截断（上半正常、下半消失）。

## 相关笔记

- [[前端技术栈]] —— 前端 MOC，ECharts 是其中「图表」选型
- [[前端图表ECharts]] —— 本项目如何落地 ECharts（若已细分）
- [[React是什么]] —— 声明式 UI 框架，ECharts 被它封装成组件
- [[Tailwind是什么]] —— 界面样式，与图表渲染互补
- [[代码文件总览]] —— 定位 `echart_generator.py` / `EChartView.tsx` 等文件
