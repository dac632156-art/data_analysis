---
name: medical-dashboard-remove-map
overview: 去掉数据看板(medical)模板的「地理分布」地图区块，让左侧趋势图占满整行，其余区块不动。
design:
  architecture:
    framework: react
  styleKeywords:
    - 深空暗色
    - 大屏 BI
    - 圆角卡片
    - 细发光分隔
    - 整行占满
  fontSystem:
    fontFamily: Inter, PingFang SC, Microsoft YaHei
    heading:
      size: 20px
      weight: 700
    subheading:
      size: 12px
      weight: 700
    body:
      size: 14px
      weight: 400
  colorSystem:
    primary:
      - "#38BDF8"
      - "#7DD3FC"
      - "#8B5CF6"
    background:
      - "#020518"
      - "#0F172A"
    text:
      - "#F8FAFC"
      - "#94A3B8"
    functional:
      - "#34D399"
      - "#FB7185"
      - "#FBBF24"
todos:
  - id: remove-map-section
    content: 移除 MedicalDashboard Row2 右侧地理分布区块并清理 mainMap/sideMaps 变量
    status: pending
  - id: reflow-trend-row
    content: 将 Row2 栅格改单列，趋势区占满整行并重排副图并排网格
    status: pending
    dependencies:
      - remove-map-section
  - id: keep-map-classify
    content: 保留 useMemo 中 isMap/mapCharts 分类分支防止地图串入趋势区
    status: pending
    dependencies:
      - remove-map-section
  - id: verify-layout
    content: 本地 lint/构建校验并手动确认地图消失且趋势区占满无空洞
    status: pending
    dependencies:
      - reflow-trend-row
      - keep-map-classify
---

## 用户需求

在仪表盘的「数据看板」(medical 模板，对应 `MedicalDashboard.tsx`) 中，去掉「地理分布」地图区块。

## 产品概述

仅针对数据看板大屏（标题默认「数据看板」）的 Row 2 右侧地图区域做移除，地图卡片不再展示；其余模板（经典网格 grid 的 3D 地图、指挥中心 command 的 3D 地球）与其它区块保持不变。

## 核心特性

- 移除 Row 2 右侧「地理分布」区块（含主地图与副地图卡片），整段不渲染。
- 原地图占据的 1/3 列宽释放后，左侧「趋势分析」区块横向占满整行，充分使用空间。
- 趋势区内部重新排布：主趋势图保持大尺寸，副趋势图改为并排网格，适配加宽后的宽度。
- 保留地图卡片的分类吸收逻辑，确保地图类卡片不会串入趋势区以图表形式重新出现。
- 不改配色、不动后端、不动其它模板与 Row1/Row3/Row4 区块；纯前端热更新生效。

## 技术栈

- 前端框架：React + TypeScript（沿用现有组件）
- 样式方案：Tailwind 工具类 + 内联 style（与 `MedicalDashboard.tsx` 现状一致），不引入新依赖
- 纯前端单文件改动，无需重启 uvicorn

## 实现思路

采用「删渲染 + 改栅格 + 清变量 + 保分类」四步最小改动策略：

1. **删渲染**：移除 Row 2 右侧「地理分布」`<section>`（原 134–145 行），地图卡片不再进入 DOM。
2. **改栅格**：Row 2 外层 `grid` 的 `gridTemplateColumns: '2fr 1fr'` 改为单列（移除该 style 或设为 `1fr`），使左侧趋势 section 占满整行宽度，从而「相邻图表占满空间」。
3. **清变量**：删除因删渲染而失效的 `mainMap = mapCharts[0]` 与 `sideMaps = mapCharts.slice(1, 3)`（原 57–59 行），避免未使用变量残留。
4. **保分类**：保留 `useMemo` 中的 `isMap` 判定与 `mapCharts` 收集分支（else-if 顺序中 `isMap` 在 `isTrend` 之前），让地图卡片被分类「吞掉」而不渲染——这是防止地图数据以趋势图形式重新出现的关键安全带，不删除该分支。

## 实现细节

- **趋势区内部重排**：趋势 section 加宽后，将内部布局由纯纵向堆叠升级为「主趋势图全宽 + 副趋势图响应式并排网格」，充分利用释放出的横向空间、视觉更完整。
- 主趋势图：`mainTrend` 全宽，`height` 维持约 320。
- 副趋势图：`subTrends` 用 `gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))'` 并排，`height` 约 200；无副图时自然不渲染该网格。
- **性能**：仅删除/调整 JSX 与几个变量，无新增计算或副作用，零性能开销；`useMemo` 依赖 `[cards]` 不变，重渲染成本不变。
- **健壮性**：分类分支保留确保即便后端仍下发地图卡片，前端也不展示且不会串位；其余区块（KPI/排行/表格/预警洞察）与 `isMap` 之外的逻辑完全不动，控制改动爆炸半径。
- **向后兼容**：`mapCharts` 变量仍被收集但不再用于渲染；若未来需恢复地图，仅需在 Row 2 重新加回 section 即可，无需改动分类。

## 架构设计

仅修改单个展示组件，架构层级不变：
`DashboardPage` → `MedicalDashboard`（本次唯一改动点）→ `ChartBlock` 等子组件。
数据流 `cards` 入参不变；分类结果中 `mapCharts` 仅作为「吸收桶」，不再参与渲染。

## 目录结构

```
frontend/src/components/BigScreen/
└── MedicalDashboard.tsx   # [MODIFY] 唯一改动文件。移除 Row2 右侧「地理分布」地图 section；
                           #           Row2 外层 grid 改为单列使趋势区占满整行；
                           #           删除 mainMap/sideMaps 未用变量；
                           #           趋势区内部升级为主图全宽+副图并排网格；
                           #           保留 useMemo 中 isMap/mapCharts 分类分支（吸收地图卡片，防串位）。
```

## 设计风格

沿用现有「Galaxy AI Analytics」深空暗色大屏风格（深空背景 + 星光蓝描边 + 圆角卡片 + 细发光分隔线），不做任何配色与字体变更，仅调整布局结构。

## 页面块设计（仅 Row 2 变更）

- **Row 2 外层**：由 `2fr 1fr` 双列改为单列，趋势分析区块横向占满整行宽度，原地图 1/3 空间被趋势区吸收。
- **趋势分析区块（占满整行）**：
- 顶部「趋势分析」标题栏不变（紫条 + 大写小标题）。
- 主趋势图：全宽大图（height≈320），下方副趋势图以响应式并排网格（minmax 300px 自动折行）排列，height≈200，充分利用加宽后的横向空间，视觉饱满无空洞。
- 移除原右侧「地理分布」区块（青色描边卡片、主/副地图）整段，不再占位列。
- Row 1（KPI）、Row 3（排行+表格）、Row 4（预警+洞察）完全不变，保持大屏整体节奏一致。