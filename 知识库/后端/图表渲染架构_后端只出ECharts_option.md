---
title: 图表渲染架构（后端只出 ECharts option）
aliases: [后端图表渲染, option 怎么进 package, 后端不出图]
tags: [tech/backend, viz, architecture]
created: 2026-07-24
---

# 图表渲染架构：后端只出 ECharts option，不出图片

> 一句话：**后端算完数值后，产出的是 ECharts 的 `option` JSON 配置对象，把它塞进 `AnalysisPackage.charts` 传给前端；真正的"画成图"发生在浏览器里（[[ECharts是什么]]）。服务端全程不生成任何图片文件。**

## 一、为什么后端不出图

- 出图（Canvas/图片）是**前端浏览器**的活儿，[`[[ECharts是什么]]`] 是跑在 JS 里的渲染引擎。
- 后端只负责"算出图该长什么样"——即一份描述 series/tooltip/xAxis/legend 的 `option` 字典。
- 好处：配置是纯 JSON，可走 API、可缓存、可被导出 HTML 复用；渲染交给客户端，服务端零图片 I/O、零依赖（无 matplotlib/PIL/savefig）。

## 二、后端链路（已查代码确认）

| 步骤 | 文件:行 | 做什么 |
|---|---|---|
| 1. 生成 option | `src/echart_generator.py` `create_chart()` | 入参 `df, chart_type, x, y, title`，返回 ECharts `option` 字典（纯 JSON 可序列化）。**无 savefig/to_image/PIL**。 |
| 2. 包进 ChartItem | `src/chart_renderer.py:44` 调 `create_chart`，`:54` 构造 `ChartItem(..., option=option)` | 把 option 挂到图表项上 |
| 3. 结构定义 | `src/analysis_templates/base.py:77` `ChartItem`，`:83` `option: dict` | 图表项的数据类，option 是普通 dict 字段 |
| 4. 进 package | `AnalysisPackage.charts: List[ChartItem]`（`base.py:132`） | 所有图表项汇集到分析包的 charts 列表 |
| 5. 序列化 | `AnalysisPackage.to_api_dict()` 用 `dataclasses.asdict` + `sanitize_json` | option 作为 JSON 随 package 经 API 返回前端 |

> 旁证：搜 `savefig|to_image|PIL|html2image|playwright|\.png|matplotlib` 在 `src/` 图表链路**零命中**，确认服务端不出图。

## 三、两层数据，别混淆

- `chart_data`（域模型 `ChartData`，`base.py:67`）：`slot/chart_type/title/x/y/data`，是**原始数据行**，给前端表格/兜底用。
- `charts`（渲染结果 `ChartItem`）：带 `option`，是**可直接交给 ECharts 画**的完整配置。
- 前端 `EChartView` 优先用 `option` 直接渲染；导出 HTML（`exportEChartsDashboard.ts`）也复用同一份 option。

## 四、一句话闭环

```
后端 pandas 算数值 → create_echart 出 option(JSON) → ChartItem.option → AnalysisPackage.charts → API 返回
→ 前端 ECharts.js 拿 option 在 canvas 上画成图
```

## 相关

- [[ECharts是什么]] —— 前端视角：浏览器里用 option 渲染图表
- [[数据洞察分析后端全链路]] —— 分析可视化整体阶段（意图→pandas→package）
- [[前后端src三层分工]] —— backend/接口壳、src/干活内核、frontend/页面三层角色
