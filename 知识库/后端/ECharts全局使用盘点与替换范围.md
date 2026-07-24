---
title: ECharts 全局使用盘点与替换范围
aliases: [echarts 都用哪了, 换 echarts 要动哪些, echarts 依赖盘点]
tags: [tech/audit, viz, echarts]
created: 2026-07-24
---

# ECharts 全局使用盘点与替换范围

> 全局审计结论：ECharts 不是「一个库」，扎进 **前端渲染层（8 文件）+ 导出 HTML（最重）+ 后端单一生成源 + ~71 消费端 + 2 个扩展**。换库须按此清单动。详见 [[图表渲染库可替换性]]。

## 一、依赖清单（frontend/package.json）
| 依赖 | 版本 | 用途 | 是否 echarts |
|---|---|---|---|
| `echarts` | ^6.1.0 | 核心（所有普通图表） | ✅ |
| `echarts-gl` | ^2.1.0 | 3D/地理地图 WebGL | ✅ 扩展 |
| `echarts-wordcloud` | ^2.1.0 | 词云 | ✅ 扩展 |
| `html2canvas` | ^1.4.1 | DOM 截图导出图片 | ❌ 相邻（非 echarts） |
| `@jiaminghi/data-view-react` | ^1.2.5 | 大屏排名榜 DataV | ❌ 相邻 |

## 二、前端渲染层（import echarts 处 = 换库必动）
### A. 直接生产渲染器
- `frontend/src/components/EChartView.tsx` —— **核心渲染器**：`echarts/core` + charts/components/renderers + `import 'echarts-wordcloud'` + `import 'echarts-gl'`；词云/3D 检测也在此。
- `frontend/src/components/GLMapView.tsx` —— **3D/WebGL 中国地图**：`echarts/core` + `init(...,{renderer:'webgl'})` + `registerMap('china')`。
- `frontend/src/components/BigScreen/CommandScreen.tsx` —— 指挥中心大屏 **2D 地图飞线/散点**：`echarts/core` + `EffectScatterChart`/`LinesChart` + `GeoComponent` + `CanvasRenderer` + `registerMap('china')`（另用 DataV 排名榜）。
- `frontend/src/components/BigScreen/MedicalDashboard.tsx` —— 医疗看板。
- `frontend/src/components/BigScreen/EGridLayout.tsx` —— 大屏栅格布局引擎。
- `frontend/src/components/DashboardRenderer/WidgetRenderer/ChartWidget.tsx` —— 看板图表 widget（`+ 'echarts-gl'`）。
- `frontend/src/components/DashboardRenderer/WidgetRenderer/KPIWidget.tsx` —— KPI widget。
- `frontend/src/components/DashboardRenderer/WidgetRenderer/MapWidget.tsx` —— 看板地图 widget（`+ 'echarts-gl'`）。

### B. 间接消费（喂 option 给 EChartView，不 import echarts → 换库不用动）
`DashboardPage.tsx`、`AnalysisPage.tsx`、`VisualiationRenderer.tsx`、`DashboardRenderer/*` —— 经 `<EChartView option={chart.option} />` 渲染。

### C. 导出 HTML（最重）
`frontend/src/utils/exportEChartsDashboard.ts` —— 内嵌 `echarts@5.5.0` CDN + `echarts-gl@2.0.9` CDN + `makeEChartsScript` 直接操作 option（`setOption`/`registerMap`/pie·wordCloud·radar 提取/resize）。

## 三、后端层
| 文件 | 角色 | 换库动作 |
|---|---|---|
| `src/echart_generator.py` | **唯一种 ECharts `option` 的源**（`create_chart`, ~1454 行） | 改产出格式/加适配器（核心） |
| `src/chart_renderer.py` | 调 `create_chart` 包成 `ChartItem.option` | 随源改 |
| `src/table_renderer.py` | 仅 `import GALAXY`（调色板常量） | 可保留（纯颜色） |
| ~71 个读 `option` 的文件（`dashboard/widget_generator.py`、`semantic_widget_generator.py`、`card_generator.py`、`report_builder.py`、`package_reconstructor.py`…） | 消费端读 `option`/字段 | 换格式时字段访问改 |

## 四、两个扩展（非核心，须单独找替代）
- **词云** `echarts-wordcloud`：`EChartView` 的 `import 'echarts-wordcloud'` + `echart_generator` wordcloud 分支 → 换 `d3-cloud`/`wordcloud2.js`。
- **3D/地理** `echarts-gl` + `registerMap('china')`：`GLMapView`/`CommandScreen`/`ChartWidget`/`MapWidget`/`exportEChartsDashboard.ts` CDN → 换 `deck.gl`/`Mapbox`/高德 JS。

## 五、换库要动的部分（汇总清单）
**最少 2 个漏斗口子（渲染）：** `EChartView.tsx`、`exportEChartsDashboard.ts`
**其余渲染器（8 处）：** `GLMapView.tsx`、`BigScreen/CommandScreen.tsx`、`BigScreen/MedicalDashboard.tsx`、`BigScreen/EGridLayout.tsx`、`DashboardRenderer/WidgetRenderer/{ChartWidget,KPIWidget,MapWidget}.tsx`
**生成端（1 源）：** `src/echart_generator.py` + `src/chart_renderer.py`
**格式跟随（消费端）：** 后端 ~71 个读 `option` 文件
**单独实现（无通用 option）：** 词云、3D/地理地图
**可保留（非 echarts）：** `html2canvas`（导出图片）、`@jiaminghi/data-view-react`（大屏排名榜）

## 相关
- [[图表渲染架构_后端只出ECharts_option]] —— 后端只出 option JSON、前端渲染的链路
- [[图表渲染库可替换性]] —— 能换但有约束；双口子转换器策略
