---
title: React 全局使用盘点与替换成 Vue 的代价
aliases: [换Vue, React换Vue, 前端框架替换]
tags: [前端, React, Vue, 架构, 重构]
created: 2026-07-24
---

# React 全局使用盘点与替换成 Vue 的代价

> 用户问：全局用到 React 哪些部分？想替换成 Vue 麻烦吗，要替换哪些？

## 一、结论（实话）

- **后端完全不用动**：后端只吐 JSON API，与 React 解耦（搜 `src/` 无任何 React/JSX 耦合）。换 Vue 对 Python 服务零影响。
- **前端必须全量重写**：34 个 `.tsx` 组件**没有一个是"改几行"能变 Vue 的**，必须按 Vue 3 SFC + Composition API 重写。JSX 心智模型、hooks 生命周期与 Vue 模板/响应式不同，无无损自动化工具。
- **约 23 个 `.ts` 里只有一部分是框架无关的**：`api/client.ts`、`types/*.ts`、`theme/*.ts`、`utils/exportEChartsDashboard.ts` 可原样复用；但 `DashboardRenderer/InteractionBinder.ts`、`DashboardRenderer/hooks/*.ts` 直接写了 React hooks（`useXxx`），属 React 耦合，要重写。
- **难度一个数量级**：换 ECharts 只动 2 个漏斗口子；换 Vue 是重写整个视图层。详见 [[ECharts全局使用盘点与替换范围]]。

## 二、前端 React 依赖清单（package.json）

| 依赖 | 角色 | 换 Vue 动作 |
|---|---|---|
| `react` / `react-dom` (^18.3) | 核心框架 | → `vue` (^3) |
| `react-router-dom` (^6.28) | 路由 | → `vue-router` |
| `react-dropzone` (^15) | 文件拖拽上传 | → 原生 `dragover`/`drop` 或 `vue-filepond` 等 |
| `react-icons` (^5.6) / `lucide-react` (^1.18) | 图标 | → `@lucide/vue-next` / `@iconify/vue` |
| `@jiaminghi/data-view-react` (^1.2.5) | 大屏排名榜（DataV） | → `@jiaminghi/data-view`（有 Vue 版） |
| `class-variance-authority` / `clsx` / `tailwind-merge` | 类名工具 | **可保留**（与框架无关） |
| `echarts` / `echarts-gl` / `echarts-wordcloud` | 图表（见 [[ECharts全局使用盘点与替换范围]]） | **可保留**（与框架无关，Vue 里照常用 `echarts.init().setOption(option)`） |
| `html2canvas` / `axios` / `marked` / `countup.js` | 截图/HTTP/Markdown/数字动画 | **可保留**（框架无关） |

## 三、React 组件规模与状态管理

- **规模**：`frontend/src` 共 34 个 `.tsx` + 23 个 `.ts`。无 SSR、无 Next.js，纯 Vite + React SPA。
- **入口**：`main.tsx`（`ReactDOM.createRoot`） + `App.tsx`（`BrowserRouter` + `Routes` + `DataProvider`）。
- **状态管理**：**无 Redux/Zustand**，主要靠 `contexts/DataContext.tsx`（`createContext` + `useState`）。换 Vue → 用 `Pinia` store 或 `provide/inject`。
- **路由**：4 个页面 `UploadPage` / `CleanPage` / `AnalysisPage` / `DashboardPage`，包在 `Layout`/`Sidebar`。换 Vue → `vue-router` 的 `createRouter` + 路由表。
- **hooks 密度**：`DashboardPage` 32 处、`AnalysisPage` 21 处、`EChartView` 12 处、`UploadPage` 12 处… 全量 hooks 转换无法自动化。

## 四、换 Vue 要替换/重写的清单

**A. 必须重写（React 视图层，34 个 tsx）**
| 类别 | 文件 | 难度 |
|---|---|---|
| 入口/路由 | `main.tsx`、`App.tsx` | 低 |
| 布局 | `Layout/Layout.tsx`、`Layout/Sidebar.tsx`、`Layout/StarBackground.tsx` | 低 |
| 页面 | `UploadPage`(16K) / `CleanPage`(22K) / `AnalysisPage`(50K) / `DashboardPage`(32K) | **高（大页面）** |
| 核心渲染器 | `EChartView.tsx`(28K，含大量 useEffect/refs/事件) | **最高** |
| 地图 | `GLMapView.tsx`（WebGL 3D 地图） | 高 |
| 大屏 | `BigScreen/CommandScreen.tsx`(22K)、`EGridLayout.tsx`(14K)、`MedicalDashboard.tsx`(14K) | 高 |
| 看板引擎 | `DashboardRenderer/*`(17K+7.8K+5.7K)、`WidgetRenderer/*`(Chart/KPI/Map/Table/Insight) | 高 |
| 通用组件 | `DataTable`、`KPICards`、`MetricCard`、`AnimatedNumber`、`FileUploader`、`QueueModal`、`ErrorBoundary`、`VisualizationRenderer`、`TbHbTable` | 中 |
| React 耦合 .ts | `DashboardRenderer/InteractionBinder.ts`(18 hooks)、`hooks/useWidgetAnimation.ts`、`hooks/useLazyLoad.ts` | 中 |

**B. 可原样复用（框架无关 .ts）**
- `api/client.ts`（axios 封装）、`types/api.ts`、`types/dashboard.ts`、`types/index.ts`
- `theme/*.ts`（`Palette`/`Shadow`/`ChartStyle` 等 SSOT 常量）
- `utils/exportEChartsDashboard.ts`（纯 JS 字符串脚本，不 import React）

**C. 可保留的 npm 依赖**
- `echarts` / `echarts-gl` / `echarts-wordcloud`（Vue 里照用）、`html2canvas`、`axios`、`marked`、`countup.js`、`class-variance-authority`/`clsx`/`tailwind-merge`、`tailwindcss`(配置)、`postcss`/`autoprefixer`

## 五、关键策略

1. **后端零改动**：纯 JSON API 契约不变，Vue 前端照调 `api/client.ts`。
2. **图表零改动**：ECharts 的 `option` 是纯 JSON，Vue 版 `EChartView` 同样 `echarts.init(el).setOption(option)`。换 Vue 与 [[图表渲染库可替换性]] 是两件事，可独立进行。
3. **状态管理迁移**：`DataContext` → Pinia（推荐，比 provide/inject 更适合跨页共享数据）。
4. **没有无痛工具**：`react-to-vue` 类工具只适合简单展示组件，对 hooks 密集/动画/事件绑定的大组件无效。本质是重写。

## 六、工作量一句话

> 换 Vue = 重写 34 个 tsx 组件（含 50K 的 AnalysisPage、28K 的 EChartView、22K 的大屏） + 状态管理迁 Pinia + 6 个 React 依赖换 Vue 版；后端、ECharts、API client、类型、主题常量全部不动。难度约为"重新写一遍前端视图层"，但受益于可复用 .ts 与不变的后端契约，比纯从零略省。

## 相关

- 上游：[[图表渲染架构_后端只出ECharts_option]]、[[图表渲染库可替换性]]、[[ECharts全局使用盘点与替换范围]]
- 下游：若同时想换图表库见 [[ECharts全局使用盘点与替换范围]]
